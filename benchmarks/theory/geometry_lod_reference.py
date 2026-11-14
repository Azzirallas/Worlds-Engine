"""CPU-only screen-error and stable LOD choice reference for mesh representations.

Conservative proxy error estimates, NOT proof of pixel-perfect geometry accuracy.
"""

from dataclasses import dataclass
from math import inf, isfinite, radians, tan


def _real(v, positive=False):
    """Reject nonfinite, bool, negative and optionally zero scalar inputs."""
    if (type(v) not in (int, float) or not isfinite(v) or v < 0
            or (positive and v == 0)):
        raise ValueError("Invalid projection/error scalar")
    return float(v)


@dataclass(frozen=True)
class Camera:
    """One vertical pixel scale, perspective/orthographic projection and object depth."""
    distance: float
    bound_radius: float
    viewport_height: int = 1080
    perspective_fov_y_deg: float | None = 60.0
    ortho_height: float | None = None
    near: float = 0.05
    max_scale: float = 1.0

    def __post_init__(self):
        """Ensure camera parameters form exactly one finite supported projection."""
        _real(self.distance)
        _real(self.bound_radius)
        _real(self.near, positive=True)
        _real(self.max_scale, positive=True)
        if type(self.viewport_height) is not int or self.viewport_height < 1:
            raise ValueError("Invalid viewport height")
        if (self.perspective_fov_y_deg is None) == (self.ortho_height is None):
            raise ValueError("Choose exactly one projection mode")
        if self.ortho_height is not None:
            _real(self.ortho_height, positive=True)
        else:
            fov = _real(self.perspective_fov_y_deg, positive=True)
            if not fov < 179:
                raise ValueError("Perspective FOV must stay below 179 degrees")

    def error_px(self, world_error):
        """Use closest sphere depth to conservatively bound projected size."""
        error = _real(world_error) * self.max_scale
        if error == 0:
            return 0.0
        if self.ortho_height is not None:
            return error * self.viewport_height / self.ortho_height
        closest = self.distance - self.bound_radius
        if closest <= self.near:
            return inf  # Near-plane crossing: demand finest available detail.
        projection_scale = self.viewport_height / (2 * tan(radians(self.perspective_fov_y_deg) / 2))
        return error * projection_scale / closest


@dataclass(frozen=True)
class Level:
    """One parent-first representation with a conservative world-space error bound."""
    name: str
    parent: str | None
    error: float


@dataclass(frozen=True)
class Choice:
    """Selected resident page plus ideal target, error, fallback and transition state."""
    page: str
    preferred: str
    pixel_error: float
    fallback: bool
    within_budget: bool
    changed: bool


class LODSelector:
    """One chain of independently authored levels from coarse to fine detail."""

    def __init__(self, levels):
        """Validate strict parent chain and nonincreasing conservative error bounds."""
        levels = tuple(levels)
        if not levels:
            raise ValueError("At least one coarse LOD is mandatory")
        seen, previous = set(), None
        for level in levels:
            if not isinstance(level, Level) or type(level.name) is not str or not level.name:
                raise ValueError("Invalid LOD")
            if level.name in seen or level.parent != previous:
                raise ValueError("Invalid or branching LOD chain")
            _real(level.error)
            if previous is not None and level.error > last_error:
                raise ValueError("Finer LOD must not advertise worse error")
            seen.add(level.name)
            previous, last_error = level.name, level.error
        self.levels = levels
        self.names = tuple(level.name for level in levels)

    def choose(self, camera, budget_px, resident, previous=None, hysteresis=0.15):
        """Return resident detail, with hysteresis and explicit coarse quality fallback."""
        if not isinstance(camera, Camera):
            raise ValueError("Expected validated camera")
        budget = _real(budget_px, positive=True)
        h = _real(hysteresis)
        if h >= 1:
            raise ValueError("Hysteresis must be smaller than one")
        available = set(resident)
        if self.names[0] not in available:
            raise ValueError("Coarse fallback must always remain resident")
        if previous is not None and previous not in self.names:
            raise ValueError("Previous LOD must belong to this asset")
        max_available = 0
        for i in range(1, len(self.levels)):
            if self.names[i] not in available:
                break
            max_available = i
        errors = [camera.error_px(level.error) for level in self.levels]
        ideal = next((i for i, error in enumerate(errors) if error <= budget), len(errors)-1)
        target = min(ideal, max_available)
        previous_idx = self.names.index(previous) if previous in self.names[:max_available+1] else None
        selected = target
        if previous_idx is not None:
            if target > previous_idx and errors[previous_idx] <= budget * (1 + h):
                selected = previous_idx  # Do not upgrade for a tiny threshold crossing.
            elif target < previous_idx and errors[target] >= budget * (1 - h):
                selected = previous_idx  # Do not downgrade until comfortably below budget.
        return Choice(self.names[selected], self.names[ideal], errors[selected],
                      selected < ideal, errors[selected] <= budget,
                      previous is not None and self.names[selected] != previous)

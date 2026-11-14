"""Pure-CPU visibility reference for a possible optional Worlds Engine GPU instance path.

This models conservative frustum selection and dirty-record contracts only; it does
not call Godot, render pixels, simulate GPU scheduling or predict performance.
"""

from dataclasses import dataclass, replace
from math import floor, isfinite, sqrt


@dataclass(frozen=True, order=True)
class Handle:
    """Generation-tagged presentation slot; never a persistent simulation entity ID."""
    slot: int
    generation: int


@dataclass(frozen=True)
class Sphere:
    """Conservative world-space bounding sphere."""
    center: tuple[float, float, float]
    radius: float

    def __post_init__(self):
        """Reject invalid or non-conservative bounds."""
        if (len(self.center) != 3 or not all(isfinite(v) for v in self.center)
                or not isfinite(self.radius) or self.radius < 0):
            raise ValueError("Invalid bounding sphere")
        object.__setattr__(self, "center", tuple(self.center))

    def transformed(self, basis, translation):
        """Apply an affine transform with a safe nonuniform/shear radius bound."""
        if (len(basis) != 3 or any(len(row) != 3 for row in basis)
                or len(translation) != 3
                or not all(isfinite(v) for row in basis for v in row)
                or not all(isfinite(v) for v in translation)):
            raise ValueError("Invalid affine transform")
        center = tuple(sum(basis[i][j] * self.center[j] for j in range(3))
                       + translation[i] for i in range(3))
        # Spectral norm <= sqrt(matrix 1-norm * infinity-norm).
        one_norm = max(sum(abs(basis[i][j]) for i in range(3)) for j in range(3))
        inf_norm = max(sum(abs(v) for v in row) for row in basis)
        return Sphere(center, self.radius * sqrt(one_norm * inf_norm))


@dataclass(frozen=True)
class Plane:
    """Frustum half-space: normal dot position + offset >= 0 means inside."""
    normal: tuple[float, float, float]
    offset: float

    def __post_init__(self):
        """Require finite nonzero normals; normalization is unnecessary."""
        if (len(self.normal) != 3 or not all(isfinite(v) for v in self.normal)
                or not isfinite(self.offset) or not any(self.normal)):
            raise ValueError("Invalid frustum plane")
        object.__setattr__(self, "normal", tuple(self.normal))

    def signed(self, point):
        """Return signed half-space distance scaled by normal length."""
        return sum(a * b for a, b in zip(self.normal, point)) + self.offset


@dataclass(frozen=True)
class View:
    """Per-camera frustum and 32-bit visibility mask; no shared temporal state."""
    planes: tuple[Plane, ...]
    layers: int = 0xFFFFFFFF

    def __post_init__(self):
        """Validate the immutable view description."""
        if not 0 <= self.layers <= 0xFFFFFFFF or not all(isinstance(p, Plane) for p in self.planes):
            raise ValueError("Invalid view")
        object.__setattr__(self, "planes", tuple(self.planes))


@dataclass(frozen=True)
class Instance:
    """Minimum visual record for CPU visibility parity tests."""
    sphere: Sphere
    layers: int = 1
    enabled: bool = True

    def __post_init__(self):
        """Disallow invalid layer masks and bounds."""
        if not isinstance(self.sphere, Sphere) or not 0 <= self.layers <= 0xFFFFFFFF:
            raise ValueError("Invalid instance")


@dataclass(frozen=True)
class Update:
    """GPU-target record update, including deletion tombstones."""
    handle: Handle
    record: Instance | None


@dataclass(frozen=True)
class DirtyRun:
    """Contiguous slot update interval; suitable for a future staging upload."""
    start: int
    values: tuple[Update, ...]


@dataclass(frozen=True)
class Visibility:
    """All visible handles plus bounded-path eligibility and diagnostic counts."""
    handles: tuple[Handle, ...]
    regions_tested: int
    instances_tested: int
    fallback_required: bool


def sphere_intersects(sphere, planes):
    """Reject only spheres wholly outside a frustum half-space."""
    for plane in planes:
        normal_length = sqrt(sum(v * v for v in plane.normal))
        if plane.signed(sphere.center) < -sphere.radius * normal_length:
            return False
    return True


def box_intersects(bounds, planes):
    """Reject AABBs only when the extreme positive vertex is outside a plane."""
    low, high = bounds
    for plane in planes:
        positive = tuple(high[i] if plane.normal[i] >= 0 else low[i] for i in range(3))
        if plane.signed(positive) < 0:
            return False
    return True


class Scene:
    """Independent, reference-only region-culling and change-coalescing model."""

    def __init__(self, region_size=16.0):
        """Create an empty scene with nonzero finite spatial buckets."""
        if not isfinite(region_size) or region_size <= 0:
            raise ValueError("Invalid region size")
        self.region_size = region_size
        self.records = []
        self.generations = []
        self.free = []
        self.regions = {}
        self.slot_region = {}
        self.dirty = set()
        self.bounds_cache = {}
        self.invalid_regions = set()

    def _region_key(self, sphere):
        """Assign by center; conservative region bounds retain straddling spheres."""
        return tuple(floor(v / self.region_size) for v in sphere.center)

    def _invalidate(self, key):
        """Recompute exactly when region membership or instance bounds change."""
        self.invalid_regions.add(key)

    def _attach(self, slot, record):
        """Add one occupied slot to its spatial region."""
        key = self._region_key(record.sphere)
        self.regions.setdefault(key, set()).add(slot)
        self.slot_region[slot] = key
        self._invalidate(key)

    def _detach(self, slot):
        """Remove a slot and invalidate the region's bounds."""
        key = self.slot_region.pop(slot)
        members = self.regions[key]
        members.remove(slot)
        if not members:
            del self.regions[key]
            self.bounds_cache.pop(key, None)
            self.invalid_regions.discard(key)
        else:
            self._invalidate(key)

    def _read(self, handle):
        """Reject stale generations and empty slots."""
        if (not isinstance(handle, Handle) or handle.slot < 0
                or handle.slot >= len(self.records)
                or self.generations[handle.slot] != handle.generation
                or self.records[handle.slot] is None):
            raise ValueError("Stale or invalid render handle")
        return self.records[handle.slot]

    def create(self, record):
        """Allocate or reuse one slot with the current generation."""
        if not isinstance(record, Instance):
            raise ValueError("Invalid instance")
        if self.free:
            slot = self.free.pop()
        else:
            slot = len(self.records)
            self.records.append(None)
            self.generations.append(1)
        self.records[slot] = record
        self._attach(slot, record)
        self.dirty.add(slot)
        return Handle(slot, self.generations[slot])

    def change(self, handle, *, sphere=None, layers=None, enabled=None):
        """Replace an instance, rehome it if needed, and coalesce dirty writes."""
        old = self._read(handle)
        next_record = replace(old, sphere=old.sphere if sphere is None else sphere,
                              layers=old.layers if layers is None else layers,
                              enabled=old.enabled if enabled is None else enabled)
        self._detach(handle.slot)
        self.records[handle.slot] = next_record
        self._attach(handle.slot, next_record)
        self.dirty.add(handle.slot)

    def delete(self, handle):
        """Publish a deletion tombstone and advance generation before slot reuse."""
        self._read(handle)
        self._detach(handle.slot)
        self.records[handle.slot] = None
        self.generations[handle.slot] += 1
        self.free.append(handle.slot)
        self.dirty.add(handle.slot)

    def dirty_runs(self):
        """Consume sorted consecutive slots, including overwritten and deleted records."""
        slots = sorted(self.dirty)
        self.dirty.clear()
        runs = []
        for slot in slots:
            value = Update(Handle(slot, self.generations[slot]), self.records[slot])
            if runs and runs[-1][-1].handle.slot == slot - 1:
                runs[-1].append(value)
            else:
                runs.append([value])
        return tuple(DirtyRun(run[0].handle.slot, tuple(run)) for run in runs)

    def _region_bounds(self, key):
        """Build a conservative union of all member spheres, including disabled members."""
        if key in self.invalid_regions or key not in self.bounds_cache:
            low = [float("inf")] * 3
            high = [-float("inf")] * 3
            for slot in self.regions[key]:
                sphere = self.records[slot].sphere
                for i in range(3):
                    low[i] = min(low[i], sphere.center[i] - sphere.radius)
                    high[i] = max(high[i], sphere.center[i] + sphere.radius)
            self.bounds_cache[key] = (tuple(low), tuple(high))
            self.invalid_regions.discard(key)
        return self.bounds_cache[key]

    def full_scan(self, view):
        """Ground-truth control: scan every occupied instance, without region pruning."""
        return tuple(Handle(i, self.generations[i]) for i, rec in enumerate(self.records)
                     if rec is not None and rec.enabled and (rec.layers & view.layers)
                     and sphere_intersects(rec.sphere, view.planes))

    def cull(self, view, capacity=None):
        """Select conservatively and force fallback rather than truncate on overflow."""
        if not isinstance(view, View) or (capacity is not None and capacity <= 0):
            raise ValueError("Invalid view or output capacity")
        visible = []
        tested = 0
        regions_tested = 0
        for key in sorted(self.regions):
            regions_tested += 1
            if not box_intersects(self._region_bounds(key), view.planes):
                continue
            for slot in sorted(self.regions[key]):
                tested += 1
                rec = self.records[slot]
                if rec.enabled and (rec.layers & view.layers) and sphere_intersects(rec.sphere, view.planes):
                    visible.append(Handle(slot, self.generations[slot]))
        visible.sort()
        return Visibility(tuple(visible), regions_tested, tested,
                          capacity is not None and len(visible) > capacity)

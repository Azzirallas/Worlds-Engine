"""CPU-only contract for a guarded non-indexed GPU indirect draw command.

This is an isolated data/ABI reference, NOT a Godot renderer implementation.
"""

from dataclasses import dataclass
from struct import Struct

U32_MAX = (1 << 32) - 1
DRAW_INDIRECT = Struct('<4I')  # vertexCount, instanceCount, firstVertex, firstInstance
FLAG_OUTPUT_OVERFLOW = 1
FLAG_INVALID_DATA = 2
FLAG_STALE_GENERATION = 4


def _u32(value):
    """Reject invalid or out-of-range unsigned 32-bit fields."""
    if type(value) is not int or not 0 <= value <= U32_MAX:
        raise ValueError('Expected uint32')
    return value


@dataclass(frozen=True)
class VisibilityCounters:
    """Atomic output count and fault flags produced by the visibility kernel."""
    visible_count: int
    flags: int = 0

    def __post_init__(self):
        """Validate fields before attempting to construct a draw command."""
        _u32(self.visible_count)
        _u32(self.flags)


@dataclass(frozen=True)
class DrawCommand:
    """Vulkan/RenderingDevice non-indexed indirect command: 16 little-endian bytes."""
    vertex_count: int
    instance_count: int
    first_vertex: int = 0
    first_instance: int = 0

    def __post_init__(self):
        """Ensure the in-memory packet cannot silently wrap on serialization."""
        for value in (self.vertex_count, self.instance_count,
                      self.first_vertex, self.first_instance):
            _u32(value)

    def to_bytes(self):
        """Pack the exact ABI for the Godot non-indexed indirect draw path."""
        return DRAW_INDIRECT.pack(self.vertex_count, self.instance_count,
                                  self.first_vertex, self.first_instance)

    @staticmethod
    def from_bytes(raw):
        """Decode one complete non-indexed draw command."""
        if len(raw) != DRAW_INDIRECT.size:
            raise ValueError('Indirect draw command must be exactly 16 bytes')
        return DrawCommand(*DRAW_INDIRECT.unpack(raw))


@dataclass(frozen=True)
class DrawDecision:
    """Safe GPU packet and whether caller must use standard mesh fallback."""
    command: DrawCommand
    fallback_required: bool
    reason: str


def finalize_draw(counters, capacity, vertex_count, max_instances=None):
    """Suppress the indirect draw on ANY error or exceeded output capacity.

    A zero-instance command is not a fallback draw. The caller must preserve
    ordinary rendering separately when ``fallback_required`` is true.
    """
    if not isinstance(counters, VisibilityCounters):
        raise ValueError('Missing visibility counter snapshot')
    capacity = _u32(capacity)
    vertex_count = _u32(vertex_count)
    max_instances = capacity if max_instances is None else _u32(max_instances)

    reasons = []
    if counters.flags:
        reasons.append('visibility_flags')
    if counters.visible_count > capacity:
        reasons.append('output_overflow')
    if counters.visible_count > max_instances:
        reasons.append('draw_limit')
    if vertex_count == 0:
        reasons.append('invalid_mesh')
    unsafe = bool(reasons)
    return DrawDecision(DrawCommand(vertex_count, 0 if unsafe else counters.visible_count),
                        unsafe, ','.join(reasons) if reasons else 'valid')

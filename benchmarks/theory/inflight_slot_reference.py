"""CPU-only reference for safe GPU presentation-slot updates and frame retirement.

No GPU timing, fence API, renderer integration, or graphics correctness is implied.
"""

from copy import deepcopy
from dataclasses import dataclass


UINT32_MAX = 0xFFFFFFFF


class CapacityError(RuntimeError):
    """The experimental table cannot safely accept another presentation slot."""


@dataclass(frozen=True, order=True)
class Handle:
    """Transient render slot and generation, distinct from persistent world identity."""
    slot: int
    generation: int
    scene_epoch: int = 1


@dataclass(frozen=True)
class Packet:
    """One versioned upload or tombstone; may arrive out of order."""
    handle: Handle
    revision: int
    value: object | None


@dataclass(frozen=True)
class Submission:
    """Decision for optional fast path; rejected requests require conventional drawing."""
    accepted: bool
    frame: int | None
    reason: str


class FrameSlots:
    """Reference-model table with generation checks and deferred unsafe mutations."""

    def __init__(self, max_slots=None, max_inflight=3, max_generation=UINT32_MAX,
                 max_revision=UINT32_MAX, scene_epoch=1, max_scene_epoch=UINT32_MAX):
        """Bound slot and outstanding-frame counts without silently dropping objects."""
        if (max_slots is not None and (type(max_slots) is not int or not 0 <= max_slots <= UINT32_MAX + 1)
                or type(max_inflight) is not int or max_inflight < 1
                or type(max_generation) is not int or not 2 <= max_generation <= UINT32_MAX
                or type(max_revision) is not int or not 1 <= max_revision <= UINT32_MAX
                or type(scene_epoch) is not int or type(max_scene_epoch) is not int
                or not 1 <= scene_epoch <= max_scene_epoch <= UINT32_MAX):
            raise ValueError("Invalid frame table limits")
        self.max_slots = max_slots
        self.max_inflight = max_inflight
        self.max_generation = max_generation
        self.max_revision = max_revision
        self.max_scene_epoch = max_scene_epoch
        self.scene_epoch = scene_epoch
        self.reset_pending = False
        self.cpu = []
        self.gpu = []
        self.generation = []
        self.revision = []
        self.published = []
        self.slot_refs = []  # Incremented per admitted frame; O(1) referenced test.
        self.free = []
        self.retiring = set()
        self.inflight = {}
        self.deferred = {}
        self.next_frame = 1  # Never recycle tickets across a reset.

    def _active(self):
        """Refuse scene mutations while an old scene is draining."""
        if self.reset_pending:
            raise RuntimeError("Scene reset pending; conventional rendering required")

    def _slot(self, handle):
        """Validate the live CPU identity, never trusting only a recycled slot index."""
        if (not isinstance(handle, Handle) or handle.scene_epoch != self.scene_epoch
                or handle.slot < 0
                or handle.slot >= len(self.cpu)
                or self.generation[handle.slot] != handle.generation
                or self.cpu[handle.slot] is None):
            raise ValueError("Invalid or stale presentation handle")
        return handle.slot

    def create(self, value):
        """Allocate a live slot and return an initial packet; caller must publish it."""
        self._active()
        if value is None:
            raise ValueError("Use delete to represent a tombstone")
        if self.free:
            slot = self.free.pop()
        else:
            if (len(self.cpu) >= UINT32_MAX + 1
                    or self.max_slots is not None and len(self.cpu) >= self.max_slots):
                raise CapacityError("Presentation table full; use conventional rendering")
            slot = len(self.cpu)
            self.cpu.append(None)
            self.gpu.append(None)
            self.generation.append(1)
            self.revision.append(0)
            self.published.append(0)
            self.slot_refs.append(0)
        if self.generation[slot] >= self.max_generation:
            raise CapacityError("Retired generation is not reusable")
        self.cpu[slot] = deepcopy(value)
        self.revision[slot] = 1
        self.published[slot] = 0
        self.gpu[slot] = None
        return Packet(Handle(slot, self.generation[slot], self.scene_epoch), 1, deepcopy(value))

    def update(self, handle, value):
        """Issue a latest-state packet, leaving existing in-flight GPU data untouched."""
        self._active()
        if value is None:
            raise ValueError("Use delete for tombstones")
        slot = self._slot(handle)
        if self.revision[slot] >= self.max_revision:
            raise CapacityError("Revision would wrap; retire/recreate or use conventional rendering")
        self.cpu[slot] = deepcopy(value)
        self.revision[slot] += 1
        return Packet(handle, self.revision[slot], deepcopy(value))

    def delete(self, handle):
        """Invalidate CPU identity immediately; defer the GPU tombstone until safe."""
        self._active()
        slot = self._slot(handle)
        self.cpu[slot] = None
        # The last generation is a terminal tombstone, never a reusable identity.
        if self.generation[slot] >= self.max_generation:
            raise ValueError("A live slot cannot have terminal generation")
        self.generation[slot] += 1
        self.revision[slot] = 1
        # A new generation has no published revision, even if the previous had 1.
        self.published[slot] = 0
        self.retiring.add(slot)
        # A deleted slot is deliberately not free until its tombstone is published.
        return Packet(Handle(slot, self.generation[slot], self.scene_epoch), 1, None)

    def _referenced(self, slot):
        """Track every outstanding frame that may still read the physical slot."""
        return self.slot_refs[slot] != 0

    def _recycle(self, slot):
        """Reuse only after final frame completion AND published deletion tombstone."""
        if (slot in self.retiring and not self._referenced(slot)
                and self.published[slot] == self.revision[slot]
                and self.gpu[slot] is None):
            self.retiring.remove(slot)
            if self.generation[slot] < self.max_generation:
                self.free.append(slot)  # Terminal tombstones never recycle.

    def publish(self, packet):
        """Validate generation/revision and defer writes referenced by GPU frames."""
        if not isinstance(packet, Packet):
            raise ValueError("Expected a versioned upload packet")
        if self.reset_pending:
            return "RESET_PENDING"
        slot = packet.handle.slot
        if (packet.handle.scene_epoch != self.scene_epoch or slot < 0
                or slot >= len(self.cpu)
                or self.generation[slot] != packet.handle.generation
                or self.revision[slot] != packet.revision
                or packet.value != self.cpu[slot]):
            return "STALE"
        if self.published[slot] == packet.revision:
            return "DUPLICATE"
        if self._referenced(slot):
            self.deferred[slot] = packet  # coalesce to latest version
            return "DEFERRED"
        self.gpu[slot] = deepcopy(packet.value)
        self.published[slot] = packet.revision
        self.deferred.pop(slot, None)
        self._recycle(slot)
        return "APPLIED"

    def submit(self, handles):
        """Admit a frame only when each handle's GPU state matches the CPU revision."""
        if self.reset_pending:
            return Submission(False, None, "reset_pending")
        handles = tuple(handles)
        if len(self.inflight) >= self.max_inflight:
            return Submission(False, None, "inflight_budget")
        if len(set(handles)) != len(handles):
            return Submission(False, None, "duplicate_handle")
        for h in handles:
            try:
                slot = self._slot(h)
            except ValueError:
                return Submission(False, None, "stale_handle")
            if (slot in self.retiring or self.published[slot] != self.revision[slot]
                    or self.gpu[slot] != self.cpu[slot]):
                return Submission(False, None, "upload_pending")
        frame = self.next_frame
        self.next_frame += 1
        self.inflight[frame] = handles
        for h in handles:
            self.slot_refs[h.slot] += 1
        return Submission(True, frame, "ready")

    def retire(self, frame):
        """Simulate explicit completed-frame acknowledgement, including out of order."""
        if frame not in self.inflight:
            raise ValueError("Unknown or already completed frame")
        handles = self.inflight.pop(frame)
        for slot in sorted(set(h.slot for h in handles)):
            if self.slot_refs[slot] <= 0:
                raise AssertionError("Frame reference counter underflow")
            self.slot_refs[slot] -= 1
            if self.reset_pending or self._referenced(slot):
                continue
            pending = self.deferred.pop(slot, None)
            if pending is not None:
                self.publish(pending)
            self._recycle(slot)

    def begin_reset(self):
        """Freeze old-scene uploads/submits while existing GPU frames drain."""
        if self.reset_pending:
            raise RuntimeError("Reset already pending")
        if self.scene_epoch >= self.max_scene_epoch:
            raise CapacityError("Scene epoch would wrap; rebuild device identity")
        self.reset_pending = True
        self.deferred.clear()  # Old packets must never publish after scene reset.

    def complete_reset(self):
        """Replace table only after all old GPU frame references have retired."""
        if not self.reset_pending:
            raise RuntimeError("No scene reset pending")
        if self.inflight or any(self.slot_refs):
            raise RuntimeError("Old scene remains in flight")
        self.scene_epoch += 1
        self.cpu.clear()
        self.gpu.clear()
        self.generation.clear()
        self.revision.clear()
        self.published.clear()
        self.slot_refs.clear()
        self.free.clear()
        self.retiring.clear()
        self.deferred.clear()
        self.reset_pending = False
        # next_frame deliberately stays monotonic to reject late old completions.

    def quiescent(self):
        """Signal whether no old work, deferred writes or pending reset remain."""
        return (not self.reset_pending and not self.inflight and not self.deferred
                and not self.retiring and not any(self.slot_refs))

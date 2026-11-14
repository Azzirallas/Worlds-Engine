"""CPU-only reference for safe GPU presentation-slot updates and frame retirement.

No GPU timing, fence API, renderer integration, or graphics correctness is implied.
"""

from copy import deepcopy
from dataclasses import dataclass


class CapacityError(RuntimeError):
    """The experimental table cannot safely accept another presentation slot."""


@dataclass(frozen=True, order=True)
class Handle:
    """Transient render slot and generation, distinct from persistent world identity."""
    slot: int
    generation: int


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

    def __init__(self, max_slots=None, max_inflight=3):
        """Bound slot and outstanding-frame counts without silently dropping objects."""
        if (max_slots is not None and (type(max_slots) is not int or max_slots < 0)
                or type(max_inflight) is not int or max_inflight < 1):
            raise ValueError("Invalid frame table limits")
        self.max_slots = max_slots
        self.max_inflight = max_inflight
        self.cpu = []
        self.gpu = []
        self.generation = []
        self.revision = []
        self.published = []
        self.free = []
        self.retiring = set()
        self.inflight = {}
        self.deferred = {}
        self.next_frame = 1

    def _slot(self, handle):
        """Validate the live CPU identity, never trusting only a recycled slot index."""
        if (not isinstance(handle, Handle) or handle.slot < 0
                or handle.slot >= len(self.cpu)
                or self.generation[handle.slot] != handle.generation
                or self.cpu[handle.slot] is None):
            raise ValueError("Invalid or stale presentation handle")
        return handle.slot

    def create(self, value):
        """Allocate a live slot and return an initial packet; caller must publish it."""
        if value is None:
            raise ValueError("Use delete to represent a tombstone")
        if self.free:
            slot = self.free.pop()
        else:
            if self.max_slots is not None and len(self.cpu) >= self.max_slots:
                raise CapacityError("Presentation table full; use conventional rendering")
            slot = len(self.cpu)
            self.cpu.append(None)
            self.gpu.append(None)
            self.generation.append(1)
            self.revision.append(0)
            self.published.append(0)
        self.cpu[slot] = deepcopy(value)
        self.revision[slot] = 1
        self.published[slot] = 0
        self.gpu[slot] = None
        return Packet(Handle(slot, self.generation[slot]), 1, deepcopy(value))

    def update(self, handle, value):
        """Issue a latest-state packet, leaving existing in-flight GPU data untouched."""
        if value is None:
            raise ValueError("Use delete for tombstones")
        slot = self._slot(handle)
        self.cpu[slot] = deepcopy(value)
        self.revision[slot] += 1
        return Packet(handle, self.revision[slot], deepcopy(value))

    def delete(self, handle):
        """Invalidate CPU identity immediately; defer the GPU tombstone until safe."""
        slot = self._slot(handle)
        self.cpu[slot] = None
        self.generation[slot] += 1
        self.revision[slot] = 1
        self.retiring.add(slot)
        # A deleted slot is deliberately not free until its tombstone is published.
        return Packet(Handle(slot, self.generation[slot]), 1, None)

    def _referenced(self, slot):
        """Track every outstanding frame that may still read the physical slot."""
        return any(any(h.slot == slot for h in handles)
                   for handles in self.inflight.values())

    def _recycle(self, slot):
        """Reuse only after final frame completion AND published deletion tombstone."""
        if (slot in self.retiring and not self._referenced(slot)
                and self.published[slot] == self.revision[slot]
                and self.gpu[slot] is None):
            self.retiring.remove(slot)
            self.free.append(slot)

    def publish(self, packet):
        """Validate generation/revision and defer writes referenced by GPU frames."""
        if not isinstance(packet, Packet):
            raise ValueError("Expected a versioned upload packet")
        slot = packet.handle.slot
        if (slot < 0 or slot >= len(self.cpu)
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
        return Submission(True, frame, "ready")

    def retire(self, frame):
        """Simulate explicit completed-frame acknowledgement, including out of order."""
        if frame not in self.inflight:
            raise ValueError("Unknown or already completed frame")
        handles = self.inflight.pop(frame)
        for slot in sorted(set(h.slot for h in handles)):
            if self._referenced(slot):
                continue
            pending = self.deferred.pop(slot, None)
            if pending is not None:
                self.publish(pending)
            self._recycle(slot)

    def quiescent(self):
        """Signal whether all old GPU references and deferred writes are retired."""
        return not self.inflight and not self.deferred and not self.retiring

"""CPU-only staging/upload scheduling model for an optional GPU instance path.

Stages immutable byte payloads into bounded, versioned batches. Acknowledge
simulates transfer completion; it is NOT a GPU driver command or fence.
"""

from collections import OrderedDict
from dataclasses import dataclass

from gpu_slot_packet_abi import FLAG_TOMBSTONE, SlotPacket, UINT32_MAX
from inflight_slot_reference import CapacityError, FrameSlots, Packet

HEADER_BYTES = 32
ALIGNMENT = 16


def _limit(value, name):
    """Require a positive host-side byte/packet budget."""
    if type(value) is not int or not 1 <= value <= UINT32_MAX:
        raise ValueError(f'Invalid {name}')
    return value


def _weight(packet):
    """Reserve descriptor bytes and an aligned upper bound for immutable payload."""
    n = 0 if packet.value is None else len(packet.value)
    return HEADER_BYTES + ((n + ALIGNMENT - 1) // ALIGNMENT) * ALIGNMENT


@dataclass(frozen=True)
class UploadBatch:
    """One immutable transfer snapshot; the queue retains ownership until ack."""
    ticket: int
    scene_epoch: int
    descriptors: tuple[SlotPacket, ...]
    staging: bytes
    packets: tuple[Packet, ...]

    @property
    def charged_bytes(self):
        """Account for aligned staging and all 32-byte descriptor headers."""
        return sum(_weight(packet) for packet in self.packets)


class StagingUploads:
    """Bounded queue, coalescing and simulated completion with scene reset gates."""

    def __init__(self, slots, max_staging_bytes=65536, max_batch_bytes=4096,
                 max_packets=1024, max_batches=3):
        """Constrain pending+in-flight memory, each batch and outstanding transfers."""
        if not isinstance(slots, FrameSlots):
            raise ValueError('Expected frame-safe presentation table')
        self.slots = slots
        self.max_staging_bytes = _limit(max_staging_bytes, 'staging budget')
        self.max_batch_bytes = _limit(max_batch_bytes, 'batch budget')
        self.max_packets = _limit(max_packets, 'packet budget')
        self.max_batches = _limit(max_batches, 'batch count')
        if self.max_batch_bytes > self.max_staging_bytes:
            raise ValueError('Batch cannot exceed the staging budget')
        self.pending = OrderedDict()
        self.transfers = {}
        self.busy_slots = set()
        self.held_bytes = 0
        self.next_ticket = 1

    def _current(self, packet):
        """Compare the full authoritative scene, slot, revision and CPU payload."""
        if not isinstance(packet, Packet):
            return False
        h = packet.handle
        slot = h.slot
        return (h.scene_epoch == self.slots.scene_epoch
                and 0 <= slot < len(self.slots.cpu)
                and self.slots.generation[slot] == h.generation
                and self.slots.revision[slot] == packet.revision
                and self.slots.cpu[slot] == packet.value)

    def _count(self):
        """Count separately retained packets even when their slots match."""
        return len(self.pending) + sum(len(batch.packets) for batch in self.transfers.values())

    def _remove_pending(self, slot):
        """Release one queued snapshot without touching outstanding transfers."""
        old = self.pending.pop(slot, None)
        if old is not None:
            self.held_bytes -= _weight(old)

    def enqueue(self, packet):
        """Coalesce the latest immutable packet; refuse on memory pressure."""
        if self.slots.reset_pending:
            return 'RESET_PENDING'
        if not isinstance(packet, Packet):
            raise ValueError('Expected a presentation upload Packet')
        if packet.value is not None and (type(packet.value) is not bytes or not packet.value):
            raise ValueError('Live staging payload must be nonempty immutable bytes')
        if not self._current(packet):
            return 'STALE'
        slot = packet.handle.slot
        old = self.pending.get(slot)
        if old is not None and old == packet:
            return 'DUPLICATE'
        bytes_needed = self.held_bytes - (_weight(old) if old is not None else 0) + _weight(packet)
        packet_count = self._count() + (0 if old is not None else 1)
        if (_weight(packet) > self.max_batch_bytes or bytes_needed > self.max_staging_bytes
                or packet_count > self.max_packets):
            raise CapacityError('Upload staging budget exhausted; use conventional rendering')
        if old is not None:
            self._remove_pending(slot)
        # Immutable value is held by the batch without retaining mutable caller data.
        snapshot = Packet(packet.handle, packet.revision, packet.value)
        self.pending[slot] = snapshot
        self.held_bytes += _weight(snapshot)
        return 'QUEUED'

    def prepare(self):
        """Select safe, current packets within the byte budget without publishing."""
        if self.slots.reset_pending or len(self.transfers) >= self.max_batches:
            return None
        payload = bytearray()
        packets = []
        descriptors = []
        for slot, packet in tuple(self.pending.items()):
            if not self._current(packet):
                self._remove_pending(slot)
                continue
            if slot in self.busy_slots or self.slots.slot_refs[slot]:
                continue
            if self.slots.published[slot] == packet.revision:
                self._remove_pending(slot)
                continue
            offset = ((len(payload) + ALIGNMENT - 1) // ALIGNMENT) * ALIGNMENT
            n = 0 if packet.value is None else len(packet.value)
            total = offset + n + (len(packets) + 1) * HEADER_BYTES
            if total > self.max_batch_bytes:
                continue
            if packet.value is None:
                descriptor = SlotPacket(slot, packet.handle.generation, packet.revision,
                                        packet.handle.scene_epoch, 0, 0, FLAG_TOMBSTONE)
            else:
                descriptor = SlotPacket(slot, packet.handle.generation, packet.revision,
                                        packet.handle.scene_epoch, offset, n)
                payload.extend(b'\0' * (offset - len(payload)))
                payload.extend(packet.value)
            descriptor.validate_payload(len(payload))
            packets.append(packet)
            descriptors.append(descriptor)
        if not packets:
            return None
        for packet in packets:
            self.pending.pop(packet.handle.slot)
            self.busy_slots.add(packet.handle.slot)
        batch = UploadBatch(self.next_ticket, self.slots.scene_epoch, tuple(descriptors),
                            bytes(payload), tuple(packets))
        self.next_ticket += 1
        self.transfers[batch.ticket] = batch
        return batch

    def acknowledge(self, batch, success=True):
        """Release transfer memory; publish only verified/current completed writes."""
        if (not isinstance(batch, UploadBatch)
                or self.transfers.get(batch.ticket) is not batch):
            raise ValueError('Unknown, forged or previously completed upload batch')
        if type(success) is not bool:
            raise ValueError('Completion result must be boolean')
        del self.transfers[batch.ticket]
        outcomes = []
        for packet in batch.packets:
            slot = packet.handle.slot
            self.busy_slots.remove(slot)
            self.held_bytes -= _weight(packet)
            if self.slots.reset_pending or batch.scene_epoch != self.slots.scene_epoch:
                outcomes.append('CANCELLED_RESET')
            elif not self._current(packet):
                outcomes.append('STALE')
            elif not success or self.slots.slot_refs[slot]:
                # A new queued revision wins; an old transfer must never roll it back.
                if slot not in self.pending:
                    self.enqueue(packet)
                outcomes.append('RETRY')
            else:
                outcomes.append(self.slots.publish(packet))
        return tuple(outcomes)

    def begin_reset(self):
        """Freeze new work, discard queued snapshots and retain active transfer memory."""
        self.slots.begin_reset()
        for slot in tuple(self.pending):
            self._remove_pending(slot)

    def complete_reset(self):
        """Require transfer completion and old draw-frame retirement before reset."""
        if self.transfers:
            raise RuntimeError('Outstanding uploads must complete before resetting scene')
        self.slots.complete_reset()
        if self.pending or self.busy_slots or self.held_bytes:
            raise AssertionError('Old scene staging resources not released')

    def pending_count(self):
        """Report retained queued snapshots only; outstanding transfers are separate."""
        return len(self.pending)

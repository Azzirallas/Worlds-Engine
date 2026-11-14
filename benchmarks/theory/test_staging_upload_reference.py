"""Hardware-independent staging, epoch, packet coalescing and budget tests."""

import random
import unittest

from inflight_slot_reference import CapacityError, FrameSlots
from staging_upload_reference import HEADER_BYTES, StagingUploads
from gpu_slot_packet_abi import FLAG_TOMBSTONE, SlotPacket


class StagingTests(unittest.TestCase):
    """Validate immutable upload snapshots and explicit completion protocols."""

    def setUp(self):
        """Prepare a deterministic bounded CPU-only upload queue."""
        self.slots = FrameSlots(max_slots=128, max_inflight=6)
        self.queue = StagingUploads(self.slots, max_staging_bytes=1024,
                                    max_batch_bytes=256, max_packets=20, max_batches=3)

    def _create(self, payload=b'hello'):
        """Create a CPU record and queue its versioned payload."""
        packet = self.slots.create(payload)
        self.assertEqual(self.queue.enqueue(packet), 'QUEUED')
        return packet

    def test_initial_upload_unblocks_draw_only_after_ack(self):
        """Staged but incomplete uploads never authorize fast-path drawing."""
        packet = self._create()
        batch = self.queue.prepare()
        self.assertEqual(self.slots.submit([packet.handle]).reason, 'upload_pending')
        self.assertEqual(batch.descriptors[0], SlotPacket(0, 1, 1, 1, 0, 5))
        self.assertEqual(batch.staging, b'hello')
        self.assertEqual(self.queue.acknowledge(batch), ('APPLIED',))
        self.assertTrue(self.slots.submit([packet.handle]).accepted)
        self.assertEqual(self.queue.held_bytes, 0)

    def test_staging_is_immutable_snapshot(self):
        """A submitted transfer's payload cannot be changed by later CPU writes."""
        first = self._create(b'a' * 17)
        batch = self.queue.prepare()
        self.assertEqual(len(batch.staging), 17)
        later = self.slots.update(first.handle, b'b' * 17)
        self.assertEqual(self.queue.enqueue(later), 'QUEUED')
        self.assertEqual(batch.staging, b'a' * 17)
        self.assertEqual(self.queue.acknowledge(batch), ('STALE',))
        second = self.queue.prepare()
        self.assertEqual(second.staging, b'b' * 17)
        self.assertEqual(self.queue.acknowledge(second), ('APPLIED',))
        self.assertEqual(self.slots.gpu[0], b'b' * 17)

    def test_two_packets_align_offsets_and_total_bytes(self):
        """Each descriptor locates a non-overlapping, aligned immutable payload."""
        self._create(b'A' * 17)
        self._create(b'B' * 4)
        batch = self.queue.prepare()
        self.assertEqual([d.offset for d in batch.descriptors], [0, 32])
        self.assertEqual([d.length for d in batch.descriptors], [17, 4])
        self.assertEqual(batch.staging[17:32], b'\0' * 15)
        self.assertEqual(batch.staging[32:36], b'BBBB')
        self.assertLessEqual(batch.charged_bytes, 256)
        self.assertEqual(self.queue.acknowledge(batch), ('APPLIED', 'APPLIED'))

    def test_budget_keeps_overflow_pending(self):
        """Per-batch work budget never returns a partial transfer packet."""
        q = StagingUploads(self.slots, max_staging_bytes=512, max_batch_bytes=64)
        packets = [self.slots.create(bytes([i]) * 16) for i in range(3)]
        for p in packets:
            q.enqueue(p)
        one = q.prepare()
        self.assertEqual(len(one.packets), 1)
        self.assertEqual(q.pending_count(), 2)
        q.acknowledge(one)
        two = q.prepare()
        self.assertEqual(len(two.packets), 1)
        q.acknowledge(two)
        three = q.prepare()
        self.assertEqual(len(three.packets), 1)
        q.acknowledge(three)
        self.assertEqual(q.held_bytes, 0)

    def test_capacity_rejection_is_atomic(self):
        """No allocator accounting or pending state changes after rejected writes."""
        p = self._create(b'a' * 16)
        before = (self.queue.held_bytes, list(self.queue.pending.items()))
        with self.assertRaises(CapacityError):
            self.queue.enqueue(self.slots.update(p.handle, b'b' * 240))
        self.assertEqual((self.queue.held_bytes, list(self.queue.pending.items())), before)
        self.assertEqual(self.queue.prepare(), None)  # queued old packet became stale
        self.assertEqual(self.queue.held_bytes, 0)

    def test_old_versions_coalesce_and_are_rejected(self):
        """Only the latest version of a slot occupies the pending queue."""
        first = self._create(b'1')
        p2 = self.slots.update(first.handle, b'2')
        self.assertEqual(self.queue.enqueue(first), 'STALE')
        self.assertEqual(self.queue.enqueue(p2), 'QUEUED')
        self.assertEqual(self.queue.enqueue(p2), 'DUPLICATE')
        self.assertEqual(self.queue.pending_count(), 1)
        batch = self.queue.prepare()
        self.assertEqual(batch.packets, (p2,))
        self.assertEqual(self.queue.acknowledge(batch), ('APPLIED',))

    def test_existing_draw_frame_blocks_preparation(self):
        """Do not upload over storage still sampled by outstanding draw frames."""
        p = self._create(b'old')
        self.queue.acknowledge(self.queue.prepare())
        draw = self.slots.submit([p.handle])
        next_packet = self.slots.update(p.handle, b'new')
        self.queue.enqueue(next_packet)
        self.assertIsNone(self.queue.prepare())
        self.slots.retire(draw.frame)
        self.assertEqual(self.queue.acknowledge(self.queue.prepare()), ('APPLIED',))

    def test_transfer_failure_retries_latest(self):
        """Failed transfers return immutable snapshots to the queue for retry."""
        p = self._create(b'tree')
        batch = self.queue.prepare()
        self.assertEqual(self.queue.acknowledge(batch, success=False), ('RETRY',))
        self.assertEqual(self.queue.pending_count(), 1)
        self.assertEqual(self.queue.held_bytes, HEADER_BYTES + 16)
        self.assertEqual(self.queue.acknowledge(self.queue.prepare()), ('APPLIED',))
        self.assertTrue(self.slots.submit([p.handle]).accepted)

    def test_new_revision_wins_over_failed_old_transfer(self):
        """A failed old packet cannot displace a newer queued revision."""
        p = self._create(b'a')
        old = self.queue.prepare()
        newest = self.slots.update(p.handle, b'b')
        self.queue.enqueue(newest)
        self.assertEqual(self.queue.acknowledge(old, success=False), ('STALE',))
        self.assertEqual(self.queue.acknowledge(self.queue.prepare()), ('APPLIED',))
        self.assertEqual(self.slots.gpu[0], b'b')

    def test_invalid_and_duplicate_ack_rejected(self):
        """Forged and already completed transfer tickets cannot mutate the GPU mirror."""
        self._create()
        batch = self.queue.prepare()
        with self.assertRaises(ValueError):
            self.queue.acknowledge(batch, success=1)
        from dataclasses import replace
        with self.assertRaises(ValueError):
            self.queue.acknowledge(replace(batch))
        self.assertEqual(self.queue.acknowledge(batch), ('APPLIED',))
        with self.assertRaises(ValueError):
            self.queue.acknowledge(batch)

    def test_tombstone_does_not_recycle_until_completed(self):
        """Deleted presentation slots remain quarantined until tombstone upload ack."""
        p = self._create()
        self.queue.acknowledge(self.queue.prepare())
        tomb = self.slots.delete(p.handle)
        self.assertEqual(self.queue.enqueue(tomb), 'QUEUED')
        batch = self.queue.prepare()
        self.assertEqual(batch.descriptors[0].flags, FLAG_TOMBSTONE)
        self.assertEqual(self.slots.free, [])
        self.assertEqual(self.queue.acknowledge(batch), ('APPLIED',))
        self.assertEqual(self.slots.free, [0])

    def test_reset_discard_pending_and_drain_transfers(self):
        """Reset must not release staging memory owned by an in-flight transfer."""
        one = self._create(b'a')
        old = self.queue.prepare()
        latest = self.slots.update(one.handle, b'b')
        self.queue.enqueue(latest)
        held = self.queue.held_bytes
        self.queue.begin_reset()
        self.assertLess(self.queue.held_bytes, held)
        self.assertEqual(self.queue.enqueue(latest), 'RESET_PENDING')
        self.assertIsNone(self.queue.prepare())
        with self.assertRaises(RuntimeError):
            self.queue.complete_reset()
        self.assertEqual(self.queue.acknowledge(old), ('CANCELLED_RESET',))
        self.queue.complete_reset()
        self.assertEqual(self.slots.scene_epoch, 2)
        self.assertEqual(self.queue.held_bytes, 0)
        self.assertEqual(self.queue.enqueue(one), 'STALE')
        fresh = self._create(b'c')
        self.assertEqual(fresh.handle.slot, one.handle.slot)
        self.assertNotEqual(fresh.handle.scene_epoch, one.handle.scene_epoch)

    def test_reset_waits_for_draw_frame_and_transfer(self):
        """Scene reset gates on both old draw tickets and transfer tickets."""
        p = self._create(b'v1')
        self.queue.acknowledge(self.queue.prepare())
        frame = self.slots.submit([p.handle])
        next_packet = self.slots.update(p.handle, b'v2')
        self.queue.enqueue(next_packet)
        self.queue.begin_reset()
        with self.assertRaises(RuntimeError):
            self.queue.complete_reset()
        self.slots.retire(frame.frame)
        self.queue.complete_reset()

    def test_packet_count_and_memory_cap(self):
        """Fail closed rather than dropping some transforms under upload pressure."""
        q = StagingUploads(self.slots, max_staging_bytes=96, max_batch_bytes=96,
                           max_packets=1)
        a = self.slots.create(b'x' * 16)
        b = self.slots.create(b'y' * 16)
        q.enqueue(a)
        with self.assertRaises(CapacityError):
            q.enqueue(b)
        self.assertEqual(q.pending_count(), 1)
        self.assertEqual(q.held_bytes, 48)
        with self.assertRaises(ValueError):
            q.enqueue(None)
        with self.assertRaises(ValueError):
            StagingUploads(self.slots, max_batch_bytes=8192, max_staging_bytes=128)

    def test_inflight_batch_count_limits(self):
        """A limited number of pending uploads cannot be over-committed."""
        q = StagingUploads(self.slots, max_staging_bytes=512,
                           max_batch_bytes=64, max_batches=1)
        for v in (b'a', b'b'):
            q.enqueue(self.slots.create(v))
        first = q.prepare()
        self.assertIsNone(q.prepare())
        q.acknowledge(first)
        self.assertIsNotNone(q.prepare())

    def test_delete_during_inflight_transfer_keeps_new_tombstone(self):
        """A late old-data ack cannot overwrite an already deleted slot."""
        p = self._create(b'former')
        old = self.queue.prepare()
        tomb = self.slots.delete(p.handle)
        self.assertEqual(self.queue.enqueue(tomb), 'QUEUED')
        self.assertEqual(self.queue.acknowledge(old), ('STALE',))
        transfer = self.queue.prepare()
        self.assertEqual(transfer.descriptors[0].scene_epoch, p.handle.scene_epoch)
        self.assertEqual(transfer.descriptors[0].flags, FLAG_TOMBSTONE)
        self.assertEqual(self.queue.acknowledge(transfer), ('APPLIED',))
        self.assertIsNone(self.slots.gpu[p.handle.slot])
        self.assertIn(p.handle.slot, self.slots.free)

    def test_blocked_slot_does_not_starve_independent_upload(self):
        """An in-flight draw on one slot does not block unrelated uploads."""
        first = self._create(b'first')
        self.queue.acknowledge(self.queue.prepare())
        frame = self.slots.submit([first.handle])
        update = self.slots.update(first.handle, b'updated')
        self.queue.enqueue(update)
        second = self._create(b'other')
        batch = self.queue.prepare()
        self.assertEqual(batch.packets, (second,))
        self.assertEqual(self.queue.acknowledge(batch), ('APPLIED',))
        self.slots.retire(frame.frame)
        self.assertEqual(self.queue.acknowledge(self.queue.prepare()), ('APPLIED',))

    def test_reject_mutable_and_empty_live_payload(self):
        """Only real immutable nonempty bytes can become a live staging upload."""
        for value in (bytearray(b'x'), b'', ['not bytes']):
            p = self.slots.create(value)
            with self.assertRaises(ValueError):
                self.queue.enqueue(p)
        # A forged payload cannot match the authoritative source record.
        from inflight_slot_reference import Packet
        p = self.slots.create(b'valid')
        forged = Packet(p.handle, p.revision, b'forged')
        self.assertEqual(self.queue.enqueue(forged), 'STALE')

    def test_seeded_staging_interleavings(self):
        """Test 800 operations with independent memory and slot-ref accounting."""
        rng = random.Random(28170)
        live, batches, frames = [], [], []
        for i in range(800):
            action = rng.randrange(7)
            if action == 0 and len(live) < 25:
                try:
                    packet = self.slots.create(bytes([i % 251]) * rng.randrange(1, 80))
                    live.append(packet.handle)
                    self.queue.enqueue(packet)
                except CapacityError:
                    pass
            elif action == 1 and live:
                h = rng.choice(live)
                packet = self.slots.update(h, bytes([i % 251]) * rng.randrange(1, 80))
                try:
                    self.queue.enqueue(packet)
                except CapacityError:
                    pass
            elif action == 2 and live:
                h = live.pop(rng.randrange(len(live)))
                packet = self.slots.delete(h)
                try:
                    self.queue.enqueue(packet)
                except CapacityError:
                    pass
            elif action == 3:
                batch = self.queue.prepare()
                if batch:
                    batches.append(batch)
            elif action == 4 and batches:
                batch = batches.pop(rng.randrange(len(batches)))
                self.queue.acknowledge(batch, success=rng.randrange(4) != 0)
            elif action == 5:
                subset = rng.sample(live, min(len(live), rng.randrange(4)))
                result = self.slots.submit(subset)
                if result.accepted:
                    frames.append(result.frame)
            elif frames:
                self.slots.retire(frames.pop(rng.randrange(len(frames))))
            expected = sum(HEADER_BYTES + ((len(p.value or b'') + 15) // 16) * 16
                           for p in self.queue.pending.values())
            expected += sum(batch.charged_bytes for batch in self.queue.transfers.values())
            self.assertEqual(self.queue.held_bytes, expected)
            self.assertLessEqual(expected, self.queue.max_staging_bytes)
            expected_refs = [0] * len(self.slots.slot_refs)
            for handles in self.slots.inflight.values():
                for h in handles:
                    expected_refs[h.slot] += 1
            self.assertEqual(self.slots.slot_refs, expected_refs)
        for batch in batches:
            self.queue.acknowledge(batch)
        for frame in frames:
            self.slots.retire(frame)


if __name__ == '__main__':
    unittest.main()

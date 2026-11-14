"""Hardware-free adversarial tests for frame-safe presentation slot updates."""

import random
import unittest

from inflight_slot_reference import CapacityError, FrameSlots, Handle, Packet


class FrameSlotTests(unittest.TestCase):
    """Test fences, generations, writes, fallback, and slot quarantine."""

    def test_create_requires_initial_publish(self):
        """Fresh CPU objects cannot enter experimental GPU path until uploaded."""
        state = FrameSlots()
        p = state.create(("mesh", 1))
        self.assertFalse(state.submit([p.handle]).accepted)
        self.assertEqual(state.publish(p), "APPLIED")
        frame = state.submit([p.handle])
        self.assertTrue(frame.accepted)
        state.retire(frame.frame)
        self.assertTrue(state.quiescent())

    def test_published_packet_cannot_mutate_inflight_slot(self):
        """An old GPU read prevents overwriting live table storage."""
        state = FrameSlots()
        p = state.create(("x", 0))
        state.publish(p)
        frame = state.submit([p.handle])
        next_packet = state.update(p.handle, ("x", 1))
        self.assertEqual(state.publish(next_packet), "DEFERRED")
        self.assertEqual(state.gpu[p.handle.slot], ("x", 0))
        self.assertFalse(state.submit([p.handle]).accepted)
        state.retire(frame.frame)
        self.assertEqual(state.gpu[p.handle.slot], ("x", 1))
        self.assertTrue(state.submit([p.handle]).accepted)

    def test_delete_quarantines_slot_until_frame_and_tombstone(self):
        """A deleted instance is not silently reused by a frame still reading it."""
        state = FrameSlots()
        first = state.create("old")
        state.publish(first)
        old_frame = state.submit([first.handle])
        tomb = state.delete(first.handle)
        self.assertFalse(state.submit([first.handle]).accepted)
        self.assertEqual(state.publish(tomb), "DEFERRED")
        new = state.create("different")
        self.assertNotEqual(first.handle.slot, new.handle.slot)
        state.retire(old_frame.frame)
        self.assertIn(first.handle.slot, state.free)
        reuse = state.create("reused")
        self.assertEqual(reuse.handle.slot, first.handle.slot)
        self.assertGreater(reuse.handle.generation, first.handle.generation)
        self.assertEqual(state.publish(first), "STALE")
        self.assertEqual(state.publish(tomb), "STALE")

    def test_tombstone_not_published_blocks_reuse(self):
        """A free physical slot requires both a completion and a deletion write."""
        state = FrameSlots(max_slots=1)
        p = state.create("one")
        state.publish(p)
        frame = state.submit([p.handle])
        tomb = state.delete(p.handle)
        state.retire(frame.frame)
        with self.assertRaises(CapacityError):
            state.create("two")
        self.assertEqual(state.publish(tomb), "APPLIED")
        reused = state.create("two")
        self.assertEqual(reused.handle.slot, p.handle.slot)

    def test_out_of_order_fence_completion(self):
        """The last in-flight reference, not the first completed ticket, releases it."""
        state = FrameSlots(max_inflight=3, max_slots=2)
        p = state.create("one")
        state.publish(p)
        first = state.submit([p.handle])
        second = state.submit([p.handle])
        tomb = state.delete(p.handle)
        self.assertEqual(state.publish(tomb), "DEFERRED")
        state.retire(second.frame)
        self.assertNotIn(p.handle.slot, state.free)
        with self.assertRaises(CapacityError):
            state_two = FrameSlots(max_slots=0)
            state_two.create("fail")
        state.retire(first.frame)
        self.assertIn(p.handle.slot, state.free)

    def test_out_of_order_uploads_only_latest_accepted(self):
        """Late packets cannot revert an already newer transform."""
        state = FrameSlots()
        p = state.create(("position", 0))
        state.publish(p)
        v2 = state.update(p.handle, ("position", 2))
        v3 = state.update(p.handle, ("position", 3))
        self.assertEqual(state.publish(v2), "STALE")
        self.assertEqual(state.publish(v3), "APPLIED")
        self.assertEqual(state.publish(v2), "STALE")
        self.assertEqual(state.publish(v3), "DUPLICATE")
        self.assertEqual(state.gpu[p.handle.slot], ("position", 3))

    def test_deferred_packet_superseded_before_retirement(self):
        """A deferred old revision must not publish after newer CPU work."""
        state = FrameSlots()
        p = state.create(1)
        state.publish(p)
        frame = state.submit([p.handle])
        v2 = state.update(p.handle, 2)
        self.assertEqual(state.publish(v2), "DEFERRED")
        v3 = state.update(p.handle, 3)
        state.retire(frame.frame)
        self.assertEqual(state.gpu[p.handle.slot], 1)
        self.assertFalse(state.submit([p.handle]).accepted)
        self.assertEqual(state.publish(v3), "APPLIED")
        self.assertEqual(state.gpu[p.handle.slot], 3)

    def test_deletion_invalidates_queued_update(self):
        """A deleted generation's transform must never land after the tombstone."""
        state = FrameSlots()
        p = state.create("a")
        state.publish(p)
        frame = state.submit([p.handle])
        update = state.update(p.handle, "b")
        self.assertEqual(state.publish(update), "DEFERRED")
        tomb = state.delete(p.handle)
        self.assertEqual(state.publish(update), "STALE")
        self.assertEqual(state.publish(tomb), "DEFERRED")
        state.retire(frame.frame)
        self.assertEqual(state.gpu[p.handle.slot], None)
        self.assertEqual(state.publish(update), "STALE")

    def test_two_camera_frames_reference_same_slot(self):
        """Shared geometry is protected until every view's GPU frame completes."""
        state = FrameSlots()
        p = state.create(("tree", 7))
        state.publish(p)
        camera_a = state.submit([p.handle])
        camera_b = state.submit([p.handle])
        update = state.update(p.handle, ("tree", 8))
        self.assertEqual(state.publish(update), "DEFERRED")
        state.retire(camera_a.frame)
        self.assertEqual(state.gpu[p.handle.slot], ("tree", 7))
        state.retire(camera_b.frame)
        self.assertEqual(state.gpu[p.handle.slot], ("tree", 8))

    def test_rejected_frames_use_conventional_fallback(self):
        """No capacity/identity/dirty condition is reported as a valid fast path."""
        state = FrameSlots(max_slots=1, max_inflight=1)
        p = state.create("a")
        self.assertEqual(state.submit([p.handle]).reason, "upload_pending")
        state.publish(p)
        self.assertEqual(state.submit([p.handle, p.handle]).reason, "duplicate_handle")
        first = state.submit([p.handle])
        self.assertTrue(first.accepted)
        self.assertEqual(state.submit([p.handle]).reason, "inflight_budget")
        state.retire(first.frame)
        with self.assertRaises(ValueError):
            state.retire(first.frame)
        state.delete(p.handle)
        self.assertEqual(state.submit([p.handle]).reason, "stale_handle")

    def test_external_mutation_does_not_modify_published_packet(self):
        """Value snapshots are immune to later modifications of caller-owned lists."""
        state = FrameSlots()
        data = ["material", [3, 4]]
        p = state.create(data)
        data[1][0] = 99
        self.assertEqual(p.value[1][0], 3)
        state.publish(p)
        data[1][1] = 88
        self.assertEqual(state.gpu[p.handle.slot][1], [3, 4])

    def test_no_reuse_when_all_slots_in_flight(self):
        """A bounded table reports pressure, rather than recycling unsafe storage."""
        state = FrameSlots(max_slots=1)
        p = state.create("one")
        state.publish(p)
        frame = state.submit([p.handle])
        tomb = state.delete(p.handle)
        with self.assertRaises(CapacityError):
            state.create("second")
        state.publish(tomb)
        state.retire(frame.frame)
        two = state.create("second")
        self.assertEqual(two.handle.slot, p.handle.slot)

    def test_empty_frame_and_bad_inputs(self):
        """Empty submission may retire; invalid requests and packets fail explicitly."""
        state = FrameSlots()
        e = state.submit(())
        self.assertTrue(e.accepted)
        state.retire(e.frame)
        self.assertTrue(state.quiescent())
        for fn in (lambda: FrameSlots(max_slots=-1), lambda: FrameSlots(max_inflight=0),
                   lambda: state.create(None), lambda: state.publish(None),
                   lambda: state.update(Handle(400, 1), "missing")):
            with self.assertRaises(ValueError):
                fn()
        p = state.create("payload")
        self.assertEqual(state.publish(Packet(p.handle, p.revision, "forged")), "STALE")

    def test_seeded_interleaving_never_exposes_old_generation(self):
        """Exercise random submit/update/delete/publish/retire interleavings."""
        rng = random.Random(20019)
        state = FrameSlots(max_slots=90, max_inflight=5)
        live = []
        flights = []
        for _ in range(1000):
            action = rng.randrange(5)
            if action == 0 and len(live) < 65:
                try:
                    p = state.create(("new", rng.randrange(1000)))
                except CapacityError:
                    continue
                live.append(p.handle)
                if rng.randrange(2):
                    state.publish(p)
            elif action == 1 and live:
                h = rng.choice(live)
                p = state.update(h, ("moved", rng.randrange(1000)))
                if rng.randrange(4):
                    state.publish(p)
            elif action == 2 and live:
                h = live.pop(rng.randrange(len(live)))
                tomb = state.delete(h)
                if rng.randrange(3):
                    state.publish(tomb)
            elif action == 3:
                s = state.submit(rng.sample(live, min(len(live), rng.randrange(0, 5))))
                if s.accepted:
                    flights.append(s.frame)
            elif flights:
                f = flights.pop(rng.randrange(len(flights)))
                state.retire(f)
            # Every current GPU slot must either be current or protected by references.
            for h in live:
                slot = h.slot
                if state.gpu[slot] != state.cpu[slot]:
                    self.assertTrue(state.published[slot] != state.revision[slot]
                                    or state._referenced(slot))
        for frame in flights:
            state.retire(frame)
        for h in live:
            # Ensure no negative generation or stale GPU reuse.
            self.assertEqual(state.generation[h.slot], h.generation)


if __name__ == "__main__":
    unittest.main()

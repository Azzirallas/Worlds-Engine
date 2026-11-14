"""CPU-only scene reset, epoch ABA, and in-flight draining tests."""

import random
import unittest

from inflight_slot_reference import CapacityError, FrameSlots, Handle, Packet, UINT32_MAX


class SceneResetTests(unittest.TestCase):
    """Prove a restarted scene cannot accept old GPU identities or packets."""

    def test_aba_recycled_slot_and_generation_rejected_across_scene(self):
        """Epoch distinguishes otherwise identical slot/generation pairs."""
        s = FrameSlots(max_slots=1)
        old = s.create("old")
        self.assertEqual(s.publish(old), "APPLIED")
        s.begin_reset()
        s.complete_reset()
        fresh = s.create("new")
        self.assertEqual((old.handle.slot, old.handle.generation),
                         (fresh.handle.slot, fresh.handle.generation))
        self.assertNotEqual(old.handle.scene_epoch, fresh.handle.scene_epoch)
        self.assertEqual(s.publish(old), "STALE")
        self.assertEqual(s.submit([old.handle]).reason, "stale_handle")
        with self.assertRaises(ValueError):
            s.update(old.handle, "malicious old transform")
        self.assertEqual(s.publish(fresh), "APPLIED")
        self.assertTrue(s.submit([fresh.handle]).accepted)

    def test_two_phase_reset_holds_old_gpu_records(self):
        """Old buffer lifetime survives reset requests until all frames retire."""
        s = FrameSlots(max_inflight=4)
        old = s.create("tree")
        s.publish(old)
        a = s.submit([old.handle])
        b = s.submit([old.handle])
        s.begin_reset()
        self.assertEqual(s.slot_refs, [2])
        self.assertEqual(s.gpu[0], "tree")
        self.assertEqual(s.submit([old.handle]).reason, "reset_pending")
        self.assertEqual(s.publish(old), "RESET_PENDING")
        for callback in (lambda: s.create("new"), lambda: s.update(old.handle, "x"),
                         lambda: s.delete(old.handle), s.complete_reset):
            with self.assertRaises(RuntimeError):
                callback()
        s.retire(b.frame)
        self.assertEqual(s.slot_refs, [1])
        with self.assertRaises(RuntimeError):
            s.complete_reset()
        s.retire(a.frame)
        self.assertEqual(s.slot_refs, [0])
        s.complete_reset()
        self.assertEqual(s.scene_epoch, 2)
        self.assertEqual(s.cpu, [])
        self.assertEqual(s.gpu, [])
        self.assertTrue(s.quiescent())

    def test_stale_deferred_packets_cannot_publish_on_reset(self):
        """Reset drops pending writes without touching in-flight GPU snapshots."""
        s = FrameSlots()
        initial = s.create(11)
        s.publish(initial)
        frame = s.submit([initial.handle])
        later = s.update(initial.handle, 12)
        self.assertEqual(s.publish(later), "DEFERRED")
        s.begin_reset()
        self.assertEqual(s.deferred, {})
        s.retire(frame.frame)
        self.assertEqual(s.gpu[initial.handle.slot], 11)
        s.complete_reset()
        self.assertEqual(s.publish(later), "STALE")

    def test_unpublished_tombstone_can_be_discarded_by_whole_scene_reset(self):
        """Quiescent whole-device reset retires the old slot storage itself."""
        s = FrameSlots(max_slots=1)
        p = s.create("one")
        s.publish(p)
        tomb = s.delete(p.handle)
        self.assertFalse(s.quiescent())
        s.begin_reset()
        self.assertEqual(s.publish(tomb), "RESET_PENDING")
        s.complete_reset()
        next_packet = s.create("two")
        self.assertEqual(next_packet.handle, Handle(0, 1, 2))
        self.assertEqual(s.publish(tomb), "STALE")

    def test_terminal_generation_slot_can_restart_only_in_new_epoch(self):
        """Epoch rollover is a controlled reset, not same-epoch generation wrap."""
        s = FrameSlots(max_slots=1, max_generation=2)
        p = s.create("one")
        s.publish(p)
        final = s.delete(p.handle)
        s.publish(final)
        with self.assertRaises(CapacityError):
            s.create("no same-epoch reuse")
        s.begin_reset()
        s.complete_reset()
        new = s.create("new scene")
        self.assertEqual(new.handle, Handle(0, 1, 2))

    def test_epoch_exhaustion_refuses_before_invalidating_live_scene(self):
        """Stop before scene epochs wrap and old scene identities recur."""
        s = FrameSlots(scene_epoch=2, max_scene_epoch=2)
        p = s.create("still valid")
        s.publish(p)
        with self.assertRaises(CapacityError):
            s.begin_reset()
        self.assertFalse(s.reset_pending)
        self.assertTrue(s.submit([p.handle]).accepted)

    def test_repeated_or_misordered_reset_calls_fail_closed(self):
        """Require a single explicit two-phase transition."""
        s = FrameSlots()
        with self.assertRaises(RuntimeError):
            s.complete_reset()
        s.begin_reset()
        with self.assertRaises(RuntimeError):
            s.begin_reset()
        self.assertFalse(s.quiescent())
        s.complete_reset()
        self.assertEqual(s.scene_epoch, 2)
        self.assertTrue(s.quiescent())

    def test_old_frame_tickets_not_reused_after_reset(self):
        """A late old completion must never retire a new scene's frame."""
        s = FrameSlots()
        old = s.create("one")
        s.publish(old)
        completed = s.submit([old.handle])
        s.retire(completed.frame)
        s.begin_reset()
        s.complete_reset()
        new = s.create("two")
        s.publish(new)
        active = s.submit([new.handle])
        self.assertGreater(active.frame, completed.frame)
        with self.assertRaises(ValueError):
            s.retire(completed.frame)
        self.assertEqual(s.slot_refs, [1])
        s.retire(active.frame)

    def test_empty_inflight_ticket_still_blocks_reset(self):
        """Even an empty submitted frame must complete before state replacement."""
        s = FrameSlots()
        ticket = s.submit([])
        s.begin_reset()
        with self.assertRaises(RuntimeError):
            s.complete_reset()
        s.retire(ticket.frame)
        s.complete_reset()

    def test_scene_epoch_initialization_validation(self):
        """Zero, bool and out-of-range epoch values are invalid."""
        for kwargs in ({"scene_epoch": 0}, {"scene_epoch": UINT32_MAX + 1},
                       {"max_scene_epoch": 0}, {"max_scene_epoch": True},
                       {"scene_epoch": 3, "max_scene_epoch": 2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                FrameSlots(**kwargs)

    def test_24_scene_resets_never_accept_old_packets(self):
        """Keep stale packets through many resets, even when new slots look identical."""
        s = FrameSlots(max_scene_epoch=25)
        old = []
        for epoch in range(1, 25):
            p = s.create({"scene": epoch})
            s.publish(p)
            for prior in old:
                self.assertEqual(s.publish(prior), "STALE")
                self.assertEqual(s.submit([prior.handle]).reason, "stale_handle")
            old.append(p)
            s.begin_reset()
            s.complete_reset()
        self.assertEqual(s.scene_epoch, 25)
        with self.assertRaises(CapacityError):
            s.begin_reset()

    def test_random_interleaved_reset_and_frame_completion(self):
        """Seeded mixed edits, resets and out-of-order retirements preserve invariants."""
        rng = random.Random(198307)
        s = FrameSlots(max_slots=20, max_inflight=5, max_scene_epoch=100)
        live, frames, prior = [], [], []
        for _ in range(1300):
            action = rng.randrange(8)
            if s.reset_pending:
                if frames:
                    ticket = frames.pop(rng.randrange(len(frames)))
                    s.retire(ticket)
                else:
                    s.complete_reset()
                    live = []
            elif action == 0 and len(live) < 18:
                try:
                    p = s.create(rng.randrange(999))
                except CapacityError:
                    continue
                s.publish(p)
                live.append(p.handle)
                prior.append(p)
            elif action == 1 and live:
                h = rng.choice(live)
                p = s.update(h, rng.randrange(999))
                if rng.randrange(2):
                    s.publish(p)
            elif action == 2 and live:
                h = live.pop(rng.randrange(len(live)))
                p = s.delete(h)
                if rng.randrange(2):
                    s.publish(p)
            elif action == 3:
                subset = rng.sample(live, min(len(live), rng.randrange(4)))
                admission = s.submit(subset)
                if admission.accepted:
                    frames.append(admission.frame)
            elif action == 4 and frames:
                s.retire(frames.pop(rng.randrange(len(frames))))
            elif action == 5 and s.scene_epoch < s.max_scene_epoch:
                s.begin_reset()
            elif action == 6 and prior:
                p = rng.choice(prior)
                if p.handle.scene_epoch != s.scene_epoch:
                    self.assertEqual(s.publish(p), "STALE")
            expected = [0] * len(s.cpu)
            for handles in s.inflight.values():
                for h in handles:
                    expected[h.slot] += 1
            self.assertEqual(s.slot_refs, expected)
        for frame in frames:
            s.retire(frame)
        if s.reset_pending:
            s.complete_reset()
        self.assertFalse(s.reset_pending)


if __name__ == '__main__':
    unittest.main()

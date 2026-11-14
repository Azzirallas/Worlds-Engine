"""CPU-only per-slot reference-count and bounded integer tests."""

import random
import unittest

from inflight_slot_reference import CapacityError, FrameSlots, Handle, Packet, UINT32_MAX


class RefCountAndWrapTests(unittest.TestCase):
    """Compare count-backed references with the ticket-set truth."""

    def assert_counts_match(self, state):
        """Recalculate from submitted tickets without using cached counts."""
        expected = [0] * len(state.cpu)
        for handles in state.inflight.values():
            for h in handles:
                expected[h.slot] += 1
        self.assertEqual(state.slot_refs, expected)
        self.assertEqual([state._referenced(i) for i in range(len(expected))],
                         [n > 0 for n in expected])

    def test_counts_shared_between_three_views(self):
        """Multiple camera submissions increment once each and retire out of order."""
        s = FrameSlots(max_inflight=4)
        p = s.create('tree')
        self.assertEqual(s.publish(p), 'APPLIED')
        frames = [s.submit([p.handle]) for _ in range(3)]
        self.assertEqual(s.slot_refs, [3])
        s.retire(frames[1].frame)
        self.assertEqual(s.slot_refs, [2])
        s.retire(frames[0].frame)
        self.assertEqual(s.slot_refs, [1])
        s.retire(frames[2].frame)
        self.assertEqual(s.slot_refs, [0])
        self.assertTrue(s.quiescent())

    def test_rejected_submission_cannot_leak_counts(self):
        """A frame must be admitted atomically after all handles validate."""
        s = FrameSlots(max_inflight=1)
        p = s.create('ok')
        q = s.create('pending')
        s.publish(p)
        self.assertEqual(s.submit([p.handle, q.handle]).reason, 'upload_pending')
        self.assert_counts_match(s)
        self.assertEqual(s.slot_refs, [0, 0])
        self.assertEqual(s.submit([p.handle, p.handle]).reason, 'duplicate_handle')
        self.assertEqual(s.slot_refs, [0, 0])
        f = s.submit([p.handle])
        self.assertTrue(f.accepted)
        self.assertEqual(s.slot_refs, [1, 0])
        self.assertEqual(s.submit([]).reason, 'inflight_budget')
        self.assertEqual(s.slot_refs, [1, 0])
        s.retire(f.frame)
        self.assert_counts_match(s)

    def test_deleted_slot_releases_only_on_last_frame(self):
        """Terminal tombstones still have to wait for the last reference."""
        s = FrameSlots(max_generation=3, max_slots=1)
        one = s.create('old')
        s.publish(one)
        a = s.submit([one.handle])
        b = s.submit([one.handle])
        tomb = s.delete(one.handle)
        self.assertEqual(s.publish(tomb), 'DEFERRED')
        s.retire(b.frame)
        self.assertEqual(s.slot_refs, [1])
        self.assertEqual(s.free, [])
        s.retire(a.frame)
        self.assertEqual(s.slot_refs, [0])
        self.assertEqual(s.free, [0])
        two = s.create('again')
        s.publish(two)
        self.assertEqual(two.handle.generation, 2)
        final = s.delete(two.handle)
        self.assertEqual(final.handle.generation, 3)
        self.assertEqual(s.publish(final), 'APPLIED')
        self.assertEqual(s.free, [])
        self.assertTrue(s.quiescent())
        with self.assertRaises(CapacityError):
            s.create('must not reuse terminal generation')

    def test_revision_exhaustion_fails_before_mutation(self):
        """Never wrap an old revision into one that could pass an ABA check."""
        s = FrameSlots(max_revision=2)
        p = s.create('a')
        self.assertEqual(s.publish(p), 'APPLIED')
        v2 = s.update(p.handle, 'b')
        self.assertEqual(v2.revision, 2)
        with self.assertRaises(CapacityError):
            s.update(p.handle, 'c')
        self.assertEqual(s.cpu[0], 'b')
        self.assertEqual(s.revision[0], 2)
        self.assertEqual(s.publish(v2), 'APPLIED')
        s.delete(p.handle)

    def test_default_unsigned_limits_and_invalid_limits(self):
        """UInt32 is an explicit ABI policy, not Python's unlimited integers."""
        self.assertEqual(UINT32_MAX, 4294967295)
        s = FrameSlots()
        self.assertEqual(s.max_generation, UINT32_MAX)
        self.assertEqual(s.max_revision, UINT32_MAX)
        for kwargs in ({'max_slots': UINT32_MAX + 2}, {'max_generation': 1},
                       {'max_generation': UINT32_MAX + 1}, {'max_revision': 0},
                       {'max_revision': UINT32_MAX + 1}, {'max_revision': True},
                       {'max_inflight': False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                FrameSlots(**kwargs)

    def test_high_revision_boundary(self):
        """The maximum legal revision is published, then changes are rejected."""
        s = FrameSlots(max_revision=3)
        p = s.create('initial')
        s.publish(p)
        p2 = s.update(p.handle, 'b')
        p3 = s.update(p.handle, 'c')
        self.assertEqual(s.publish(p2), 'STALE')
        self.assertEqual(s.publish(p3), 'APPLIED')
        with self.assertRaises(CapacityError):
            s.update(p.handle, 'd')
        self.assertEqual(s.gpu[0], 'c')

    def test_many_random_interleavings_keep_exact_counts(self):
        """Recompute counters independently over 1,500 seeded mutations."""
        rng = random.Random(42017)
        s = FrameSlots(max_slots=64, max_inflight=8, max_generation=20, max_revision=20)
        live = []
        frames = []
        for _ in range(1500):
            action = rng.randrange(5)
            if action == 0:
                try:
                    p = s.create(('model', rng.randrange(10)))
                except CapacityError:
                    continue
                live.append(p.handle)
                if rng.randrange(2):
                    s.publish(p)
            elif action == 1 and live:
                h = rng.choice(live)
                try:
                    pkt = s.update(h, rng.randrange(20))
                except CapacityError:
                    continue
                if rng.randrange(2):
                    s.publish(pkt)
            elif action == 2 and live:
                h = live.pop(rng.randrange(len(live)))
                tomb = s.delete(h)
                if rng.randrange(2):
                    s.publish(tomb)
            elif action == 3:
                subset = rng.sample(live, min(len(live), rng.randrange(5)))
                result = s.submit(subset)
                if result.accepted:
                    frames.append(result.frame)
            elif frames:
                f = frames.pop(rng.randrange(len(frames)))
                s.retire(f)
            self.assert_counts_match(s)
        for f in frames:
            s.retire(f)
            self.assert_counts_match(s)

    def test_retire_duplicate_ticket_cannot_underflow(self):
        """Repeated completion reports must fail without altering reference counts."""
        s = FrameSlots()
        p = s.create('sample')
        s.publish(p)
        f = s.submit([p.handle])
        s.retire(f.frame)
        with self.assertRaises(ValueError):
            s.retire(f.frame)
        self.assertEqual(s.slot_refs[0], 0)


if __name__ == '__main__':
    unittest.main()

"""Safety, cost and fair replay tests for a regional-root / aggregate hybrid."""
import random
import unittest
from root_topology_reference import Config
from hybrid_topology_reference import HybridTopology, compare_three


class HybridTests(unittest.TestCase):
    """Assert fallback roots remain safe under optional proxy memory pressure."""

    def test_no_proxy_before_far_view(self):
        """Near focus starts at exactly the same coarse bytes as regional-only."""
        m = HybridTopology()
        self.assertEqual(m.resident_bytes, 32)
        self.assertFalse(m.proxy_resident)
        self.assertEqual(m.tick((0,)).draw_calls, 16)

    def test_far_eventually_uses_one_aggregate(self):
        """After delayed upload a distant view can replace 16 submissions with one."""
        m = HybridTopology()
        for _ in range(5):
            last = m.tick(())
        self.assertEqual(last.draw_calls, 1)
        self.assertEqual(m.stats().proxy_loads, 1)
        self.assertEqual(m.resident_bytes, 42)
        self.assertTrue(m.verify())

    def test_aggregate_extra_bytes_are_not_free(self):
        """Aggregate memory is counted beyond the ordinary regional root baseline."""
        m = HybridTopology(Config(resident_budget=41), proxy_bytes=10)
        for _ in range(10):
            self.assertEqual(m.tick(()).draw_calls, 16)
        self.assertEqual(m.upload_total, 0)
        self.assertEqual(m.resident_bytes, 32)

    def test_near_detail_matches_regional_without_global_siblings(self):
        """Near-fine pages need no unrelated coarse upload dependencies."""
        m = compare_three([(0,)] * 12, Config(resident_budget=70))
        self.assertEqual(m['hybrid'].reports[-1].selected_fine, (0,))
        self.assertEqual(m['regional'].reports[-1].selected_fine, (0,))
        self.assertNotEqual(m['global'].reports[-1].selected_fine, (0,))
        self.assertEqual(m['hybrid'].upload_total, 12)

    def test_inflight_proxy_not_evicted_by_near_transfer(self):
        """A submitted aggregate frame retains its bytes until its ticket retires."""
        c = Config(side=2, resident_budget=25, region_coarse_bytes=2,
                   fine_bytes=12, draw_latency=5)
        m = HybridTopology(c, proxy_bytes=10)
        for _ in range(4):
            m.tick(())
        self.assertTrue(m.proxy_resident)
        self.assertGreater(m.proxy_refs, 0)
        for _ in range(3):
            m.tick((0,))
        self.assertNotIn(0, m.fine_loaded)
        self.assertTrue(m.proxy_resident)
        for _ in range(8):
            m.tick((0,))
        self.assertIn(0, m.fine_loaded)
        self.assertFalse(m.proxy_resident)
        self.assertTrue(m.verify())

    def test_proxy_evicts_unneeded_fines_transactionally(self):
        """Far proxy can replace unused detail after prior draw holds expire."""
        c = Config(side=2, resident_budget=24, region_coarse_bytes=2, fine_bytes=12)
        m = HybridTopology(c, proxy_bytes=10)
        for _ in range(6):
            m.tick((0,))
        self.assertIn(0, m.fine_loaded)
        for _ in range(6):
            m.tick(())
        self.assertTrue(m.proxy_resident)
        self.assertNotIn(0, m.fine_loaded)
        self.assertGreater(m.evictions, 0)
        self.assertTrue(m.verify())

    def test_pending_far_transfer_is_cancelled_by_camera_cut(self):
        """A stale aggregate transfer cannot create a now-unwanted proxy."""
        m = HybridTopology(Config(transfer_latency=4))
        m.tick(())
        self.assertIn(('proxy', 0), m.pending)
        m.tick((0,))
        self.assertNotIn(('proxy', 0), m.pending)
        self.assertEqual(m.proxy_cancellations, 1)
        self.assertFalse(m.proxy_resident)

    def test_distant_proxy_impossible_upload_budget(self):
        """A whole page bigger than the upload tick cannot partially publish."""
        m = HybridTopology(Config(upload_budget=5), proxy_bytes=10)
        for _ in range(9):
            self.assertEqual(m.tick(()).draw_calls, 16)
        self.assertEqual(m.upload_total, 0)
        self.assertTrue(m.verify())

    def test_proxy_budget_failure_cannot_evacuate_detail(self):
        """Failed admission leaves existing visual detail unchanged."""
        c = Config(side=2, resident_budget=22, region_coarse_bytes=2, fine_bytes=12,
                   draw_latency=10)
        m = HybridTopology(c, proxy_bytes=10)
        for _ in range(5):
            m.tick((0,))
        self.assertTrue(m.held)
        for _ in range(3):
            m.tick(())
        self.assertFalse(m.proxy_resident)
        self.assertIn(0, m.fine_loaded)

    def test_invalid_proxy_size(self):
        """Reject malformed independent optional proxy sizes without side effects."""
        for val in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                HybridTopology(proxy_bytes=val)

    def test_identical_initial_root_budget(self):
        """All three policies preserve the same initial baseline coarse budget."""
        modes = compare_three([], Config(side=4))
        self.assertEqual({m.resident_bytes for m in modes.values()}, {32})

    def test_camera_movement_1200_tick_invariants(self):
        """Random focus cuts and long far views never break byte or ref accounting."""
        rng = random.Random(571701)
        c = Config(side=3, resident_budget=80, upload_budget=24, draw_latency=5)
        m = HybridTopology(c, proxy_bytes=10)
        for _ in range(1200):
            regions = tuple(rng.sample(range(c.region_count), rng.choice((0, 0, 0, 1, 2))))
            r = m.tick(regions)
            self.assertTrue(m.verify())
            self.assertLessEqual(r.resident_bytes, c.resident_budget)
            self.assertLessEqual(r.upload_bytes, c.upload_budget)
            self.assertEqual(r.fallback_regions, len(set(regions) - set(r.selected_fine)))
        self.assertGreater(m.proxy_loads, 0)
        self.assertGreater(m.proxy_frames_total, 0)


if __name__ == '__main__':
    unittest.main()

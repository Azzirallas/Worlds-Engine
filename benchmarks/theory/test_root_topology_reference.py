"""Independent CPU tests for coarse-root residency tradeoffs and safety."""
import random
import unittest
from root_topology_reference import Config, Topology, compare


class TopologyTests(unittest.TestCase):
    """Compare topology costs with identical base-detail geometry and byte budgets."""

    def test_equal_coarse_baseline(self):
        """Both topologies start with the same resident coarse geometry bytes."""
        c = Config(side=4)
        models = compare([()] * 8, c)
        self.assertEqual(models['regional'].resident_bytes, models['global'].resident_bytes)
        self.assertEqual(models['regional'].resident_bytes, c.coarse_bytes)

    def test_far_camera_favors_single_global_draw(self):
        """Far view is a single global proxy draw versus regional root draws."""
        models = compare([()] * 6)
        self.assertEqual(models['global'].reports[-1].draw_calls, 1)
        self.assertEqual(models['regional'].reports[-1].draw_calls, 16)
        self.assertEqual(models['global'].upload_total, 0)
        self.assertEqual(models['regional'].upload_total, 0)

    def test_regional_focus_refines_without_siblings(self):
        """A focused region does not require uploading sixteen sibling root pages."""
        c = Config(side=4, resident_budget=70, upload_budget=24)
        models = compare([(0,)] * 12, c)
        self.assertEqual(models['regional'].reports[-1].fallback_regions, 0)
        self.assertEqual(models['global'].reports[-1].fallback_regions, 1)
        self.assertEqual(models['regional'].upload_total, c.fine_bytes)
        self.assertEqual(models['global'].upload_total, c.coarse_bytes)
        self.assertLess(models['regional'].resident_bytes, models['global'].resident_bytes)

    def test_larger_budget_allows_global_upgrade_later(self):
        """Global hierarchy can reach full requested detail if memory permits."""
        models = compare([(0,)] * 12, Config(resident_budget=100))
        for name in models:
            self.assertEqual(models[name].reports[-1].fallback_regions, 0)
        self.assertGreater(models['global'].upload_total, models['regional'].upload_total)

    def test_global_return_to_far_view_reuses_single_root(self):
        """Resident children need not force global-root replacement at a far view."""
        m = Topology('global', Config(resident_budget=100))
        for _ in range(12):
            m.tick((0,))
        self.assertTrue(m.root_split)
        last = m.tick(())
        self.assertEqual(last.draw_calls, 1)
        self.assertEqual(last.fallback_regions, 0)

    def test_tight_resident_budget_preserves_full_coverage(self):
        """Permanent root coverage survives a page that never fits."""
        models = compare([(0,)] * 20, Config(resident_budget=33))
        for model in models.values():
            self.assertEqual(model.reports[-1].fallback_regions, 1)
            self.assertTrue(model.verify())
            self.assertLessEqual(model.resident_bytes, 33)

    def test_small_upload_budget_never_partially_issues_fine(self):
        """Whole-page transfers fail closed under insufficient per-tick bandwidth."""
        models = compare([(0,)] * 20, Config(upload_budget=3))
        self.assertEqual(models['regional'].upload_total, 0)
        self.assertEqual(models['global'].reports[-1].fallback_regions, 1)
        self.assertTrue(all(r.upload_bytes <= 3 for m in models.values() for r in m.reports))

    def test_capacity_recovery_evicts_old_detail_only_after_draws_retire(self):
        """Safe evictions allow new detail without recycling referenced geometry."""
        c = Config(side=2, resident_budget=20, region_coarse_bytes=2,
                   fine_bytes=12, draw_latency=2)
        m = Topology('regional', c)
        for _ in range(6):
            m.tick((0,))
        self.assertEqual(m.reports[-1].selected_fine, (0,))
        for _ in range(8):
            m.tick((1,))
        self.assertEqual(m.reports[-1].selected_fine, (1,))
        self.assertGreaterEqual(m.evictions, 1)
        self.assertTrue(m.verify())

    def test_invalid_inputs_rejected_without_state_mutation(self):
        """Invalid demands and impossible coarse budgets cannot corrupt state."""
        for kwargs in ({'side': 0}, {'resident_budget': 2}, {'upload_budget': 0}):
            with self.assertRaises(ValueError):
                Config(**kwargs)
        model = Topology('regional')
        with self.assertRaises(ValueError):
            model.tick((999,))
        self.assertEqual(model.clock, 0)

    def test_multiple_cameras_share_one_detail_page(self):
        """Merged demand has one page per region irrespective of camera count."""
        m = Topology('regional', Config())
        for _ in range(8):
            m.tick(set((0, 1)) | set((0,)))
        self.assertEqual(m.upload_total, 24)
        self.assertEqual(m.reports[-1].selected_fine, (0, 1))

    def test_1200_random_camera_changes_preserve_budget_and_references(self):
        """Random rapid focus switches retain exact byte and frame counts."""
        rng = random.Random(3417)
        c = Config(resident_budget=104, upload_budget=24)
        models = {'global': Topology('global', c), 'regional': Topology('regional', c)}
        for t in range(1200):
            targets = tuple(rng.sample(range(c.region_count), rng.randrange(4)))
            for model in models.values():
                report = model.tick(targets)
                self.assertTrue(model.verify())
                self.assertEqual(report.fallback_regions,
                                 len(set(targets) - set(report.selected_fine)))
                self.assertLessEqual(report.resident_bytes, c.resident_budget)
                self.assertLessEqual(report.upload_bytes, c.upload_budget)


if __name__ == '__main__':
    unittest.main()

"""Hardware-independent geometry error, LOD hysteresis and fallback tests."""

from dataclasses import replace
import random
import unittest
from geometry_lod_reference import Camera, Level, LODSelector
from geometry_async_reference import AsyncGeometry


class LODTests(unittest.TestCase):
    """Check conservative projection, hysteresis, and page residency coupling."""

    def setUp(self):
        """Create one strictly improving coarse -> medium -> fine representation."""
        self.lods = LODSelector([Level('root', None, 1.0),
                                 Level('medium', 'root', 0.2),
                                 Level('fine', 'medium', 0.01)])

    def cam(self, distance=100, radius=1):
        """Use a fixed projection for reproducible pixel-error comparisons."""
        return Camera(distance, radius, viewport_height=1000, perspective_fov_y_deg=60)

    def test_far_camera_prefers_coarse(self):
        """The coarsest adequate representation avoids wasteful fine submissions."""
        choice = self.lods.choose(self.cam(1000), 2, {'root','medium','fine'})
        self.assertEqual(choice.page, 'root')
        self.assertTrue(choice.within_budget)

    def test_close_camera_prefers_fine(self):
        """Error budget chooses finer representation under large projected error."""
        choice = self.lods.choose(self.cam(4), 2, {'root','medium','fine'})
        self.assertEqual(choice.page, 'fine')
        self.assertTrue(choice.within_budget is False)  # Even fine error can exceed 2px.

    def test_missing_fine_uses_resident_medium(self):
        """Missing pages never disappear; fallback is explicit and quality is measured."""
        choice = self.lods.choose(self.cam(20), 2, {'root','medium'})
        self.assertEqual(choice.page, 'medium')
        self.assertEqual(choice.preferred, 'fine')
        self.assertTrue(choice.fallback)
        self.assertFalse(choice.within_budget)

    def test_missing_medium_disallows_orphan_fine(self):
        """A resident fine page is unusable if its required parent is missing."""
        choice = self.lods.choose(self.cam(20), 2, {'root','fine'})
        self.assertEqual(choice.page, 'root')
        self.assertTrue(choice.fallback)

    def test_near_plane_crossing_demands_finest(self):
        """Avoid underestimating projected error for an intersecting bounding sphere."""
        choice = self.lods.choose(self.cam(0.5, radius=1), 2,
                                  {'root','medium','fine'})
        self.assertEqual(choice.page, 'fine')
        self.assertFalse(choice.within_budget)

    def test_orthographic_error_independent_of_distance(self):
        """Orthographic projected errors do not fall with camera distance."""
        a = Camera(5, 1, 500, None, 20)
        b = Camera(500, 1, 500, None, 20)
        self.assertEqual(a.error_px(0.1), 2.5)
        self.assertEqual(a.error_px(0.1), b.error_px(0.1))

    def test_nonuniform_scale_applies_conservative_max_scale(self):
        """Scaled objects increase the estimated worst-case projected error."""
        normal = self.cam(100)
        scaled = replace(normal, max_scale=3)
        self.assertAlmostEqual(scaled.error_px(0.2), normal.error_px(0.2) * 3)

    def test_hysteresis_prevents_threshold_flicker(self):
        """Small oscillations around an error threshold keep the previous LOD."""
        resident = {'root','medium','fine'}
        # Find two depths giving medium projected error ~ just over and under 2px.
        d = 0.2 * (1000 / (2 * __import__('math').tan(__import__('math').radians(60)/2))) / 2 + 1
        selected = self.lods.choose(self.cam(d*0.98), 2, resident, previous='medium')
        self.assertEqual(selected.page, 'medium')
        selected = self.lods.choose(self.cam(d*1.02), 2, resident, previous='fine')
        self.assertEqual(selected.page, 'fine')

    def test_hysteresis_allows_significant_upgrade_and_downgrade(self):
        """Strong error signals can still change quality promptly."""
        resident = {'root','medium','fine'}
        near = self.lods.choose(self.cam(20), 2, resident, previous='medium')
        self.assertEqual(near.page, 'fine')
        far = self.lods.choose(self.cam(1000), 2, resident, previous='fine')
        self.assertEqual(far.page, 'root')
        self.assertTrue(far.changed)

    def test_missing_previous_forces_safe_fallback(self):
        """After eviction, a previous page cannot be retained by hysteresis."""
        choice = self.lods.choose(self.cam(20), 2, {'root'}, previous='fine')
        self.assertEqual(choice.page, 'root')
        self.assertTrue(choice.changed)

    def test_zero_error_exact_geometry_requires_no_detail(self):
        """Exact coarse representation is always adequate even near the camera."""
        exact = LODSelector([Level('root', None, 0.0), Level('fine','root',0.0)])
        choice = exact.choose(self.cam(.01, radius=1), 1, {'root'})
        self.assertEqual(choice.page, 'root')
        self.assertEqual(choice.pixel_error, 0)

    def test_invalid_projection_and_lod_chain(self):
        """Do not hide malformed assets or unsafe camera math behind a fallback."""
        with self.assertRaises(ValueError):
            Camera(10, 1, viewport_height=0)
        with self.assertRaises(ValueError):
            Camera(10, 1, perspective_fov_y_deg=180)
        with self.assertRaises(ValueError):
            Camera(10, 1, perspective_fov_y_deg=60, ortho_height=20)
        with self.assertRaises(ValueError):
            LODSelector([Level('root',None,.1), Level('fine','root',.2)])
        with self.assertRaises(ValueError):
            self.lods.choose(self.cam(), 1, set())
        with self.assertRaises(ValueError):
            self.lods.choose(self.cam(), 1, {'root'}, hysteresis=1)

    def test_lod_choice_can_drive_async_page_demand(self):
        """Desired detail requests flow into async streaming while coarse stays visible."""
        s = AsyncGeometry(100,100,100,100)
        for key,size,parent in [('root',20,None),('medium',30,'root'),('fine',40,'medium')]:
            s.register(key,size,parent)
        choice = self.lods.choose(self.cam(20), 2, s.resident)
        self.assertEqual(choice.page, 'root')
        self.assertEqual(choice.preferred, 'fine')
        s.request(choice.preferred)
        for t in s.issue_reads(100):
            s.complete_read(t)
        for _ in range(2):
            for t in s.issue_uploads(100):
                self.assertEqual(s.complete_upload(t), 'RESIDENT')
        choice = self.lods.choose(self.cam(20), 2, s.resident)
        self.assertEqual(choice.page, 'fine')
        self.assertFalse(choice.fallback)

    def test_random_perspective_errors_decrease_with_distance(self):
        """Projection estimate is monotone, independent of randomized input order."""
        rng = random.Random(9218)
        for _ in range(700):
            radius = rng.uniform(0.01, 3)
            near = rng.uniform(.05, .5)
            d = rng.uniform(radius+near+1, 1000)
            e = rng.uniform(0, 5)
            a = Camera(d, radius, near=near)
            b = Camera(d+10, radius, near=near)
            self.assertLessEqual(b.error_px(e), a.error_px(e))
            choice = self.lods.choose(a, 2, {'root','medium','fine'})
            self.assertIn(choice.page, self.lods.names)


if __name__ == '__main__':
    unittest.main()

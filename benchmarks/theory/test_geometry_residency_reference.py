"""Synthetic residency/LOD fallback tests requiring no renderer or GPU."""

import random
import unittest
from geometry_residency_reference import GeometryResidency


class ResidencyTests(unittest.TestCase):
    """Assert no missing coarse geometry, bounded allocations and frame safety."""

    def setUp(self):
        """Provide a coarse tree root with streamable medium and fine pages."""
        self.r = GeometryResidency(100)
        self.r.register('root', 20)
        self.r.register('medium', 30, 'root')
        self.r.register('fine', 50, 'medium')

    def test_coarse_root_is_immediately_drawable(self):
        """Incomplete streaming never makes a registered object invisible."""
        self.assertEqual(self.r.fallback('fine'), 'root')
        self.assertTrue(self.r.verify())
        self.assertEqual(self.r.used_bytes, 20)

    def test_parent_first_detail_then_fine(self):
        """Hierarchies must load prerequisite coarse levels first."""
        self.r.request('fine')
        self.assertEqual(self.r.step(100).loaded, ('medium',))
        self.assertEqual(self.r.fallback('fine'), 'medium')
        self.assertEqual(self.r.step(100).loaded, ('fine',))
        self.assertEqual(self.r.fallback('fine'), 'fine')
        self.assertTrue(self.r.verify())

    def test_hard_budget_holds_fallback_when_page_is_too_large(self):
        """Unavailable high detail cannot break root-only fallback."""
        r = GeometryResidency(40)
        r.register('base', 15)
        r.register('detail', 50, 'base')
        r.request('detail')
        self.assertEqual(r.step(100).loaded, ())
        self.assertEqual(r.fallback('detail'), 'base')
        self.assertTrue(r.verify())

    def test_upload_budget_does_not_partially_publish_page(self):
        """A byte-limited step must never expose a partially loaded detail page."""
        self.r.request('fine')
        self.assertEqual(self.r.step(10).upload_bytes, 0)
        self.assertEqual(self.r.fallback('fine'), 'root')
        self.assertEqual(self.r.step(30).loaded, ('medium',))
        self.assertEqual(self.r.step(20).loaded, ())
        self.assertTrue(self.r.verify())

    def test_root_cannot_exceed_pinned_budget(self):
        """Invalid registration is atomic, preserving the only legal fallback."""
        with self.assertRaises(ValueError):
            self.r.register('too_big_root', 90)
        self.assertNotIn('too_big_root', self.r.pages)
        self.assertEqual(self.r.used_bytes, 20)
        self.assertTrue(self.r.verify())

    def test_multi_camera_coalesces_demand(self):
        """One page is uploaded once for independently requesting cameras."""
        self.r.request('medium', 'a', 1, 80)
        self.r.request('medium', 'b', 1, 40)
        self.assertEqual(self.r.step(30).loaded, ('medium',))
        self.assertEqual(self.r.step(30).loaded, ())
        self.assertTrue(self.r.verify())

    def test_camera_cut_invalidates_only_its_old_demands(self):
        """New view epochs do not wipe other views or reusable resident pages."""
        self.r.request('fine', 'a', 1)
        self.r.request('medium', 'b', 1)
        self.r.set_view_epoch('a', 2)
        self.assertNotIn(('a', 'fine'), self.r.demands)
        self.assertIn(('b', 'medium'), self.r.demands)
        self.assertEqual(self.r.request('fine', 'a', 1), 'STALE_VIEW')
        self.assertEqual(self.r.step(30).loaded, ('medium',))
        self.assertEqual(self.r.fallback('fine'), 'medium')

    def test_eviction_under_pressure_preserves_coarse_root(self):
        """Loading detail of another object may evict optional leaves, never roots."""
        self.r.capacity = 120  # Both roots and the first fine page must fit initially.
        self.r.register('other_root', 10)
        self.r.register('other_detail', 35, 'other_root')
        self.r.request('fine')
        self.r.step(100)
        self.r.step(100)
        self.r.request('other_detail', 'camera2')
        result = self.r.step(100)
        self.assertEqual(result.loaded, ('other_detail',))
        self.assertIn('fine', result.evicted)
        self.assertIn('root', self.r.resident)
        self.assertIn('other_root', self.r.resident)
        self.assertEqual(self.r.fallback('fine'), 'medium')
        self.assertTrue(self.r.verify())

    def test_outstanding_draw_prevents_eviction_of_page(self):
        """A frame's detail page cannot be replaced while the frame uses it."""
        self.r.capacity = 120  # Both roots and the first fine page must fit initially.
        self.r.register('other_root', 10)
        self.r.register('other_detail', 35, 'other_root')
        self.r.request('fine')
        self.r.step(100)
        self.r.step(100)
        frame = self.r.submit(['fine'])
        self.r.request('other_detail')
        result = self.r.step(100)
        self.assertEqual(result.loaded, ())
        self.assertEqual(self.r.fallback('other_detail'), 'other_root')
        self.r.retire(frame)
        self.assertEqual(self.r.step(100).loaded, ('other_detail',))
        self.assertTrue(self.r.verify())

    def test_parent_protected_while_resident_child(self):
        """Eviction may not delete a page needed as another page's parent."""
        self.r.request('fine')
        self.r.step(100)
        self.r.step(100)
        self.assertTrue(self.r._dependent('medium'))
        self.assertTrue(self.r.verify())

    def test_duplicate_and_invalid_retirement(self):
        """Reference counts cannot become negative through double completion."""
        frame = self.r.submit(['root'])
        self.r.retire(frame)
        with self.assertRaises(ValueError):
            self.r.retire(frame)
        self.assertEqual(self.r.refs['root'], 0)
        self.assertTrue(self.r.verify())

    def test_invalid_pages_and_requests(self):
        """Reject invalid page dependencies, names and epoch/priority values."""
        for args in (('root', 10), ('missingparent', 10, 'missing'), ('n', 0)):
            with self.assertRaises(ValueError):
                self.r.register(*args)
        with self.assertRaises(ValueError):
            self.r.request('missing')
        with self.assertRaises(ValueError):
            self.r.request('fine', epoch=0)
        with self.assertRaises(ValueError):
            self.r.request('fine', importance=101)
        with self.assertRaises(ValueError):
            self.r.submit(['fine'])

    def test_failed_budget_fit_does_not_evict_useful_detail(self):
        """Planning a failed load cannot degrade pages that remain drawable."""
        r = GeometryResidency(100)
        r.register('base', 20)
        r.register('other', 20)
        r.register('small', 20, 'base')
        r.register('too_large', 70, 'other')
        r.request('small', importance=80)
        self.assertEqual(r.step(100).loaded, ('small',))
        r.request('too_large', importance=100)
        result = r.step(100)
        self.assertEqual(result.loaded, ())
        self.assertEqual(result.evicted, ())
        self.assertEqual(r.fallback('small'), 'small')
        self.assertEqual(r.fallback('too_large'), 'other')
        self.assertTrue(r.verify())

    def test_deterministic_camera_teleport_stress(self):
        """500 changes keep a drawable ancestor and exact resident byte accounting."""
        r = GeometryResidency(120)
        for i in range(4):
            r.register(f'r{i}', 10)
            r.register(f'm{i}', 20, f'r{i}')
            r.register(f'f{i}', 45, f'm{i}')
        rng = random.Random(73842)
        frames = []
        for tick in range(500):
            view = 'a' if tick % 2 else 'b'
            epoch = tick // 2 + 1
            target = f'f{rng.randrange(4)}'
            r.request(target, view, epoch, rng.randrange(101))
            r.step(rng.randrange(10, 70))
            chosen = r.fallback(target)
            self.assertIn(chosen, r.resident)
            self.assertTrue(r.verify())
            if rng.randrange(4) == 0:
                frames.append(r.submit([chosen]))
            if frames and rng.randrange(3) == 0:
                r.retire(frames.pop(rng.randrange(len(frames))))
        for frame in frames:
            r.retire(frame)
        self.assertTrue(r.verify())


if __name__ == '__main__':
    unittest.main()

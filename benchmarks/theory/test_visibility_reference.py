"""CPU-only correctness gates for the optional GPU visibility design."""

import random
import unittest

from visibility_reference import (Handle, Instance, Plane, Scene, Sphere, View,
                                  box_intersects, sphere_intersects)


def box_view(half=10, layers=0xFFFFFFFF):
    """Construct a closed axis-aligned reference frustum."""
    return View(tuple(Plane(tuple(sign if j == axis else 0 for j in range(3)), half)
                      for axis in range(3) for sign in (-1, 1)), layers)


class VisibilityReferenceTests(unittest.TestCase):
    """Compare optimized selection to a complete control after adverse edits."""

    def test_empty_scene_and_clean_dirty(self):
        """Empty scene must be visible nowhere and produce no writes."""
        scene = Scene()
        self.assertEqual(scene.cull(box_view()).handles, ())
        self.assertEqual(scene.dirty_runs(), ())

    def test_conservative_boundary_and_non_unit_planes(self):
        """Tangent spheres and scaled planes remain visible; fully outside do not."""
        planes = (Plane((2, 0, 0), 20),)
        self.assertTrue(sphere_intersects(Sphere((-11, 0, 0), 1), planes))
        self.assertFalse(sphere_intersects(Sphere((-11.01, 0, 0), 1), planes))
        self.assertTrue(box_intersects(((-11, -1, -1), (-9, 1, 1)), planes))

    def test_aabb_includes_region_straddling_spheres(self):
        """Center-only spatial bins must not accidentally clip crossing spheres."""
        scene = Scene(region_size=5)
        handle = scene.create(Instance(Sphere((7, 0, 0), 5)))
        view = View((Plane((-1, 0, 0), 2),))  # x <= 2 intersects at x=2
        self.assertEqual(scene.cull(view).handles, (handle,))
        self.assertEqual(scene.cull(view).handles, scene.full_scan(view))

    def test_rehome_and_bounds_shrink(self):
        """Crossing cell boundaries and shrinking former bounds stay correct."""
        scene = Scene(region_size=10)
        h1 = scene.create(Instance(Sphere((0, 0, 0), 1)))
        h2 = scene.create(Instance(Sphere((1, 0, 0), 1)))
        scene.change(h1, sphere=Sphere((50, 0, 0), 1))
        self.assertEqual(scene.cull(box_view(3)).handles, (h2,))
        scene.delete(h2)
        self.assertEqual(scene.cull(box_view(3)).handles, ())
        self.assertEqual(scene.cull(box_view(3)).handles, scene.full_scan(box_view(3)))

    def test_generation_on_delete_reuse(self):
        """A recycled slot cannot accept a stale transform or deletion."""
        scene = Scene()
        old = scene.create(Instance(Sphere((0, 0, 0), 1)))
        scene.delete(old)
        new = scene.create(Instance(Sphere((1, 0, 0), 1)))
        self.assertEqual(old.slot, new.slot)
        self.assertNotEqual(old.generation, new.generation)
        with self.assertRaises(ValueError):
            scene.change(old, sphere=Sphere((2, 0, 0), 1))
        with self.assertRaises(ValueError):
            scene.delete(old)
        self.assertEqual(scene.dirty_runs()[0].values[0].handle, new)

    def test_deletion_tombstone(self):
        """Deletion is emitted even when the slot becomes empty."""
        scene = Scene()
        h = scene.create(Instance(Sphere((0, 0, 0), 1)))
        scene.dirty_runs()
        scene.delete(h)
        update = scene.dirty_runs()[0].values[0]
        self.assertIsNone(update.record)
        self.assertEqual(update.handle.generation, h.generation + 1)

    def test_last_write_wins_and_contiguous_runs(self):
        """Repeat modifications of adjacent slots coalesce without obsolete values."""
        scene = Scene()
        handles = [scene.create(Instance(Sphere((i, 0, 0), 1))) for i in range(6)]
        scene.dirty_runs()
        scene.change(handles[1], sphere=Sphere((100, 0, 0), 1))
        scene.change(handles[1], sphere=Sphere((200, 0, 0), 1))
        scene.change(handles[2], layers=2)
        scene.change(handles[4], enabled=False)
        runs = scene.dirty_runs()
        self.assertEqual([(r.start, len(r.values)) for r in runs], [(1, 2), (4, 1)])
        self.assertEqual(runs[0].values[0].record.sphere.center, (200, 0, 0))
        self.assertEqual(scene.dirty_runs(), ())

    def test_multiview_layers_and_camera_cut(self):
        """Separate cameras must recompute independent geometry and layer selection."""
        scene = Scene(region_size=3)
        a = scene.create(Instance(Sphere((0, 0, 0), 1), layers=1))
        b = scene.create(Instance(Sphere((100, 0, 0), 1), layers=2))
        self.assertEqual(scene.cull(box_view(10, 1)).handles, (a,))
        self.assertEqual(scene.cull(box_view(200, 2)).handles, (b,))
        self.assertEqual(scene.cull(box_view(10, 1)).handles, (a,))
        scene.change(b, sphere=Sphere((0, 0, 0), 1))
        self.assertEqual(scene.cull(box_view(10, 2)).handles, (b,))

    def test_capacity_overflow_requires_full_fallback(self):
        """The experimental compacted buffer must never silently drop visible IDs."""
        scene = Scene()
        hs = [scene.create(Instance(Sphere((0, 0, 0), 1))) for _ in range(5)]
        result = scene.cull(box_view(), capacity=2)
        self.assertTrue(result.fallback_required)
        self.assertEqual(result.handles, tuple(hs))
        self.assertFalse(scene.cull(box_view(), capacity=5).fallback_required)

    def test_transform_nonuniform_and_shear_conservative(self):
        """Bounding-radius scale covers nonuniform transforms without clipping."""
        s = Sphere((1, 2, 3), 1)
        identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        self.assertEqual(s.transformed(identity, (0, 0, 0)), s)
        scaled = s.transformed(((2, 0, 0), (0, 1, 0), (0, 0, 0.5)), (2, 0, 0))
        self.assertEqual(scaled.center, (4, 2, 1.5))
        self.assertGreaterEqual(scaled.radius, 2)
        sheared = s.transformed(((1, 2, 0), (0, 1, 0), (0, 0, 1)), (0, 0, 0))
        self.assertGreaterEqual(sheared.radius, (5 ** 0.5))

    def test_disabled_zero_layer_and_instance_immutability(self):
        """Disabled or unmatched layers stay invisible despite region overlap."""
        scene = Scene()
        a = scene.create(Instance(Sphere((0, 0, 0), 1), enabled=False))
        b = scene.create(Instance(Sphere((0, 0, 0), 1), layers=0))
        c = scene.create(Instance(Sphere((0, 0, 0), 1), layers=4))
        self.assertEqual(scene.cull(box_view(10, 4)).handles, (c,))
        self.assertEqual(scene.full_scan(box_view(10, 4)), (c,))
        scene.change(a, enabled=True)
        self.assertEqual(scene.cull(box_view(10, 1)).handles, (a,))

    def test_adverse_deterministic_random_edit_sequence(self):
        """Regional culling must equal independent full scan across dynamic scenes."""
        randomizer = random.Random(81277)
        scene = Scene(region_size=4)
        active = []
        views = (box_view(4, 1), box_view(20, 2), box_view(100, 0xFFFFFFFF),
                 View((Plane((1, 1, 1), 15),), 3))
        for step in range(180):
            if active and step % 5 == 0:
                idx = randomizer.randrange(len(active))
                scene.delete(active.pop(idx))
            elif active and step % 3 == 0:
                h = randomizer.choice(active)
                scene.change(h, sphere=Sphere(tuple(randomizer.uniform(-40, 40) for _ in range(3)),
                                              randomizer.uniform(0, 8)),
                             layers=randomizer.choice((0, 1, 2, 3)),
                             enabled=randomizer.choice((True, False)))
            else:
                active.append(scene.create(Instance(
                    Sphere(tuple(randomizer.uniform(-40, 40) for _ in range(3)),
                           randomizer.uniform(0, 8)),
                    layers=randomizer.choice((0, 1, 2, 3)))))
            for view in views:
                result = scene.cull(view)
                self.assertEqual(result.handles, scene.full_scan(view))
                self.assertLessEqual(result.instances_tested, len(scene.records))
            if step % 7 == 0:
                scene.dirty_runs()


    def test_mutable_inputs_are_snapshotted_and_empty_regions_do_not_leak(self):
        """External input-list mutations cannot corrupt cached bounds or dead keys."""
        source_center = [1, 2, 3]
        source_normal = [1, 0, 0]
        source_planes = [Plane(source_normal, 10)]
        sphere = Sphere(source_center, 1)
        view = View(source_planes)
        source_center[0] = 10000
        source_normal[0] = -1
        source_planes.clear()
        self.assertEqual(sphere.center, (1, 2, 3))
        self.assertEqual(view.planes[0].normal, (1, 0, 0))
        self.assertEqual(len(view.planes), 1)
        scene = Scene(region_size=2)
        h = scene.create(Instance(sphere))
        scene.cull(view)
        scene.delete(h)
        self.assertEqual(scene.regions, {})
        self.assertEqual(scene.bounds_cache, {})
        self.assertEqual(scene.invalid_regions, set())

    def test_input_validation(self):
        """Bad bounds, zero normals and invalid capacities fail explicitly."""
        for call in (lambda: Scene(0), lambda: Sphere((0, float('nan'), 0), 1),
                     lambda: Sphere((0, 0, 0), -1), lambda: Plane((0, 0, 0), 1),
                     lambda: View((), -1), lambda: Instance(Sphere((0, 0, 0), 1), layers=-1)):
            with self.assertRaises(ValueError):
                call()
        with self.assertRaises(ValueError):
            Scene().cull(box_view(), capacity=0)
        with self.assertRaises(ValueError):
            Sphere((0, 0, 0), 1).transformed(((1, 0, 0),), (0, 0, 0))


if __name__ == '__main__':
    unittest.main()

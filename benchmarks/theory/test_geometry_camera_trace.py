"""Synthetic camera traces for geometry demand, complete 2D covers and seams."""
import random
import unittest
from geometry_camera_trace import CameraTrace, View, build_grid


class CameraTraceTests(unittest.TestCase):
    """Compare reproducible quality and memory accounting without graphics hardware."""

    def test_stable_close_view_reaches_available_fine_detail(self):
        """After bounded latency, a stable close view reaches the finest patches."""
        scene=CameraTrace()
        frames=[scene.step((View('main',2,2,5),)) for _ in range(24)]
        self.assertEqual(frames[0].missing_quality_area,32)
        self.assertEqual(frames[-1].missing_quality_area,0)
        self.assertGreater(frames[-1].selected_quality_area,frames[-1].requested_quality_area)
        self.assertGreater(frames[-1].excess_quality_area,0)  # Complete root split requires far siblings.
        self.assertIn('q00l00',frames[-1].visible)
        self.assertTrue(scene.stream.verify())

    def test_far_camera_avoids_unnecessary_detail_requests(self):
        """Coarse level suffices at extreme distance without simulated IO."""
        scene=CameraTrace()
        frames=[scene.step((View('main',2,2,4000),)) for _ in range(8)]
        self.assertTrue(all(f.visible==('root',) and f.missing_quality_area==0 for f in frames))
        self.assertEqual(scene.issued_read,0)
        self.assertEqual(scene.stream.resident_bytes,16)

    def test_bad_seam_coarsens_and_reports_lost_quality(self):
        """A resident but incompatible fine border cannot silently produce cracks."""
        good=CameraTrace()
        bad=CameraTrace(damaged_border=True)
        for _ in range(20):
            fg=good.step((View('a',2,2,5),))
            fb=bad.step((View('a',2,2,5),))
        self.assertEqual(fg.missing_quality_area,0)
        self.assertGreater(fb.missing_quality_area,0)
        self.assertGreater(fb.suppressed_refinements,0)
        self.assertIn('q00',fb.visible)
        self.assertTrue(bad.cover.verify_cover(fb.visible))

    def test_identical_multicamera_demand_does_not_double_load(self):
        """Shared-page demand coalesces independently of the number of cameras."""
        single=CameraTrace()
        multi=CameraTrace()
        for _ in range(20):
            a=single.step((View('left',2,2,5),))
            b=multi.step((View('left',2,2,5),View('right',2,2,5)))
            self.assertEqual(a.visible,b.visible)
        self.assertEqual(single.issued_read,multi.issued_read)
        self.assertEqual(single.issued_upload,multi.issued_upload)
        self.assertEqual(single.stream.resident,multi.stream.resident)

    def test_seeded_teleports_are_reproducible(self):
        """Rapid camera movement cannot break full coverage or hard memory ceilings."""
        rng=random.Random(18041)
        path=[]
        spots=((2,2),(6,2),(2,6),(6,6))
        for _ in range(250):
            x,y=spots[rng.randrange(4)]
            z=rng.choice((3,5,20,400,2000))
            path.append((View('main',x,y,z),))
        first=CameraTrace(read_latency=3,upload_latency=2)
        second=CameraTrace(read_latency=3,upload_latency=2)
        a=first.run(path)
        b=second.run(path)
        self.assertEqual(a,b)
        self.assertLessEqual(a.max_resident_bytes,first.stream.resident_limit)
        self.assertLessEqual(a.max_decoded_bytes,first.stream.decoded_limit)
        self.assertLessEqual(a.max_staging_bytes,first.stream.staging_limit)
        self.assertTrue(all(first.cover.verify_cover(f.visible) for f in a.frames))
        self.assertTrue(all(not first.cover.seams(f.visible)[0] for f in a.frames))
        self.assertGreater(a.cancelled_tickets,0)
        self.assertTrue(first.stream.verify())

    def test_oscillating_focus_exposes_budget_churn_without_missing_regions(self):
        """Frequent working-set changes may evict detail but preserve exact fallback."""
        trace=CameraTrace(resident_limit=100,draw_latency=2)
        spots=((2,2),(6,2),(2,6),(6,6))
        for tick in range(160):
            x,y=spots[(tick//12)%4]
            report=trace.step((View('main',x,y,5),))
            self.assertLessEqual(report.resident_bytes,100)
            self.assertTrue(trace.cover.verify_cover(report.visible))
            self.assertGreaterEqual(report.missing_quality_area,0)
            self.assertLessEqual(report.missing_quality_area,128)
        self.assertGreater(trace.evicted,0)
        self.assertGreater(trace.loaded,4)

    def test_deterministic_budgets_bound_per_frame_io_and_upload(self):
        """Frame-level budgets must constrain synthetic transfer starts exactly."""
        trace=CameraTrace(read_per_frame=25,upload_per_frame=15)
        frames=[trace.step((View('a',2,2,5),)) for _ in range(40)]
        self.assertTrue(all(f.read_bytes_started<=25 for f in frames))
        self.assertTrue(all(f.upload_bytes_started<=15 for f in frames))
        self.assertTrue(trace.stream.verify())

    def test_invalid_views_fail_before_state_changes(self):
        """A malformed camera cannot partially invalidate previous requests."""
        scene=CameraTrace()
        bad=((),(View('a',2,2,4),View('a',6,2,4)),(View('',2,2,4),),
             (View('a',2,2,-1),),(View('a',2,2,4,0),),(None,),
             (View('a',float('nan'),2,4),))
        for views in bad:
            with self.subTest(views=views),self.assertRaises(ValueError):
                scene.step(views)
            self.assertEqual(scene.frame_index,0)
            self.assertFalse(scene.stream.demands)

    def test_pages_map_to_exact_2d_grid(self):
        """The camera lab uses one root, four quadrants, sixteen leaf pages."""
        self.assertEqual(len(build_grid()),21)
        trace=CameraTrace()
        self.assertEqual(len(trace.stream.pages),21)
        self.assertTrue(trace.cover.verify_cover(('root',)))
        self.assertEqual(trace.stream.resident,{'root'})

    def test_explicit_reset_after_synthetic_frames_retire(self):
        """Old draw tickets and streaming completions must drain before scene reset."""
        trace=CameraTrace(read_latency=2,upload_latency=2,draw_latency=3)
        for _ in range(10):
            trace.step((View('a',2,2,5),))
        trace.stream.begin_reset()
        with self.assertRaises(RuntimeError):
            trace.stream.complete_reset()
        for _,t in list(trace.reads):
            trace.stream.complete_read(t)
        for _,t in list(trace.uploads):
            trace.stream.complete_upload(t)
        for _,frame in list(trace.draws):
            trace.stream.retire(frame)
        trace.stream.complete_reset()
        self.assertEqual(trace.stream.scene_epoch,2)
        self.assertEqual(trace.stream.resident,{'root'})
        self.assertTrue(trace.stream.verify())


if __name__=='__main__':
    unittest.main()

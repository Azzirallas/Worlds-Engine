"""CPU-only regression tests for asynchronous geometry page residency."""
import random
import unittest
from geometry_async_reference import AsyncGeometry


class AsyncReleaseTests(unittest.TestCase):
    """Assert stable coarse fallback, explicit completion and hard budgets."""

    def setUp(self):
        """Initialize one hierarchy and four independent synthetic byte budgets."""
        self.s = AsyncGeometry(100, 100, 100, 100)
        self.s.register('root', 20)
        self.s.register('mid', 30, 'root')
        self.s.register('fine', 40, 'mid')

    def finish(self, name):
        """Complete available reads and uploads until the chosen page is resident."""
        self.s.request(name)
        for ticket in self.s.issue_reads(100):
            self.assertEqual(self.s.complete_read(ticket), 'DECODED')
        for _ in range(2):
            for ticket in self.s.issue_uploads(100):
                self.assertEqual(self.s.complete_upload(ticket), 'RESIDENT')
        return self.s.fallback(name)

    def test_parent_first_and_pinned_fallback(self):
        """No fine page may publish without a resident parent and root."""
        self.assertEqual(self.s.fallback('fine'), 'root')
        self.assertEqual(self.finish('fine'), 'fine')
        self.assertEqual(self.s.resident_bytes, 90)
        self.assertTrue(self.s.verify())

    def test_camera_cut_discards_unwanted_read(self):
        """Old camera demand cannot revive obsolete geometry after a cut."""
        self.s.request('mid', 'a', 1)
        ticket = self.s.issue_reads(100)[0]
        self.s.set_view_epoch('a', 2)
        self.assertEqual(self.s.complete_read(ticket), 'CANCELLED_VIEW')
        self.assertEqual(self.s.request('mid', 'a', 1), 'STALE_VIEW')
        self.assertEqual(self.s.fallback('mid'), 'root')

    def test_other_camera_retains_shared_request(self):
        """Cancellation by one view does not revoke another view's demand."""
        self.s.request('mid', 'a', 1)
        self.s.request('mid', 'b', 1)
        ticket = self.s.issue_reads(100)[0]
        self.s.set_view_epoch('a', 2)
        self.assertEqual(self.s.complete_read(ticket), 'DECODED')
        self.assertEqual(self.s.complete_upload(self.s.issue_uploads(100)[0]), 'RESIDENT')

    def test_hot_reload_stale_read_and_upload(self):
        """Generation checks reject old IO/transfer completions without partial data."""
        self.s.request('mid')
        read = self.s.issue_reads(100)[0]
        self.assertEqual(self.s.hot_reload('mid'), 'INVALIDATED')
        self.assertEqual(self.s.complete_read(read), 'STALE')
        new_read = self.s.issue_reads(100)[0]
        self.assertGreater(new_read.generation, read.generation)
        self.s.complete_read(new_read)
        upload = self.s.issue_uploads(100)[0]
        self.s.hot_reload('mid')
        self.assertEqual(self.s.complete_upload(upload), 'STALE')
        self.assertEqual(self.s.fallback('mid'), 'root')
        self.assertTrue(self.s.verify())

    def test_cancelled_upload_never_evicts_current_detail(self):
        """Camera cuts reject a completed transfer without changing residency."""
        self.s.request('mid', 'camera', 1)
        self.s.complete_read(self.s.issue_reads(100)[0])
        upload = self.s.issue_uploads(100)[0]
        self.s.set_view_epoch('camera', 2)
        self.assertEqual(self.s.complete_upload(upload), 'CANCELLED_VIEW')
        self.assertEqual(self.s.resident, {'root'})
        self.assertEqual(self.s.decoded_bytes, 0)

    def test_hard_budget_reports_impossible_pages_without_reads(self):
        """No futile recurring IO for pages that cannot pass a mandatory byte cap."""
        for limits, expected in [((100, 100, 5, 100), 'READ_LIMIT'),
                                 ((100, 5, 100, 100), 'DECODED_LIMIT'),
                                 ((100, 100, 100, 5), 'STAGING_LIMIT'),
                                 ((45, 100, 100, 100), 'RESIDENT_LIMIT')]:
            state = AsyncGeometry(*limits)
            state.register('root', 20)
            state.register('detail', 30, 'root')
            state.request('detail')
            self.assertEqual(state.blocked_reason('detail'), expected)
            self.assertEqual(state.issue_reads(100), ())
            self.assertTrue(state.verify())

    def test_failed_io_and_upload_retry(self):
        """A recoverable transfer failure must not require an unnecessary disk read."""
        self.s.request('mid')
        failed = self.s.issue_reads(100)[0]
        self.assertEqual(self.s.complete_read(failed, False), 'FAILED')
        self.assertEqual(self.s.complete_read(self.s.issue_reads(100)[0]), 'DECODED')
        up = self.s.issue_uploads(100)[0]
        self.assertEqual(self.s.complete_upload(up, False), 'FAILED')
        self.assertEqual(self.s.issue_reads(100), ())
        self.assertEqual(self.s.complete_upload(self.s.issue_uploads(100)[0]), 'RESIDENT')

    def test_frame_hold_blocks_hot_reload(self):
        """A submitted frame owns every resident ancestor until retirement."""
        self.finish('fine')
        frame = self.s.submit(['fine'])
        self.assertEqual([self.s.refs[n] for n in ('root', 'mid', 'fine')], [1, 1, 1])
        self.assertEqual(self.s.hot_reload('mid'), 'BUSY_FRAME')
        self.s.retire(frame)
        self.assertEqual(self.s.hot_reload('mid'), 'INVALIDATED')
        self.assertEqual(self.s.fallback('fine'), 'root')
        self.assertTrue(self.s.verify())

    def test_eviction_after_retirement_is_transactional(self):
        """Frame-referenced detail cannot be evicted before its draw completes."""
        s = AsyncGeometry(75, 120, 120, 120)
        s.register('root_a', 10)
        s.register('old', 35, 'root_a')
        s.register('root_b', 10)
        s.register('new', 45, 'root_b')
        s.request('old')
        s.complete_read(s.issue_reads(100)[0])
        s.complete_upload(s.issue_uploads(100)[0])
        frame = s.submit(['old'])
        s.request('new')
        s.complete_read(s.issue_reads(100)[0])
        self.assertEqual(s.complete_upload(s.issue_uploads(100)[0]), 'WAIT_CAPACITY')
        self.assertEqual(s.fallback('new'), 'root_b')
        s.retire(frame)
        self.assertEqual(s.complete_upload(s.issue_uploads(100)[0]), 'RESIDENT')
        self.assertEqual(s.last_evicted, ('old',))
        self.assertTrue(s.verify())

    def test_failed_fit_preserves_resident_quality(self):
        """An unsuccessful load must not evict useful dependent pages."""
        s = AsyncGeometry(95, 120, 120, 120)
        s.register('a', 10)
        s.register('old', 25, 'a')
        s.register('child', 10, 'old')
        s.register('b', 10)
        s.register('huge', 60, 'b')
        s.request('child')
        for ticket in s.issue_reads(120):
            s.complete_read(ticket)
        for _ in range(2):
            s.complete_upload(s.issue_uploads(120)[0])
        s.request('huge')
        s.complete_read(s.issue_reads(120)[0])
        self.assertEqual(s.complete_upload(s.issue_uploads(120)[0]), 'WAIT_CAPACITY')
        self.assertEqual(s.fallback('child'), 'child')
        self.assertTrue(s.verify())

    def test_reset_waits_for_read_upload_and_draw(self):
        """Two-phase world reset must drain every outstanding completion owner."""
        self.finish('mid')
        draw = self.s.submit(['mid'])
        self.s.request('fine')
        read = self.s.issue_reads(100)[0]
        self.s.complete_read(read)
        upload = self.s.issue_uploads(100)[0]
        self.s.begin_reset()
        with self.assertRaises(RuntimeError):
            self.s.complete_reset()
        self.s.retire(draw)
        with self.assertRaises(RuntimeError):
            self.s.complete_reset()
        self.assertEqual(self.s.complete_upload(upload), 'CANCELLED_RESET')
        self.s.complete_reset()
        self.assertEqual(self.s.scene_epoch, 2)
        self.assertEqual(self.s.fallback('fine'), 'root')
        self.assertTrue(self.s.verify())

    def test_duplicate_completion_rejected(self):
        """Late or duplicate acknowledgements cannot release memory twice."""
        self.s.request('mid')
        read = self.s.issue_reads(100)[0]
        self.s.complete_read(read)
        with self.assertRaises(ValueError):
            self.s.complete_read(read)
        upload = self.s.issue_uploads(100)[0]
        self.s.complete_upload(upload)
        with self.assertRaises(ValueError):
            self.s.complete_upload(upload)

    def test_randomized_cuts_reloads_and_fences(self):
        """1,200 operations preserve strict bytes and a drawable ancestor per asset."""
        rng = random.Random(52019)
        s = AsyncGeometry(115, 110, 95, 95)
        for i in range(3):
            s.register('root' + str(i), 10)
            s.register('mid' + str(i), 20, 'root' + str(i))
            s.register('fine' + str(i), 35, 'mid' + str(i))
        reads, uploads, frames = [], [], []
        epochs = [1, 1]
        for step in range(1200):
            op = rng.randrange(11)
            if op <= 1:
                view = rng.randrange(2)
                epochs[view] += int(op == 1)
                s.request('fine' + str(rng.randrange(3)), 'cam' + str(view),
                          epochs[view], rng.randrange(101))
            elif op == 2:
                reads.extend(s.issue_reads(rng.randrange(10, 80)))
            elif op == 3 and reads:
                s.complete_read(reads.pop(rng.randrange(len(reads))), rng.randrange(5) != 0)
            elif op == 4:
                uploads.extend(s.issue_uploads(rng.randrange(10, 80)))
            elif op == 5 and uploads:
                s.complete_upload(uploads.pop(rng.randrange(len(uploads))), rng.randrange(5) != 0)
            elif op == 6:
                s.hot_reload('mid' + str(rng.randrange(3)))
            elif op == 7:
                name = 'fine' + str(rng.randrange(3))
                frames.append(s.submit([s.fallback(name)]))
            elif op == 8 and frames:
                s.retire(frames.pop(rng.randrange(len(frames))))
            self.assertTrue(s.verify(), step)
            for i in range(3):
                self.assertIn(s.fallback('fine' + str(i)), s.resident)
        for t in reads:
            s.complete_read(t)
        for t in uploads:
            s.complete_upload(t)
        for frame in frames:
            s.retire(frame)
        self.assertTrue(s.verify())


if __name__ == '__main__':
    unittest.main()

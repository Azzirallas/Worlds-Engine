"""Standard-library CPU tests for the theoretical MultiMesh region-cost model."""

import unittest

from multimesh_update_model import Policy, estimate_upload, expected_dirty_regions


class UploadModelTests(unittest.TestCase):
    """Check occupancy bounds, update locality, and threshold behavior."""

    def test_occupancy_boundaries(self):
        """Zero and full change probabilities have known exact expectations."""
        self.assertEqual(expected_dirty_regions(1000, 512, 0), 0)
        self.assertEqual(expected_dirty_regions(1000, 512, 1), 2)
        self.assertAlmostEqual(expected_dirty_regions(100_000, 512, 0.001), 78.315, places=2)

    def test_scattered_vs_clustered(self):
        """Identical edit counts can choose different upload modes."""
        policy = Policy(100_000, 100_000)
        close = estimate_upload(policy, range(100))
        scattered = estimate_upload(policy, range(0, 100_000, 1000))
        self.assertEqual(close, {"mode": "regions", "bytes": 512 * 48, "dirty_regions": 1})
        self.assertEqual(scattered, {"mode": "full", "bytes": 100_000 * 48, "dirty_regions": 100})

    def test_previous_dirty_regions(self):
        """A previous-frame region remains part of the abstract upload policy."""
        policy = Policy(2000, 2000)
        result = estimate_upload(policy, [], [1000])
        self.assertEqual(result["mode"], "regions")
        self.assertEqual(result["bytes"], 512 * 48)

    def test_visible_prefix_and_partial_bucket(self):
        """A partial last visible region counts only its visible instances."""
        policy = Policy(1000, 750)
        result = estimate_upload(policy, [600])
        self.assertEqual(result["mode"], "regions")
        self.assertEqual(result["bytes"], (750 - 512) * 48)

    def test_duplicate_edit_coalescing(self):
        """Two writes to the same instance only dirty its region once."""
        self.assertEqual(estimate_upload(Policy(1000, 1000), [4, 4, 4])["dirty_regions"], 1)

    def test_input_errors(self):
        """Invalid dimensions and out-of-range edits must raise errors."""
        with self.assertRaises(ValueError):
            Policy(-1, 0)
        with self.assertRaises(ValueError):
            Policy(5, 6)
        with self.assertRaises(ValueError):
            expected_dirty_regions(100, 512, 2.0)
        with self.assertRaises(ValueError):
            estimate_upload(Policy(10, 10), [10])


if __name__ == "__main__":
    unittest.main()

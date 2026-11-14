"""Deterministic CPU cluster coverage and coarse fallback regression tests."""
import random
import unittest
from cluster_coverage_reference import Cluster, ClusterCoverage


class CoverageTests(unittest.TestCase):
    """Check exact spatial partition and all-or-nothing subtree refinement."""

    def setUp(self):
        """Create a complete binary region tree with eight elementary cells."""
        self.tree = ClusterCoverage([
            Cluster('root', None, 0, 8),
            Cluster('left', 'root', 0, 4),
            Cluster('right', 'root', 4, 8),
            Cluster('a', 'left', 0, 2),
            Cluster('b', 'left', 2, 4),
            Cluster('c', 'right', 4, 6),
            Cluster('d', 'right', 6, 8),
        ])

    def test_coarse_only(self):
        """An unrefined root covers every cell exactly once."""
        self.assertEqual(self.tree.select({'root'}, {'root'}), ('root',))

    def test_full_refinement(self):
        """All four grandchildren may replace their complete ancestor tree."""
        selected = self.tree.select(set(self.tree.nodes), set(self.tree.nodes))
        self.assertEqual(selected, ('a', 'b', 'c', 'd'))
        self.assertTrue(self.tree.verify_cover(selected))

    def test_missing_sibling_keeps_parent(self):
        """A single loaded child cannot create a missing region."""
        selected = self.tree.select({'root', 'left', 'right'}, {'root'})
        self.assertEqual(selected, ('left', 'right'))
        selected = self.tree.select({'root', 'left'}, {'root'})
        self.assertEqual(selected, ('root',))

    def test_one_branch_refines_independently(self):
        """A fully resident left branch may refine while right remains coarse."""
        selected = self.tree.select({'root', 'left', 'right', 'a', 'b'},
                                    {'root', 'left'})
        self.assertEqual(selected, ('a', 'b', 'right'))
        self.assertTrue(self.tree.verify_cover(selected))

    def test_parent_refinement_not_requested(self):
        """Resident children are not forced into a draw without a quality request."""
        self.assertEqual(self.tree.select(set(self.tree.nodes), set()), ('root',))

    def test_missing_root_fails_closed(self):
        """No invisible holes: missing coarse fallback is a contract violation."""
        with self.assertRaises(ValueError):
            self.tree.select({'left', 'right'}, {'root'})

    def test_bad_partitions_rejected(self):
        """Reject gaps, overlaps, missing parents and invalid integer intervals."""
        invalid = [
            [Cluster('r', None, 0, 4), Cluster('a', 'r', 0, 2),
             Cluster('b', 'r', 3, 4)],
            [Cluster('r', None, 0, 4), Cluster('a', 'r', 0, 3),
             Cluster('b', 'r', 2, 4)],
            [Cluster('r', None, 0, 4), Cluster('a', 'r', 0, 3)],
            [Cluster('r', None, 0, 4), Cluster('a', 'missing', 0, 4)],
            [Cluster('r', None, 0, 0)],
            [Cluster('r', None, 0, 4), Cluster('r', None, 4, 8)],
            [Cluster('a', None, 0, 4), Cluster('b', None, 3, 8)],
        ]
        for tree in invalid:
            with self.subTest(tree=tree), self.assertRaises(ValueError):
                ClusterCoverage(tree)

    def test_independent_cover_oracle_rejects_overlap_and_hole(self):
        """Verify drawn interval unions without trusting selection's recursion."""
        self.assertFalse(self.tree.verify_cover(('root', 'left')))
        self.assertFalse(self.tree.verify_cover(('left',)))
        self.assertFalse(self.tree.verify_cover(('left', 'left', 'right')))
        self.assertTrue(self.tree.verify_cover(('left', 'right')))

    def test_random_residency_and_refinement(self):
        """2,000 random cuts preserve exact full-domain coverage."""
        rng = random.Random(5404)
        keys = list(self.tree.nodes)
        for _ in range(2000):
            resident = {'root'} | {k for k in keys if rng.randrange(2)}
            requested = {k for k in keys if rng.randrange(2)}
            selected = self.tree.select(resident, requested)
            self.assertTrue(self.tree.verify_cover(selected))
            self.assertTrue(set(selected) <= resident)

    def test_multiple_roots(self):
        """Disjoint assets each retain independent coarse representations."""
        tree = ClusterCoverage([Cluster('x', None, 0, 2),
                                Cluster('xa', 'x', 0, 1),
                                Cluster('xb', 'x', 1, 2),
                                Cluster('y', None, 10, 12)])
        self.assertEqual(tree.select({'x', 'xa', 'xb', 'y'}, {'x'}),
                         ('xa', 'xb', 'y'))
        self.assertTrue(tree.verify_cover(('xa', 'xb', 'y')))


if __name__ == '__main__':
    unittest.main()

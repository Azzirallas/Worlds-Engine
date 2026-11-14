"""CPU seam-profile and fallback validation, including randomized refinements."""
import random
import unittest
from cluster_coverage_reference import Cluster, ClusterCoverage
from cluster_seam_reference import EdgeProfile, SeamAwareCoverage, Stitch


def edge(x):
    """Create a canonical 2D polyline at one integer domain boundary."""
    return ((x, 0), (x, 10))


def fixture(bad_at=4):
    """Build a three-level interval tree with one deliberately mismatched seam."""
    nodes = [Cluster('root', None, 0, 8), Cluster('left', 'root', 0, 4),
             Cluster('right', 'root', 4, 8), Cluster('a', 'left', 0, 2),
             Cluster('b', 'left', 2, 4), Cluster('c', 'right', 4, 6),
             Cluster('d', 'right', 6, 8)]
    coverage = ClusterCoverage(nodes)
    faces = {n.key: EdgeProfile(edge(n.start), edge(n.end)) for n in nodes}
    # Perturb one edge profile, but only if its specific LOD is drawn.
    p = faces['right']
    faces['right'] = EdgeProfile(((bad_at, 1), (bad_at, 10)), p.right)
    return coverage, faces


class SeamTests(unittest.TestCase):
    """Require exact partition, matching border geometry and safe coarse fallback."""

    def setUp(self):
        """Start with a bad seam between refined left and right representations."""
        cov, faces = fixture()
        self.coverage = cov
        self.faces = faces
        self.seams = SeamAwareCoverage(cov, faces)

    def test_coarsens_refinement_when_border_disagrees(self):
        """A complete interval cover alone cannot authorize an unsafe edge."""
        selected = self.seams.select(self.coverage.nodes, {'root'})
        self.assertEqual(selected.clusters, ('root',))
        self.assertEqual(selected.suppressed, ('root',))

    def test_compatible_children_remain_refined(self):
        """Matching border polylines can be selected at mixed LOD levels."""
        faces = dict(self.faces)
        faces['right'] = EdgeProfile(edge(4), edge(8))
        selector = SeamAwareCoverage(self.coverage, faces)
        out = selector.select(self.coverage.nodes, {'root','left'})
        self.assertEqual(out.clusters, ('a','b','right'))
        self.assertEqual(out.suppressed, ())

    def test_resident_stitch_allows_targeted_mismatched_edge(self):
        """An explicit verified resident stitching proxy permits one exact boundary."""
        stitch = Stitch('join', 'left', 'right', self.faces['left'].right,
                        self.faces['right'].left)
        selector = SeamAwareCoverage(self.coverage, self.faces, [stitch])
        coarse = selector.select(self.coverage.nodes, {'root'})
        fine = selector.select(self.coverage.nodes, {'root'}, {'join'})
        self.assertEqual(coarse.clusters, ('root',))
        self.assertEqual(fine.clusters, ('left', 'right'))
        self.assertEqual(fine.stitches, ('join',))

    def test_stale_stitch_signature_must_not_authorize_edge(self):
        """A stitch for an earlier border version cannot mask a changed seam."""
        old = Stitch('old', 'left','right', edge(4), edge(4))
        selector = SeamAwareCoverage(self.coverage, self.faces, [old])
        out = selector.select(self.coverage.nodes, {'root'}, {'old'})
        self.assertEqual(out.clusters, ('root',))
        self.assertFalse(out.stitches)

    def test_missing_parent_never_draws_children(self):
        """The scene-residency dependency chain must be satisfied before refinement."""
        out = self.seams.select({'root','a','b','right'}, {'root','left'})
        self.assertEqual(out.clusters, ('root',))

    def test_unrepairable_adjacent_roots_fail_closed(self):
        """Root seams without a compatible proxy or stitch cannot be made safe."""
        c = ClusterCoverage([Cluster('x',None,0,4), Cluster('y',None,4,8)])
        faces = {'x':EdgeProfile(edge(0),edge(4)),
                 'y':EdgeProfile(((4,1),(4,10)),edge(8))}
        with self.assertRaises(ValueError):
            SeamAwareCoverage(c, faces).select({'x','y'},set())

    def test_unknown_stitch_fails_closed(self):
        """Unregistered stitch names cannot authorize arbitrary boundary geometry."""
        with self.assertRaises(ValueError):
            self.seams.select(self.coverage.nodes, {'root'}, {'fiction'})

    def test_reject_invalid_geometry_and_stitch_metadata(self):
        """Every cluster must supply canonical, unambiguous integer border samples."""
        for bad in (EdgeProfile(((0.0,0),(0,10)),edge(8)),
                    EdgeProfile(((0,0),),edge(8)),
                    EdgeProfile(((0,0),(0,0)),edge(8))):
            faces = dict(self.faces)
            faces['root'] = bad
            with self.assertRaises(ValueError):
                SeamAwareCoverage(self.coverage, faces)
        with self.assertRaises(ValueError):
            SeamAwareCoverage(self.coverage, {'root':self.faces['root']})
        with self.assertRaises(ValueError):
            SeamAwareCoverage(self.coverage, self.faces,
                              [Stitch('bad','root','d',edge(8),edge(8))])

    def test_internal_sibling_mismatch_coarsens_only_one_branch(self):
        """A bad deep seam can preserve independently safe detail elsewhere."""
        faces = {k: EdgeProfile(edge(n.start),edge(n.end))
                 for k,n in self.coverage.nodes.items()}
        faces['b'] = EdgeProfile(((2,2),(2,10)),edge(4))
        selector = SeamAwareCoverage(self.coverage, faces)
        out = selector.select(self.coverage.nodes, {'root','left','right'})
        self.assertEqual(out.clusters, ('left','c','d'))
        self.assertTrue(self.coverage.verify_cover(out.clusters))
        self.assertIn('left', out.suppressed)

    def test_two_thousand_randomized_refinement_and_residency_masks(self):
        """All choices remain exactly covered and seam-safe under random page loss."""
        rng = random.Random(54102)
        keys = tuple(self.coverage.nodes)
        for _ in range(2000):
            resident = {'root'} | {k for k in keys if rng.randrange(2)}
            requested = {k for k in keys if rng.randrange(2)}
            out = self.seams.select(resident, requested)
            self.assertTrue(self.coverage.verify_cover(out.clusters))
            self.assertFalse(self.seams.mismatches(out.clusters))
            self.assertTrue(set(out.clusters) <= resident)


if __name__ == '__main__':
    unittest.main()

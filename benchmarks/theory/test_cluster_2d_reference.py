"""CPU-only 2D exact-cover, profile, stitch, and randomized refinement tests."""
import random
import unittest
from dataclasses import replace
from cluster_2d_reference import (Patch, Borders, Stitch2D, Patch2DCoverage,
                                  flat_borders)


def build():
    """Create a root, four quadrants, and two split southwestern children."""
    pages = [Patch('root',None,0,0,8,8),
             Patch('sw','root',0,0,4,4),Patch('se','root',4,0,8,4),
             Patch('nw','root',0,4,4,8),Patch('ne','root',4,4,8,8),
             Patch('swl','sw',0,0,2,4),Patch('swr','sw',2,0,4,4)]
    return pages, {p.key:flat_borders(p) for p in pages}


class PatchTests(unittest.TestCase):
    """Check complete rectangular ownership and disallow unsafe boundary changes."""

    def setUp(self):
        """Build one fully compatible two-level rectangular cluster scene."""
        self.pages,self.borders = build()
        self.s = Patch2DCoverage(self.pages,self.borders)
        self.all = set(self.s.nodes)

    def test_root_is_complete_coarse_fallback(self):
        """An unrefined resident root covers all 64 integer area cells."""
        self.assertEqual(self.s.select({'root'},self.all).patches,('root',))
        self.assertTrue(self.s.verify_cover(('root',)))

    def test_complete_quadrant_split(self):
        """One whole 2D partition must not produce missing coverage."""
        out=self.s.select(self.all,{'root'})
        self.assertEqual(out.patches,('sw','se','nw','ne'))
        self.assertEqual(self.s.seams(out.patches),((),()))
        self.assertTrue(self.s.verify_cover(out.patches))

    def test_one_region_refines_and_neighbors_remain_coarse(self):
        """T-shaped boundaries can work when the bordering vertices match exactly."""
        out=self.s.select(self.all,{'root','sw'})
        self.assertEqual(out.patches,('swl','swr','se','nw','ne'))
        self.assertTrue(self.s.verify_cover(out.patches))
        self.assertFalse(self.s.seams(out.patches)[0])

    def test_partial_children_never_replace_parent(self):
        """A partial resident quadrant keeps the root instead of making a hole."""
        out=self.s.select({'root','sw','se','ne'},self.all)
        self.assertEqual(out.patches,('root',))

    def test_missing_intermediate_parent_blocks_grandchild(self):
        """No grandchild is drawable if the required parent page is missing."""
        out=self.s.select(self.all-{'sw'},self.all)
        self.assertEqual(out.patches,('root',))

    def test_invalid_partition_gaps_overlaps_and_out_of_parent(self):
        """Exact rectangle ownership fails on missing or multiply owned cells."""
        root=Patch('r',None,0,0,4,4)
        cases=[ [root,Patch('a','r',0,0,2,4),Patch('b','r',3,0,4,4)],
                [root,Patch('a','r',0,0,3,4),Patch('b','r',2,0,4,4)],
                [root,Patch('a','r',0,0,5,4)],
                [root,Patch('a','r',0,0,4,2)],
                [root,Patch('a','r',0,0,4,4),Patch('b','r',0,0,4,4)]]
        for pages in cases:
            with self.subTest(pages=pages),self.assertRaises(ValueError):
                Patch2DCoverage(pages,{p.key:flat_borders(p) for p in pages})

    def test_independent_oracle_rejects_overlap_hole_and_duplicates(self):
        """A separate grid-cell oracle catches malformed draw lists."""
        self.assertFalse(self.s.verify_cover(('root','sw')))
        self.assertFalse(self.s.verify_cover(('sw','se','nw')))
        self.assertFalse(self.s.verify_cover(('sw','sw','se','nw','ne')))
        self.assertFalse(self.s.verify_cover(('fiction',)))

    def test_edge_height_mismatch_coarsens_only_requested_root(self):
        """A bad seam suppresses the unsafe split instead of drawing cracks."""
        profiles=dict(self.borders)
        p=profiles['se']
        profiles['se']=replace(p,left=((0,0),(1,0),(2,2),(3,0),(4,0)))
        s=Patch2DCoverage(self.pages,profiles)
        out=s.select(self.all,{'root','sw'})
        self.assertEqual(out.patches,('root',))
        self.assertIn('root',out.suppressed)
        self.assertTrue(s.verify_cover(out.patches))

    def test_t_junction_missing_vertex_forces_safe_coarsening(self):
        """Collinear geometric position alone does not justify a T junction."""
        profiles=dict(self.borders)
        profiles['se']=replace(profiles['se'],left=((0,0),(4,0)))
        s=Patch2DCoverage(self.pages,profiles)
        self.assertEqual(s.select(self.all,{'root'}).patches,('root',))

    def test_stitch_can_certify_current_edge_only(self):
        """A resident stitch permits one exact pair of disagreeing signatures."""
        profiles=dict(self.borders)
        custom=((0,0),(1,0),(2,2),(3,0),(4,0))
        profiles['se']=replace(profiles['se'],left=custom)
        stitch=Stitch2D('seam','sw','se','x',0,4,profiles['sw'].right,custom)
        s=Patch2DCoverage(self.pages,profiles,[stitch])
        self.assertEqual(s.select(self.all,{'root'},{'seam'}).patches,('sw','se','nw','ne'))
        self.assertIn('seam',s.select(self.all,{'root'},{'seam'}).stitches)
        wrong=replace(stitch,second_profile=((0,0),(4,0)))
        stale=Patch2DCoverage(self.pages,profiles,[wrong])
        self.assertEqual(stale.select(self.all,{'root'},{'seam'}).patches,('root',))

    def test_multiple_disjoint_root_adjacency_fails_closed(self):
        """Adjacent but irreparably mismatched roots cannot silently disappear."""
        a=Patch('a',None,0,0,4,4);b=Patch('b',None,4,0,8,4)
        profiles={'a':flat_borders(a),'b':replace(flat_borders(b),left=((0,0),(4,0)))}
        s=Patch2DCoverage([a,b],profiles)
        with self.assertRaises(ValueError):
            s.select({'a','b'},{'a','b'})

    def test_signature_validation_and_unknown_stitch(self):
        """Malformed metadata and unregistered stitches are rejected explicitly."""
        profiles=dict(self.borders)
        profiles['root']=replace(profiles['root'],right=((0,0),(8.0,0)))
        with self.assertRaises(ValueError):
            Patch2DCoverage(self.pages,profiles)
        with self.assertRaises(ValueError):
            self.s.select(self.all,{'root'},{'unknown'})

    def test_randomized_full_cover_and_shared_edge_safety(self):
        """Two thousand random masks preserve complete 2D coverage and exact seams."""
        rng=random.Random(23013)
        for _ in range(2000):
            resident={'root'} | {key for key in self.s.nodes if rng.randrange(2)}
            requested={key for key in self.s.nodes if rng.randrange(2)}
            out=self.s.select(resident,requested)
            self.assertTrue(self.s.verify_cover(out.patches))
            self.assertFalse(self.s.seams(out.patches)[0])
            self.assertTrue(set(out.patches)<=resident)


if __name__ == '__main__':
    unittest.main()

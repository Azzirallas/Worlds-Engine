"""CPU-only 2D patch ownership and conservative shared-border LOD selection.

Rectangles proxy logical coverage, not mesh triangles. Edge signatures proxy
ordered quantized vertex geometry; matching them is not proof of crack-free 3D.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Patch:
    """One integer rectangle with a parent fallback and a stable key."""
    key: str
    parent: str | None
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass(frozen=True)
class Borders:
    """Globally ordered (along-edge coordinate, height) vertex signatures."""
    left: tuple
    right: tuple
    bottom: tuple
    top: tuple


@dataclass(frozen=True)
class Stitch2D:
    """An externally certified connector for one precise edge and source pair."""
    name: str
    first: str
    second: str
    axis: str
    lo: int
    hi: int
    first_profile: tuple
    second_profile: tuple


@dataclass(frozen=True)
class PatchChoice:
    """Complete drawable cover, rejected refinements and used stitch IDs."""
    patches: tuple[str, ...]
    suppressed: tuple[str, ...]
    stitches: tuple[str, ...]


def _overlap(a, b):
    """Return positive-length integer overlap, or None when disjoint."""
    low, high = max(a[0], b[0]), min(a[1], b[1])
    return (low, high) if low < high else None


def _inside(a, b):
    """Test complete rectangle containment including shared boundaries."""
    return b.x0 <= a.x0 and a.x1 <= b.x1 and b.y0 <= a.y0 and a.y1 <= b.y1


def flat_borders(patch, height=0, step=1):
    """Build canonical flat edges; endpoints are always included."""
    if type(height) is not int or type(step) is not int or step < 1:
        raise ValueError('Invalid sample spacing')
    def samples(a, b):
        return tuple((v, height) for v in (list(range(a, b, step)) + [b]))
    return Borders(samples(patch.y0, patch.y1), samples(patch.y0, patch.y1),
                   samples(patch.x0, patch.x1), samples(patch.x0, patch.x1))


class Patch2DCoverage:
    """Validate exact rectangular tiling and select safe resident refinements."""

    def __init__(self, patches, borders, stitches=()):
        """Require parent-first tiling and valid edge ownership metadata."""
        self.nodes, self.children = {}, {}
        for p in patches:
            if (not isinstance(p, Patch) or type(p.key) is not str or not p.key
                    or p.key in self.nodes or any(type(v) is not int for v in
                                                  (p.x0, p.y0, p.x1, p.y1))
                    or p.x0 >= p.x1 or p.y0 >= p.y1
                    or (p.parent is not None and p.parent not in self.nodes)):
                raise ValueError('Invalid, duplicated or out-of-order patch')
            if p.parent is not None and not _inside(p, self.nodes[p.parent]):
                raise ValueError('Child extends beyond its parent rectangle')
            self.nodes[p.key] = p
            self.children[p.key] = []
            if p.parent is not None:
                self.children[p.parent].append(p.key)
        self.roots = tuple(k for k, p in self.nodes.items() if p.parent is None)
        if not self.roots or set(borders) != set(self.nodes):
            raise ValueError('Every patch needs a boundary profile')
        for i, key in enumerate(self.roots):
            a = self.nodes[key]
            for other in self.roots[i+1:]:
                b = self.nodes[other]
                if _overlap((a.x0, a.x1), (b.x0, b.x1)) and _overlap((a.y0, a.y1), (b.y0, b.y1)):
                    raise ValueError('Root rectangles overlap')
        for key, children in self.children.items():
            if children and not self._tiled(self.nodes[key], [self.nodes[c] for c in children]):
                raise ValueError('Children do not partition parent exactly')
        self.borders = dict(borders)
        for key, b in self.borders.items():
            p = self.nodes[key]
            if not isinstance(b, Borders):
                raise ValueError('Invalid boundary profile')
            for side, lo, hi in (('left',p.y0,p.y1),('right',p.y0,p.y1),
                                 ('bottom',p.x0,p.x1),('top',p.x0,p.x1)):
                edge = getattr(b, side)
                if (type(edge) is not tuple or len(edge) < 2
                        or any(type(pt) is not tuple or len(pt) != 2
                               or any(type(value) is not int for value in pt) for pt in edge)
                        or edge[0][0] != lo or edge[-1][0] != hi
                        or any(a[0] >= c[0] for a, c in zip(edge, edge[1:]))):
                    raise ValueError('Invalid ordered border vertices')
        self.stitches = {}
        for s in stitches:
            if (not isinstance(s, Stitch2D) or type(s.name) is not str or not s.name
                    or s.name in self.stitches or s.first not in self.nodes
                    or s.second not in self.nodes or s.axis not in ('x', 'y')
                    or type(s.lo) is not int or type(s.hi) is not int or s.lo >= s.hi
                    or not isinstance(s.first_profile, tuple)
                    or not isinstance(s.second_profile, tuple)):
                raise ValueError('Invalid stitch certificate')
            self.stitches[s.name] = s

    @staticmethod
    def _tiled(parent, parts):
        """Independently count rectangle owners across every compressed grid cell."""
        xs = sorted({parent.x0,parent.x1} | {x for p in parts for x in (p.x0,p.x1)})
        ys = sorted({parent.y0,parent.y1} | {y for p in parts for y in (p.y0,p.y1)})
        for x0,x1 in zip(xs,xs[1:]):
            for y0,y1 in zip(ys,ys[1:]):
                if parent.x0 <= x0 and x1 <= parent.x1 and parent.y0 <= y0 and y1 <= parent.y1:
                    if sum(p.x0 <= x0 and x1 <= p.x1 and p.y0 <= y0 and y1 <= p.y1 for p in parts) != 1:
                        return False
        return True

    def select_cover(self, resident, requested):
        """Refine only complete subtrees with every required ancestor resident."""
        resident, requested = set(resident), set(requested)
        if not resident <= self.nodes.keys() or not requested <= self.nodes.keys():
            raise ValueError('Unknown region')
        if not set(self.roots) <= resident:
            raise ValueError('Missing pinned coarse root')
        def visit(key):
            if key not in resident:
                return None
            if key in requested and self.children[key]:
                children = [visit(c) for c in self.children[key]]
                if all(part is not None for part in children):
                    return tuple(c for part in children for c in part)
            return (key,)
        return tuple(c for root in self.roots for c in visit(root))

    def verify_cover(self, selection):
        """Verify exact selected rectangle coverage independent of selection logic."""
        selection = tuple(selection)
        if len(selection) != len(set(selection)) or not set(selection) <= self.nodes.keys():
            return False
        for root in self.roots:
            p = self.nodes[root]
            parts = [self.nodes[k] for k in selection if _inside(self.nodes[k], p)]
            if not self._tiled(p, parts):
                return False
        return True

    @staticmethod
    def _slice(edge, lo, hi):
        """Return exact vertex subrange; missing split vertices are T-junction risks."""
        result = tuple(p for p in edge if lo <= p[0] <= hi)
        return result if result and result[0][0] == lo and result[-1][0] == hi else None

    def _adjacent(self, a, b):
        """Return ordered shared-border fields for an edge overlap of positive length."""
        for first, second in ((a,b),(b,a)):
            if first.x1 == second.x0:
                span = _overlap((first.y0,first.y1),(second.y0,second.y1))
                if span:
                    return first.key,second.key,'x',span,'right','left'
            if first.y1 == second.y0:
                span = _overlap((first.x0,first.x1),(second.x0,second.x1))
                if span:
                    return first.key,second.key,'y',span,'top','bottom'
        return None

    def seams(self, selected, resident_stitches=()):
        """Report every unsupported overlap seam and exact matching stitch IDs."""
        selected = tuple(selected)
        resident_stitches = set(resident_stitches)
        if not self.verify_cover(selected) or not resident_stitches <= self.stitches.keys():
            raise ValueError('Invalid selection or stitch residency')
        failed, used = [], []
        for i, ka in enumerate(selected):
            for kb in selected[i+1:]:
                info = self._adjacent(self.nodes[ka],self.nodes[kb])
                if info is None:
                    continue
                a,b,axis,(lo,hi),sa,sb = info
                pa = self._slice(getattr(self.borders[a],sa),lo,hi)
                pb = self._slice(getattr(self.borders[b],sb),lo,hi)
                if pa is not None and pa == pb:
                    continue
                match = next((s.name for s in self.stitches.values()
                              if s.name in resident_stitches and s.first == a and s.second == b
                              and s.axis == axis and s.lo == lo and s.hi == hi
                              and pa == s.first_profile and pb == s.second_profile),None)
                if match is None:
                    failed.append((a,b,axis,lo,hi))
                else:
                    used.append(match)
        return tuple(failed), tuple(sorted(set(used)))

    def _depth(self, key):
        """Count parent links for deterministic smallest-area coarsening."""
        depth = 0
        while self.nodes[key].parent is not None:
            depth += 1
            key = self.nodes[key].parent
        return depth

    def select(self, resident, requested, resident_stitches=()):
        """Repeat exact-cover selection until all borders match or fail closed."""
        requested = set(requested)
        suppressed = []
        for _ in range(len(requested)+1):
            chosen = self.select_cover(resident,requested)
            failed,used = self.seams(chosen,resident_stitches)
            if not failed:
                return PatchChoice(chosen,tuple(suppressed),used)
            a,b,*_ = failed[0]
            eligible=[]
            for key in (a,b):
                ancestor = self.nodes[key].parent
                while ancestor is not None:
                    if ancestor in requested:
                        eligible.append((self._depth(ancestor),ancestor))
                        break
                    ancestor = self.nodes[ancestor].parent
            if not eligible:
                raise ValueError('Incompatible coarse-root seam: no safe refinement')
            d = max(depth for depth,_ in eligible)
            drop = min(key for depth,key in eligible if depth == d)
            requested.remove(drop)
            suppressed.append(drop)
        raise AssertionError('Seam refinement suppression failed to converge')

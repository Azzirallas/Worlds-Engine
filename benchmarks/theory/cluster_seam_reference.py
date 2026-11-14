"""CPU-only seam compatibility filter for exact-coverage cluster selections.

A seam is an ordered quantized shared-edge polyline, not actual triangle geometry.
Unknown/mismatched seams trigger coarsening; optional resident stitches must match
both current edge signatures. No native geometry or GPU drawing is performed.
"""
from dataclasses import dataclass
from cluster_coverage_reference import ClusterCoverage


@dataclass(frozen=True)
class EdgeProfile:
    """Canonical global-order boundary samples for a cluster's two region edges."""
    left: tuple[tuple[int, int], ...]
    right: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Stitch:
    """Certified proxy stitch for one pair of specific cluster edge profiles."""
    name: str
    left: str
    right: str
    left_edge: tuple[tuple[int, int], ...]
    right_edge: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class SeamSelection:
    """Covered compatible clusters and refinement requests suppressed for safety."""
    clusters: tuple[str, ...]
    suppressed: tuple[str, ...]
    stitches: tuple[str, ...]


def _valid_edge(edge):
    """Check canonical integer samples, avoiding tolerant float comparisons."""
    return (type(edge) is tuple and len(edge) >= 2
            and all(type(p) is tuple and len(p) == 2
                    and all(type(v) is int for v in p) for p in edge)
            and len(set(edge)) == len(edge))


class SeamAwareCoverage:
    """Choose only covers with exact signatures or registered resident stitches."""

    def __init__(self, coverage, profiles, stitches=()):
        """Bind one immutable boundary pair per cluster and validate stitch keys."""
        if not isinstance(coverage, ClusterCoverage) or set(profiles) != set(coverage.nodes):
            raise ValueError('Every cluster requires a boundary profile')
        if any(not isinstance(p, EdgeProfile) or not _valid_edge(p.left)
               or not _valid_edge(p.right) for p in profiles.values()):
            raise ValueError('Invalid seam boundary samples')
        self.coverage = coverage
        self.profiles = dict(profiles)
        self.stitches = {}
        for stitch in stitches:
            if (not isinstance(stitch, Stitch) or type(stitch.name) is not str
                    or not stitch.name or stitch.name in self.stitches
                    or stitch.left not in coverage.nodes or stitch.right not in coverage.nodes
                    or not _valid_edge(stitch.left_edge) or not _valid_edge(stitch.right_edge)
                    or coverage.nodes[stitch.left].end != coverage.nodes[stitch.right].start):
                raise ValueError('Invalid seam stitch')
            self.stitches[stitch.name] = stitch

    def _seams(self, selected, resident_stitches):
        """Return unsafe adjacency pairs plus the certified resident stitch IDs."""
        if not self.coverage.verify_cover(selected):
            raise ValueError('Seam input lacks exact region coverage')
        if not resident_stitches <= self.stitches.keys():
            raise ValueError('Unknown resident stitch')
        sorted_keys = sorted(selected, key=lambda k: (self.coverage.nodes[k].start, k))
        invalid, used = [], []
        for a, b in zip(sorted_keys, sorted_keys[1:]):
            if self.coverage.nodes[a].end != self.coverage.nodes[b].start:
                continue  # Gaps between separate asset roots are not adjoining edges.
            pa, pb = self.profiles[a].right, self.profiles[b].left
            if pa == pb:
                continue
            matched = next((s.name for s in self.stitches.values()
                            if s.name in resident_stitches and s.left == a and s.right == b
                            and s.left_edge == pa and s.right_edge == pb), None)
            if matched is None:
                invalid.append((a, b))
            else:
                used.append(matched)
        return tuple(invalid), tuple(used)

    def mismatches(self, selected, resident_stitches=()):
        """Identify every unsupported edge in an otherwise complete selection."""
        return self._seams(tuple(selected), set(resident_stitches))[0]

    def select(self, resident, requested, resident_stitches=()):
        """Drop the smallest selected refinement until all shared edges are safe."""
        requested = set(requested)
        available_stitches = set(resident_stitches)
        # Selection itself validates unknown/missing cluster identities and roots.
        suppressed = []
        for _ in range(len(requested) + 1):
            selected = self.coverage.select(resident, requested)
            mismatch, used = self._seams(selected, available_stitches)
            if not mismatch:
                return SeamSelection(selected, tuple(suppressed), used)
            left, right = mismatch[0]
            candidates = []
            for key in (left, right):
                ancestor = self.coverage.nodes[key].parent
                while ancestor is not None:
                    if ancestor in requested:
                        candidates.append((self._depth(ancestor), ancestor))
                        break
                    ancestor = self.coverage.nodes[ancestor].parent
            if not candidates:
                raise ValueError('No safe resident fallback across root boundary')
            # Prefer narrowing one side before discarding a wider root refinement.
            depth = max(d for d, _ in candidates)
            chosen = min(k for d, k in candidates if d == depth)
            requested.remove(chosen)
            suppressed.append(chosen)
        raise AssertionError('Seam coarsening did not converge')

    def _depth(self, key):
        """Count hierarchy levels to favor the smallest possible coarsening."""
        depth = 0
        while self.coverage.nodes[key].parent is not None:
            depth += 1
            key = self.coverage.nodes[key].parent
        return depth

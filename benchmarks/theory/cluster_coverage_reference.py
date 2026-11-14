"""CPU-only adaptive cluster coverage contract; no GPU, meshlets or draw calls.

A complete visible region is represented by exactly one resident ancestor or
by all of its resident descendants. Partial children never replace a parent.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Cluster:
    """A hierarchy node with an exact integer coverage interval."""
    key: str
    parent: str | None
    start: int
    end: int


class ClusterCoverage:
    """Validate exact child partitions and select safe drawable leaf clusters."""

    def __init__(self, clusters):
        """Require parent-first construction, no gaps, no overlaps and unique IDs."""
        self.nodes = {}
        self.children = {}
        for c in clusters:
            if (not isinstance(c, Cluster) or not isinstance(c.key, str)
                    or not c.key or c.key in self.nodes or type(c.start) is not int
                    or type(c.end) is not int or c.start < 0 or c.end <= c.start):
                raise ValueError("Invalid cluster")
            if c.parent is not None and c.parent not in self.nodes:
                raise ValueError("Parent must precede child")
            self.nodes[c.key] = c
            self.children[c.key] = []
            if c.parent is not None:
                self.children[c.parent].append(c.key)
        self.roots = tuple(k for k, c in self.nodes.items() if c.parent is None)
        if not self.roots:
            raise ValueError("At least one coarse root required")
        for key, kids in self.children.items():
            if not kids:
                continue
            parent = self.nodes[key]
            cursor = parent.start
            for child_key in sorted(kids, key=lambda k: self.nodes[k].start):
                child = self.nodes[child_key]
                if child.start != cursor:
                    raise ValueError("Child partition has gap or overlap")
                cursor = child.end
            if cursor != parent.end:
                raise ValueError("Child partition does not cover parent")
        intervals = sorted((self.nodes[k].start, self.nodes[k].end) for k in self.roots)
        for (_, end), (next_start, _) in zip(intervals, intervals[1:]):
            if next_start < end:
                raise ValueError("Roots overlap")

    def select(self, resident, requested):
        """Refine only complete subtrees; return one exact cover per root."""
        resident, requested = set(resident), set(requested)
        if not resident <= self.nodes.keys() or not requested <= self.nodes.keys():
            raise ValueError("Unknown cluster")
        if not set(self.roots) <= resident:
            raise ValueError("Missing permanent coarse root")

        def visit(key):
            kids = self.children[key]
            if kids and key in requested:
                refined = [visit(child) for child in kids]
                if all(part is not None for part in refined):
                    return tuple(k for part in refined for k in part)
            return (key,) if key in resident else None

        result = []
        for root in self.roots:
            part = visit(root)
            if part is None:
                raise ValueError("Uncovered root")
            result.extend(part)
        return tuple(result)

    def verify_cover(self, selected):
        """Independently check exact disjoint interval coverage against roots."""
        selected = tuple(selected)
        if len(set(selected)) != len(selected):
            return False
        expected = sorted((self.nodes[k].start, self.nodes[k].end) for k in self.roots)
        actual = sorted((self.nodes[k].start, self.nodes[k].end) for k in selected
                        if k in self.nodes)
        if len(actual) != len(selected):
            return False
        for (lo, hi) in expected:
            cursor = lo
            for a, b in actual:
                if b <= lo or a >= hi:
                    continue
                if a != cursor or b > hi:
                    return False
                cursor = b
            if cursor != hi:
                return False
        return True

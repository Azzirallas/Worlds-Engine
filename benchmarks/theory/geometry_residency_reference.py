"""CPU-only geometry-page residency and guaranteed coarse-fallback reference.

Geometry-specific, not a replacement for Godot's existing texture streaming.
No real IO, GPU pages, mesh simplification or hardware timings are modeled.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    """One registered geometry representation with a parent fallback."""
    key: str
    size: int
    parent: str | None


@dataclass(frozen=True)
class Step:
    """Single synthetic loading step with exact residency and budget outcomes."""
    loaded: tuple[str, ...]
    evicted: tuple[str, ...]
    upload_bytes: int


class GeometryResidency:
    """Demand-coalescing page scheduler with pinned roots and in-flight holds."""

    def __init__(self, capacity):
        """Initialize a strict maximum for modelled resident geometry bytes."""
        if type(capacity) is not int or capacity <= 0:
            raise ValueError('Invalid geometry residency capacity')
        self.capacity = capacity
        self.pages = {}
        self.resident = set()
        self.used_bytes = 0
        self.refs = {}
        self.last_used = {}
        self.view_epochs = {}
        self.demands = {}
        self.frames = {}
        self.next_frame = 1
        self.clock = 0

    def register(self, key, size, parent=None):
        """Append a parent-first asset page, pinning its root at registration."""
        if (not isinstance(key, str) or not key or key in self.pages
                or type(size) is not int or size <= 0
                or parent is not None and parent not in self.pages):
            raise ValueError('Invalid or duplicate geometry page')
        if parent is None and self.used_bytes + size > self.capacity:
            raise ValueError('Pinned root geometry exceeds residency capacity')
        self.pages[key] = Page(key, size, parent)
        self.refs[key] = 0
        self.last_used[key] = self.clock
        if parent is None:
            self.resident.add(key)
            self.used_bytes += size

    def set_view_epoch(self, view, epoch):
        """Invalidate old camera demand without discarding shared resident data."""
        if not isinstance(view, str) or not view or type(epoch) is not int or epoch < 1:
            raise ValueError('Invalid view identity')
        old = self.view_epochs.get(view, 0)
        if epoch < old:
            return False
        if epoch > old:
            for pair in tuple(self.demands):
                if pair[0] == view:
                    del self.demands[pair]
            self.view_epochs[view] = epoch
        return True

    def request(self, key, view='main', epoch=1, importance=50):
        """Coalesce demands per camera and reject outdated camera epochs."""
        if key not in self.pages or type(importance) is not int or not 0 <= importance <= 100:
            raise ValueError('Unknown page or invalid importance')
        if not self.set_view_epoch(view, epoch):
            return 'STALE_VIEW'
        existing = self.demands.get((view, key))
        if existing is None:
            self.demands[(view, key)] = (epoch, importance, self.clock)
        else:
            self.demands[(view, key)] = (epoch, max(importance, existing[1]), existing[2])
        return 'RESIDENT' if key in self.resident else 'QUEUED'

    def fallback(self, key):
        """Find the nearest resident ancestor; root presence prevents missing meshes."""
        if key not in self.pages:
            raise ValueError('Unknown geometry page')
        cur = key
        while cur not in self.resident:
            cur = self.pages[cur].parent
            if cur is None:
                raise AssertionError('Registered page lost its coarse fallback root')
        self.last_used[cur] = self.clock
        return cur

    def _first_missing(self, key):
        """Select the first absent ancestor after the nearest resident representation."""
        chain = []
        while key not in self.resident:
            chain.append(key)
            key = self.pages[key].parent
        return chain[-1] if chain else None

    def _dependent(self, key):
        """Do not evict a page while any resident child requires its representation."""
        return any(page.parent == key and page.key in self.resident
                   for page in self.pages.values())

    def _ancestor_of(self, candidate, key):
        """Protect every ancestor that the newly loaded page will depend upon."""
        parent = self.pages[key].parent
        while parent is not None:
            if parent == candidate:
                return True
            parent = self.pages[parent].parent
        return False

    def step(self, max_upload_bytes):
        """Load whole dependency-ready pages, evicting only unpinned safe pages."""
        if type(max_upload_bytes) is not int or max_upload_bytes < 0:
            raise ValueError('Invalid per-tick upload budget')
        self.clock += 1
        wanted = {}
        for (_view, key), (_epoch, priority, first_seen) in self.demands.items():
            missing = self._first_missing(key)
            if missing is not None:
                # Aging limits the chance of starving persistent low-priority demand.
                score = priority + min(100, self.clock - first_seen)
                wanted[missing] = max(score, wanted.get(missing, -1))
        loaded, evicted = [], []
        spent = 0
        for key in sorted(wanted, key=lambda k: (-wanted[k], k)):
            page = self.pages[key]
            # Earlier evictions in this same step can invalidate precomputed candidates.
            if page.parent is not None and page.parent not in self.resident:
                continue
            if page.size > max_upload_bytes - spent or page.size > self.capacity:
                continue
            # Decide evictions transactionally; never lower quality unless a load fits.
            needed = max(0, self.used_bytes + page.size - self.capacity)
            candidates = sorted(
                (p for p in self.resident if self.pages[p].parent is not None
                 and self.refs[p] == 0 and not self._dependent(p)
                 and not self._ancestor_of(p, key)),
                key=lambda p: (p in wanted, self.last_used[p], p))
            victims = []
            reclaimed = 0
            for victim in candidates:
                if reclaimed >= needed:
                    break
                victims.append(victim)
                reclaimed += self.pages[victim].size
            if reclaimed < needed:
                continue
            for victim in victims:
                self.resident.remove(victim)
                self.used_bytes -= self.pages[victim].size
                evicted.append(victim)
            self.resident.add(key)
            self.used_bytes += page.size
            self.last_used[key] = self.clock
            loaded.append(key)
            spent += page.size
        return Step(tuple(loaded), tuple(evicted), spent)

    def submit(self, page_keys):
        """Retain all resident page dependencies until an explicit frame completion."""
        refs = set()
        for key in tuple(page_keys):
            if key not in self.pages or key not in self.resident:
                raise ValueError('Cannot draw a nonresident geometry page')
            current = key
            while current is not None:
                if current not in self.resident:
                    raise ValueError('Missing required parent representation')
                refs.add(current)
                current = self.pages[current].parent
        frame = self.next_frame
        self.next_frame += 1
        self.frames[frame] = frozenset(refs)
        for key in refs:
            self.refs[key] += 1
            self.last_used[key] = self.clock
        return frame

    def retire(self, frame):
        """Release every dependency exactly once, including out-of-order completions."""
        if frame not in self.frames:
            raise ValueError('Unknown or already retired frame')
        for key in self.frames.pop(frame):
            self.refs[key] -= 1
            if self.refs[key] < 0:
                raise AssertionError('Page frame-reference underflow')

    def verify(self):
        """Assert modelled byte accounting, parent residency and frame refcounts."""
        assert self.used_bytes == sum(self.pages[k].size for k in self.resident)
        assert 0 <= self.used_bytes <= self.capacity
        for key in self.resident:
            parent = self.pages[key].parent
            assert parent is None or parent in self.resident
        counted = {key: 0 for key in self.pages}
        for frame in self.frames.values():
            for key in frame:
                counted[key] += 1
        assert self.refs == counted
        return True

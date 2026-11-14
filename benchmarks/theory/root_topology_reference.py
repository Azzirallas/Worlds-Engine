"""CPU-only fair-baseline comparison of global and regional coarse geometry roots.

Both topologies share the same initial coarse bytes and per-region quality.
Transfers, frame retirement, cache eviction and draw submissions are simulated.
No real mesh, GPU bandwidth, CPU renderer throughput or Godot API is modeled.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Fixed grid, identical coarse representation size and upload constraints."""
    side: int = 4
    region_coarse_bytes: int = 2
    fine_bytes: int = 12
    resident_budget: int = 88
    upload_budget: int = 24
    transfer_latency: int = 2
    draw_latency: int = 2

    def __post_init__(self):
        """Reject impossible budgets without silently relaxing quality requirements."""
        for name in ('side', 'region_coarse_bytes', 'fine_bytes', 'resident_budget',
                     'upload_budget', 'transfer_latency', 'draw_latency'):
            val = getattr(self, name)
            if type(val) is not int or val < 1:
                raise ValueError(f'Invalid {name}')
        if self.resident_budget < self.coarse_bytes:
            raise ValueError('Cannot retain complete coarse fallback')

    @property
    def region_count(self):
        """Number of equal-area independently addressable regions."""
        return self.side * self.side

    @property
    def coarse_bytes(self):
        """Same total basic-detail bytes for both topologies at startup."""
        return self.region_count * self.region_coarse_bytes


@dataclass(frozen=True)
class Tick:
    """One synthetic frame after completion, scheduling, selection and submission."""
    frame: int
    requested: tuple[int, ...]
    selected_fine: tuple[int, ...]
    fallback_regions: int
    draw_calls: int
    resident_bytes: int
    upload_bytes: int
    evictions: int


class Topology:
    """A global pinned root or multiple independent regional pinned roots."""

    def __init__(self, mode, config=Config()):
        """Retain root coverage immediately and leave detail optional."""
        if mode not in ('global', 'regional'):
            raise ValueError('Unknown topology')
        self.mode, self.c = mode, config
        self.clock = 0
        self.root_split = mode == 'regional'
        self.coarse_loaded = set(range(config.region_count)) if mode == 'regional' else set()
        self.fine_loaded = set()
        self.resident_bytes = config.coarse_bytes
        self.pending = {}  # (kind, region) -> completion frame
        self.held = {}  # fine region -> outstanding frame reference count
        self.frames = {}  # frame ticket -> (retirement frame, selected detail regions)
        self.evictions = self.upload_total = 0
        self.reports = []

    def _retire(self):
        """Release simulated in-flight draw dependencies after completion."""
        for ticket, (due, pages) in tuple(self.frames.items()):
            if due > self.clock:
                continue
            del self.frames[ticket]
            for page in pages:
                self.held[page] -= 1
                if not self.held[page]:
                    del self.held[page]

    def _admit(self, kind, key, demanded):
        """Attempt whole-page publication without preemptively dropping valid detail."""
        size = self.c.region_coarse_bytes if kind == 'coarse' else self.c.fine_bytes
        missing = max(0, self.resident_bytes + size - self.c.resident_budget)
        victims = []
        freed = 0
        for candidate in sorted(self.fine_loaded):
            if freed >= missing:
                break
            if candidate in demanded or candidate in self.held:
                continue
            victims.append(candidate)
            freed += self.c.fine_bytes
        if freed < missing:
            return False
        for victim in victims:
            self.fine_loaded.remove(victim)
            self.resident_bytes -= self.c.fine_bytes
            self.evictions += 1
        if kind == 'coarse':
            self.coarse_loaded.add(key)
        else:
            self.fine_loaded.add(key)
        self.resident_bytes += size
        self.root_split = self.mode == 'regional' or len(self.coarse_loaded) == self.c.region_count
        return True

    def _complete(self, demanded):
        """Complete due synthetic transfers only when current memory hazards permit."""
        for (kind, key), due in tuple(self.pending.items()):
            if due > self.clock:
                continue
            if kind == 'fine' and key not in demanded:
                del self.pending[(kind, key)]
                continue
            if self._admit(kind, key, demanded):
                del self.pending[(kind, key)]

    def _schedule(self, demanded):
        """Reserve at most a full tick's modeled upload bytes, whole pages only."""
        available = self.c.upload_budget
        want_coarse = self.mode == 'global' and bool(demanded) and not self.root_split
        candidates = []
        if want_coarse:
            candidates.extend(('coarse', i) for i in range(self.c.region_count)
                              if i not in self.coarse_loaded)
        elif self.root_split:
            candidates.extend(('fine', i) for i in sorted(demanded)
                              if i not in self.fine_loaded)
        issued = 0
        for kind, key in candidates:
            if (kind, key) in self.pending:
                continue
            size = self.c.region_coarse_bytes if kind == 'coarse' else self.c.fine_bytes
            if size > available:
                continue
            # Individually impossible permanent configurations must not thrash IO.
            pinned = self.c.coarse_bytes
            if kind == 'fine' and self.mode == 'global':
                pinned += self.c.coarse_bytes
            if pinned + size > self.c.resident_budget:
                continue
            available -= size
            issued += size
            self.pending[(kind, key)] = self.clock + self.c.transfer_latency
        self.upload_total += issued
        return issued

    def tick(self, focus):
        """Apply camera demand, async completions, scheduling and frame pinning."""
        requested = set(focus)
        if any(type(k) is not int or k < 0 or k >= self.c.region_count for k in requested):
            raise ValueError('Invalid view region')
        self.clock += 1
        self._retire()
        self._complete(requested)
        issued = self._schedule(requested)
        selected = tuple(sorted(requested & self.fine_loaded)) if self.root_split else ()
        # A fully retained global root remains the cheapest far-view representation.
        count = (self.c.region_count if self.mode == 'regional'
                 or (self.root_split and requested) else 1)
        self.frames[self.clock] = (self.clock + self.c.draw_latency, selected)
        for page in selected:
            self.held[page] = self.held.get(page, 0) + 1
        report = Tick(self.clock, tuple(sorted(requested)), selected,
                      len(requested - set(selected)), count, self.resident_bytes,
                      issued, self.evictions)
        self.reports.append(report)
        self.verify()
        return report

    def verify(self):
        """Independently validate all resident, frame-ref and full-coverage budgets."""
        expected = (self.c.coarse_bytes +
                    (len(self.coarse_loaded) * self.c.region_coarse_bytes if self.mode == 'global' else 0) +
                    len(self.fine_loaded) * self.c.fine_bytes)
        assert expected == self.resident_bytes
        assert self.resident_bytes <= self.c.resident_budget
        assert all(0 <= k < self.c.region_count for k in self.fine_loaded)
        if self.mode == 'global' and self.fine_loaded:
            assert len(self.coarse_loaded) == self.c.region_count
        assert self.root_split == (self.mode == 'regional' or len(self.coarse_loaded) == self.c.region_count)
        refs = {}
        for _, pages in self.frames.values():
            for page in pages:
                refs[page] = refs.get(page, 0) + 1
        assert refs == self.held
        assert self.held.keys() <= self.fine_loaded
        return True


def compare(sequence, config=Config()):
    """Replay identical frame demand on both policies without wall-clock timing."""
    modes = {name: Topology(name, config) for name in ('global', 'regional')}
    for regions in sequence:
        for mode in modes.values():
            mode.tick(regions)
    return modes

"""CPU-only hybrid geometry policy: regional streaming plus optional far proxy.

Model units are synthetic bytes and submission counts, not GPU memory or time.
Regional coarse roots are always resident; an aggregate proxy is dispensable.
"""
from dataclasses import dataclass, replace
from root_topology_reference import Config, Topology


@dataclass(frozen=True)
class HybridStats:
    """Separate aggregate-proxy lifecycle totals from inherited region reports."""
    proxy_bytes: int
    proxy_resident: bool
    proxy_refs: int
    proxy_loads: int
    proxy_evictions: int
    proxy_cancellations: int


class HybridTopology(Topology):
    """Retain independent region roots and stream a replaceable distant proxy."""

    def __init__(self, config=Config(), proxy_bytes=10):
        """Require an aggregate proxy that can coexist with pinned region roots."""
        if type(proxy_bytes) is not int or proxy_bytes <= 0:
            raise ValueError('Invalid aggregate proxy byte size')
        super().__init__('regional', config)
        self.proxy_bytes = proxy_bytes
        self.proxy_resident = False
        self.proxy_frames = {}
        self.proxy_refs = 0
        self.proxy_loads = 0
        self.proxy_evictions = 0
        self.proxy_cancellations = 0
        self.proxy_frames_total = 0

    def _retire(self):
        """Retire both regular fine and aggregate proxy frame references."""
        super()._retire()
        for frame, due in tuple(self.proxy_frames.items()):
            if due <= self.clock:
                del self.proxy_frames[frame]
                self.proxy_refs -= 1

    def _eligible_fines(self, demanded):
        """List safe optional fine pages; never evict a submitted frame page."""
        return [p for p in sorted(self.fine_loaded)
                if p not in demanded and p not in self.held]

    def _admit(self, kind, key, demanded):
        """Transactionally fit a proxy or a new detail page without root eviction."""
        if kind == 'proxy':
            if self.proxy_resident:
                return True
            size = self.proxy_bytes
            missing = max(0, self.resident_bytes + size - self.c.resident_budget)
            victims = self._eligible_fines(demanded)
            count = (missing + self.c.fine_bytes - 1) // self.c.fine_bytes
            if len(victims) < count:
                return False
            for p in victims[:count]:
                self.fine_loaded.remove(p)
                self.resident_bytes -= self.c.fine_bytes
                self.evictions += 1
            self.proxy_resident = True
            self.proxy_loads += 1
            self.resident_bytes += size
            return True
        if kind != 'fine':
            return super()._admit(kind, key, demanded)
        # The base policy needs an extra eviction path for an optional proxy.
        size = self.c.fine_bytes
        missing = max(0, self.resident_bytes + size - self.c.resident_budget)
        can_drop_proxy = self.proxy_resident and self.proxy_refs == 0
        victims = self._eligible_fines(demanded)
        capacity = len(victims) * size + (self.proxy_bytes if can_drop_proxy else 0)
        if capacity < missing:
            return False  # No destructive eviction on a failed fit.
        if missing and can_drop_proxy:
            self.proxy_resident = False
            self.resident_bytes -= self.proxy_bytes
            self.proxy_evictions += 1
        return super()._admit(kind, key, demanded)

    def _complete(self, demanded):
        """Cancel stale far-proxy jobs when the camera requires regional detail."""
        if demanded and ('proxy', 0) in self.pending:
            del self.pending[('proxy', 0)]
            self.proxy_cancellations += 1
        super()._complete(demanded)

    def _schedule(self, demanded):
        """Use the same per-tick upload budget for proxy or regional details."""
        if demanded:
            return super()._schedule(demanded)
        if (self.proxy_resident or ('proxy', 0) in self.pending
                or self.proxy_bytes > self.c.upload_budget
                or self.c.coarse_bytes + self.proxy_bytes > self.c.resident_budget):
            return 0
        self.pending[('proxy', 0)] = self.clock + self.c.transfer_latency
        self.upload_total += self.proxy_bytes
        return self.proxy_bytes

    def tick(self, focus):
        """Return the inherited frame report, substituting one far-proxy draw."""
        report = super().tick(focus)
        if not report.requested and self.proxy_resident:
            self.proxy_frames[self.clock] = self.clock + self.c.draw_latency
            self.proxy_refs += 1
            self.proxy_frames_total += 1
            report = replace(report, draw_calls=1)
            self.reports[-1] = report
        self.verify()
        return report

    def stats(self):
        """Expose optional proxy cost and guarded frame lifetime for comparisons."""
        return HybridStats(self.proxy_bytes, self.proxy_resident, self.proxy_refs,
                           self.proxy_loads, self.proxy_evictions, self.proxy_cancellations)

    def verify(self):
        """Audit every modelled byte, fine-frame hold and aggregate proxy hold."""
        c = self.c
        expected = (c.coarse_bytes + len(self.fine_loaded) * c.fine_bytes
                    + (self.proxy_bytes if self.proxy_resident else 0))
        assert expected == self.resident_bytes <= c.resident_budget
        assert self.root_split and len(self.coarse_loaded) == c.region_count
        refs = {}
        for _, pages in self.frames.values():
            for p in pages:
                refs[p] = refs.get(p, 0) + 1
        assert refs == self.held
        assert self.held.keys() <= self.fine_loaded
        assert self.proxy_refs == len(self.proxy_frames)
        assert not self.proxy_refs or self.proxy_resident
        assert self.proxy_loads >= self.proxy_evictions >= 0
        assert len(self.pending) == len(set(self.pending))
        return True


def compare_three(sequence, config=Config(), proxy_bytes=10):
    """Run identical demand traces on global, regional and hybrid policies."""
    models = {'global': Topology('global', config),
              'regional': Topology('regional', config),
              'hybrid': HybridTopology(config, proxy_bytes)}
    for demands in sequence:
        for model in models.values():
            model.tick(demands)
    return models

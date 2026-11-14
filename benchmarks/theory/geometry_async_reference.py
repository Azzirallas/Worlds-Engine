"""CPU-only asynchronous geometry-page lifecycle and residency reference.

Models completion tickets, bytes and fallback; does not perform IO or GPU work.
"""

from dataclasses import dataclass

UINT32_MAX = (1 << 32) - 1


@dataclass(frozen=True)
class Page:
    """Geometry page identity, parent dependency, size and version."""
    name: str
    size: int
    parent: str | None
    generation: int = 1


@dataclass(frozen=True)
class Ticket:
    """One IO/upload operation that owns a byte reservation until completion."""
    serial: int
    scene_epoch: int
    name: str
    generation: int
    kind: str
    size: int


class AsyncGeometry:
    """Deterministic model with pinned coarse roots and budgeted async stages."""

    def __init__(self, resident_limit, decoded_limit, read_limit, staging_limit):
        """Validate independent resident, decoded, IO, and staging byte limits."""
        values = (resident_limit, decoded_limit, read_limit, staging_limit)
        if any(type(v) is not int or not 0 < v <= UINT32_MAX for v in values):
            raise ValueError("Invalid geometry memory limit")
        self.resident_limit, self.decoded_limit, self.read_limit, self.staging_limit = values
        self.pages = {}
        self.resident = set()
        self.decoded = set()
        self.resident_bytes = self.decoded_bytes = self.read_bytes = self.staging_bytes = 0
        self.reading, self.uploading = {}, {}
        self.demands, self.view_epochs = {}, {}
        self.frames, self.refs = {}, {}
        self.last_used = {}
        self.clock, self.scene_epoch, self.next_ticket, self.next_frame = 0, 1, 1, 1
        self.reset_pending = False
        self.last_evicted = ()

    def _active(self):
        """Prevent new scene operations while old work is draining."""
        if self.reset_pending:
            raise RuntimeError("Scene reset pending")

    def register(self, name, size, parent=None):
        """Register parent-first pages; a root is pinned and charged immediately."""
        self._active()
        if (type(name) is not str or not name or name in self.pages
                or type(size) is not int or not 0 < size <= UINT32_MAX
                or (parent is not None and parent not in self.pages)):
            raise ValueError("Invalid geometry page")
        if parent is None and self.resident_bytes + size > self.resident_limit:
            raise ValueError("Coarse roots exceed resident budget")
        self.pages[name] = Page(name, size, parent)
        self.refs[name], self.last_used[name] = 0, self.clock
        if parent is None:
            self.resident.add(name)
            self.resident_bytes += size

    def set_view_epoch(self, view, epoch):
        """Discard only the superseded view's requests, never shared resident data."""
        self._active()
        if type(view) is not str or not view or type(epoch) is not int or not 1 <= epoch <= UINT32_MAX:
            raise ValueError("Invalid camera epoch")
        old = self.view_epochs.get(view, 0)
        if epoch < old:
            return False
        if epoch > old:
            self.demands = {k: v for k, v in self.demands.items() if k[0] != view}
            self.view_epochs[view] = epoch
            self._prune_decoded()
        return True

    def request(self, name, view="main", epoch=1, priority=50):
        """Aggregate camera demand and retain its original waiting timestamp."""
        self._active()
        if name not in self.pages or type(priority) is not int or not 0 <= priority <= 100:
            raise ValueError("Invalid geometry demand")
        if not self.set_view_epoch(view, epoch):
            return "STALE_VIEW"
        old = self.demands.get((view, name))
        self.demands[(view, name)] = (max(priority, old[0]) if old else priority,
                                      old[1] if old else self.clock)
        self.last_used[name] = self.clock
        return "RESIDENT" if name in self.resident else "QUEUED"

    def _wanted(self):
        """Expand requests into parent dependencies, sharing work across views."""
        wanted = {}
        for (_, name), (priority, first_seen) in self.demands.items():
            score = priority + min(100, self.clock - first_seen)
            while name is not None:
                wanted[name] = max(wanted.get(name, -1), score)
                name = self.pages[name].parent
        return wanted

    def _prune_decoded(self):
        """Free decoded bytes with no remaining view demand."""
        needed = self._wanted()
        for name in tuple(self.decoded):
            if name not in needed or name in self.resident:
                self.decoded.remove(name)
                self.decoded_bytes -= self.pages[name].size

    def fallback(self, name):
        """Return nearest resident ancestor; no registered page may disappear."""
        if name not in self.pages:
            raise ValueError("Unknown page")
        while name not in self.resident:
            name = self.pages[name].parent
            if name is None:
                raise AssertionError("Missing pinned coarse fallback")
        self.last_used[name] = self.clock
        return name

    def _start(self, name, kind):
        """Allocate a never-recycled work ticket and retain its exact version."""
        page = self.pages[name]
        t = Ticket(self.next_ticket, self.scene_epoch, name, page.generation, kind, page.size)
        self.next_ticket += 1
        return t

    def _active_for(self, name, collection):
        """Ignore old-generation work while preserving its reserved bytes."""
        return any(t.name == name and t.scene_epoch == self.scene_epoch
                   and t.generation == self.pages[name].generation
                   for t in collection.values())

    def blocked_reason(self, name):
        """Expose a hard impossible budget before issuing wasteful IO or transfers."""
        if name not in self.pages:
            raise ValueError("Unknown page")
        root_bytes = sum(p.size for p in self.pages.values() if p.parent is None)
        ancestors = []
        current = name
        while current is not None:
            ancestors.append(current)
            current = self.pages[current].parent
        for key in ancestors:
            page = self.pages[key]
            if page.parent is None:
                continue
            if page.size > self.read_limit:
                return "READ_LIMIT"
            if page.size > self.decoded_limit:
                return "DECODED_LIMIT"
            if page.size > self.staging_limit:
                return "STAGING_LIMIT"
            # Pinned roots and the target's nonroot ancestors must coexist.
            required = root_bytes
            current = page.parent
            while current is not None:
                if self.pages[current].parent is not None:
                    required += self.pages[current].size
                current = self.pages[current].parent
            if required + page.size > self.resident_limit:
                return "RESIDENT_LIMIT"
        return None

    def issue_reads(self, byte_budget):
        """Start whole-page simulated IO within both per-call and in-flight caps."""
        self._active()
        if type(byte_budget) is not int or byte_budget < 0:
            raise ValueError("Invalid read budget")
        self.clock += 1
        wanted = self._wanted()
        started, spent = [], 0
        for name in sorted(wanted, key=lambda n: (-wanted[n], self._depth(n), n)):
            p = self.pages[name]
            if (name in self.resident or name in self.decoded
                    or self.blocked_reason(name) is not None
                    or self._active_for(name, self.reading)
                    or self._active_for(name, self.uploading)):
                continue
            if p.size > byte_budget - spent or p.size > self.read_limit - self.read_bytes:
                continue
            t = self._start(name, "read")
            self.reading[t.serial] = t
            self.read_bytes += p.size
            spent += p.size
            started.append(t)
        return tuple(started)

    def _depth(self, name):
        """Bias equally important work toward prerequisite pages."""
        count = 0
        while self.pages[name].parent is not None:
            name = self.pages[name].parent
            count += 1
        return count

    def _finish(self, ticket, collection, kind):
        """Reject forged/duplicate completion without altering reservations."""
        if not isinstance(ticket, Ticket) or ticket.kind != kind or collection.get(ticket.serial) != ticket:
            raise ValueError("Unknown or already completed work ticket")
        del collection[ticket.serial]
        return (ticket.scene_epoch == self.scene_epoch
                and self.pages[ticket.name].generation == ticket.generation)

    def complete_read(self, ticket, success=True):
        """Release IO memory and retain decoded bytes only for current demand."""
        if type(success) is not bool:
            raise ValueError("Invalid read completion")
        current = self._finish(ticket, self.reading, "read")
        self.read_bytes -= ticket.size
        if self.reset_pending:
            return "CANCELLED_RESET"
        if not current:
            return "STALE"
        if ticket.name not in self._wanted():
            return "CANCELLED_VIEW"
        if not success:
            return "FAILED"
        if ticket.name in self.resident:
            return "RESIDENT"
        if ticket.name in self.decoded:
            return "DUPLICATE"
        self._prune_decoded()
        if ticket.size > self.decoded_limit - self.decoded_bytes:
            return "CPU_BUDGET"
        self.decoded.add(ticket.name)
        self.decoded_bytes += ticket.size
        return "DECODED"

    def issue_uploads(self, byte_budget):
        """Begin dependency-ready simulated transfers from immutable decoded pages."""
        self._active()
        if type(byte_budget) is not int or byte_budget < 0:
            raise ValueError("Invalid upload budget")
        self.clock += 1
        wanted = self._wanted()
        started, spent = [], 0
        for name in sorted(self.decoded, key=lambda n: (-wanted.get(n, -1), n)):
            page = self.pages[name]
            if (name not in wanted or name in self.resident
                    or self.blocked_reason(name) is not None
                    or page.parent not in self.resident
                    or self._active_for(name, self.uploading)):
                continue
            if page.size > byte_budget - spent or page.size > self.staging_limit - self.staging_bytes:
                continue
            t = self._start(name, "upload")
            self.uploading[t.serial] = t
            self.staging_bytes += t.size
            spent += t.size
            started.append(t)
        return tuple(started)

    def _ancestor(self, possible_parent, child):
        """Reject evictions of any parent needed by a new page."""
        parent = self.pages[child].parent
        while parent is not None:
            if parent == possible_parent:
                return True
            parent = self.pages[parent].parent
        return False

    def _needed_by_resident(self, name):
        """A live child must never lose a parent after a page eviction."""
        return any(p.parent == name and p.name in self.resident for p in self.pages.values())

    def _commit(self, name):
        """Plan and apply page eviction atomically only when a full load fits."""
        page = self.pages[name]
        if name in self.resident:
            return ()
        if page.parent not in self.resident:
            return None
        missing = max(0, self.resident_bytes + page.size - self.resident_limit)
        wanted = self._wanted()
        candidates = sorted((key for key in self.resident
                             if self.pages[key].parent is not None and self.refs[key] == 0
                             and not self._needed_by_resident(key)
                             and not self._ancestor(key, name)),
                            key=lambda k: (k in wanted, self.last_used[k], k))
        victims, released = [], 0
        for candidate in candidates:
            if released >= missing:
                break
            victims.append(candidate)
            released += self.pages[candidate].size
        if released < missing:
            return None
        for victim in victims:
            self.resident.remove(victim)
            self.resident_bytes -= self.pages[victim].size
        self.resident.add(name)
        self.resident_bytes += page.size
        self.last_used[name] = self.clock
        return tuple(victims)

    def complete_upload(self, ticket, success=True):
        """Commit only current, demanded pages after successful simulated transfer."""
        if type(success) is not bool:
            raise ValueError("Invalid upload completion")
        current = self._finish(ticket, self.uploading, "upload")
        self.staging_bytes -= ticket.size
        self.last_evicted = ()
        if self.reset_pending:
            return "CANCELLED_RESET"
        if not current:
            return "STALE"
        if ticket.name not in self._wanted():
            self._prune_decoded()
            return "CANCELLED_VIEW"
        if not success:
            return "FAILED"
        victims = self._commit(ticket.name)
        if victims is None:
            return "WAIT_CAPACITY"  # Keep decoded bytes for a later retry.
        self.last_evicted = victims
        self._prune_decoded()
        return "RESIDENT"

    def submit(self, names):
        """Hold each selected page and all ancestors until explicit frame retirement."""
        self._active()
        hold = set()
        for name in tuple(names):
            if name not in self.resident:
                raise ValueError("Draw requires resident geometry")
            current = name
            while current is not None:
                if current not in self.resident:
                    raise ValueError("Draw lost parent dependency")
                hold.add(current)
                current = self.pages[current].parent
        frame = self.next_frame
        self.next_frame += 1
        self.frames[frame] = frozenset(hold)
        for name in hold:
            self.refs[name] += 1
            self.last_used[name] = self.clock
        return frame

    def retire(self, frame):
        """Release exactly one submitted frame's residency references."""
        if frame not in self.frames:
            raise ValueError("Unknown or already retired draw frame")
        for name in self.frames.pop(frame):
            self.refs[name] -= 1
            if self.refs[name] < 0:
                raise AssertionError("Geometry page reference underflow")

    def hot_reload(self, name):
        """Invalidate a nonroot page subtree without replacing in-flight draw data."""
        self._active()
        if name not in self.pages or self.pages[name].parent is None:
            raise ValueError("Hot reload requires a nonroot page")
        subtree = {key for key in self.pages if key == name or self._ancestor(name, key)}
        if any(self.refs[key] for key in subtree):
            return "BUSY_FRAME"
        if any(self.pages[key].generation == UINT32_MAX for key in subtree):
            return "GENERATION_EXHAUSTED"
        for key in subtree:
            p = self.pages[key]
            self.pages[key] = Page(key, p.size, p.parent, p.generation + 1)
            if key in self.resident:
                self.resident.remove(key)
                self.resident_bytes -= p.size
            if key in self.decoded:
                self.decoded.remove(key)
                self.decoded_bytes -= p.size
        return "INVALIDATED"  # Old work retains reservations until ack.

    def begin_reset(self):
        """Stop new requests and discard decoded data, keeping in-flight reservations."""
        self._active()
        if self.scene_epoch == UINT32_MAX:
            raise RuntimeError("Scene epoch exhausted")
        self.reset_pending = True
        self.demands.clear()
        self.decoded.clear()
        self.decoded_bytes = 0

    def complete_reset(self):
        """Recreate pinned roots only after IO, uploads and draws have drained."""
        if not self.reset_pending:
            raise RuntimeError("No reset pending")
        if self.reading or self.uploading or self.frames:
            raise RuntimeError("Scene references remain in flight")
        self.scene_epoch += 1
        self.resident = {n for n, p in self.pages.items() if p.parent is None}
        self.resident_bytes = sum(self.pages[n].size for n in self.resident)
        self.pages = {n: Page(p.name, p.size, p.parent) for n, p in self.pages.items()}
        self.refs = {n: 0 for n in self.pages}
        self.last_used = {n: self.clock for n in self.pages}
        self.view_epochs.clear()
        self.last_evicted = ()
        self.reset_pending = False

    def verify(self):
        """Independently recompute all memory counters, hierarchy and frame holds."""
        assert self.resident_bytes == sum(self.pages[n].size for n in self.resident)
        assert self.decoded_bytes == sum(self.pages[n].size for n in self.decoded)
        assert self.read_bytes == sum(t.size for t in self.reading.values())
        assert self.staging_bytes == sum(t.size for t in self.uploading.values())
        assert 0 <= self.resident_bytes <= self.resident_limit
        assert 0 <= self.decoded_bytes <= self.decoded_limit
        assert 0 <= self.read_bytes <= self.read_limit
        assert 0 <= self.staging_bytes <= self.staging_limit
        assert not (self.resident & self.decoded)
        for name in self.resident:
            parent = self.pages[name].parent
            assert parent is None or parent in self.resident
        expected = {name: 0 for name in self.pages}
        for holds in self.frames.values():
            for name in holds:
                expected[name] += 1
                assert name in self.resident
        assert self.refs == expected
        return True

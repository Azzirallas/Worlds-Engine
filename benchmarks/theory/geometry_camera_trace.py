"""Deterministic CPU camera traces combining geometry streaming, LOD, 2D seams.

All memory/quality/byte metrics describe a synthetic model, not GPU timing.
"""
from dataclasses import dataclass, replace
from math import hypot, isfinite

from cluster_2d_reference import Patch, Patch2DCoverage, flat_borders
from geometry_async_reference import AsyncGeometry
from geometry_lod_reference import Camera, Level, LODSelector


@dataclass(frozen=True)
class View:
    """One camera's virtual location and screen-error tolerance."""
    name: str
    x: float
    y: float
    distance: float
    budget_px: float = 2.0


@dataclass(frozen=True)
class FrameReport:
    """One frame's complete-cover quality, model memory and flow counters."""
    index: int
    visible: tuple[str, ...]
    missing_quality_area: int
    requested_quality_area: int
    selected_quality_area: int
    excess_quality_area: int
    suppressed_refinements: int
    resident_bytes: int
    decoded_bytes: int
    reading_bytes: int
    staging_bytes: int
    read_bytes_started: int
    upload_bytes_started: int
    pages_became_resident: int
    evictions: int
    cancelled_tickets: int
    active_draws: int


@dataclass(frozen=True)
class TraceReport:
    """An immutable reproducible run with cumulative synthetic telemetry."""
    frames: tuple[FrameReport, ...]
    issued_read_bytes: int
    issued_upload_bytes: int
    loaded_pages: int
    evictions: int
    cancelled_tickets: int
    max_resident_bytes: int
    max_decoded_bytes: int
    max_staging_bytes: int


def build_grid():
    """Construct root, four quadrants and four leaf patches per quadrant."""
    patches = [Patch('root',None,0,0,8,8)]
    for cy in range(2):
        for cx in range(2):
            name = f'q{cx}{cy}'
            x,y = cx*4,cy*4
            patches.append(Patch(name,'root',x,y,x+4,y+4))
    for cy in range(2):
        for cx in range(2):
            parent = f'q{cx}{cy}'
            for dy in range(2):
                for dx in range(2):
                    x,y = cx*4+dx*2,cy*4+dy*2
                    patches.append(Patch(f'{parent}l{dx}{dy}',parent,x,y,x+2,y+2))
    return patches


class CameraTrace:
    """Compose three independently tested CPU reference models per view-frame."""

    def __init__(self, resident_limit=100, decoded_limit=180, read_limit=120,
                 staging_limit=120, read_per_frame=60, upload_per_frame=40,
                 read_latency=2, upload_latency=2, draw_latency=2,
                 damaged_border=False):
        """Configure strict synthetic memory and completion scheduling limits."""
        for value in (read_per_frame,upload_per_frame,read_latency,upload_latency,draw_latency):
            if type(value) is not int or value < 1:
                raise ValueError('Frame budgets and latencies must be positive integers')
        self.patches = build_grid()
        borders = {p.key:flat_borders(p) for p in self.patches}
        if damaged_border:
            key = 'q00l00'
            b = borders[key]
            borders[key] = replace(b,right=((0,0),(1,2),(2,0)))
        self.cover = Patch2DCoverage(self.patches,borders)
        self.stream = AsyncGeometry(resident_limit,decoded_limit,read_limit,staging_limit)
        for patch in self.patches:
            size = 16 if patch.key == 'root' else 12 if patch.parent == 'root' else 9
            self.stream.register(patch.key,size,patch.parent)
        self.lod = LODSelector([Level('L0',None,1.0),Level('L1','L0',0.2),
                                Level('L2','L1',0.01)])
        self.read_budget,self.upload_budget = read_per_frame,upload_per_frame
        self.read_latency,self.upload_latency,self.draw_latency = read_latency,upload_latency,draw_latency
        self.reads, self.uploads, self.draws = [],[],[]
        self.view_epochs = {}
        self.previous = {}
        self.frame_index = 0
        self.log = []
        self.issued_read = self.issued_upload = 0
        self.loaded = self.evicted = self.cancelled = 0

    def _desired(self, view, quadrant):
        """Convert projected geometry error to a requested depth per quadrant."""
        p = self.cover.nodes[quadrant]
        cx,cy = (p.x0+p.x1)/2,(p.y0+p.y1)/2
        distance = hypot(hypot((view.x-cx)*120,(view.y-cy)*120),view.distance)
        cam = Camera(distance,1,viewport_height=1080,perspective_fov_y_deg=60)
        previous = self.previous.get((view.name,quadrant))
        selected = self.lod.choose(cam,view.budget_px,{'L0','L1','L2'},previous)
        self.previous[(view.name,quadrant)] = selected.page
        return self.lod.names.index(selected.page)

    def _quality(self, selected, target):
        """Calculate area-weighted desired versus actual representation detail."""
        missing = desired = actual = excess = 0
        for key in selected:
            patch = self.cover.nodes[key]
            level = 0 if patch.parent is None else (1 if patch.parent == 'root' else 2)
            for q,depth in target.items():
                region = self.cover.nodes[q]
                width = max(0,min(patch.x1,region.x1)-max(patch.x0,region.x0))
                height = max(0,min(patch.y1,region.y1)-max(patch.y0,region.y0))
                area = width*height
                missing += area*max(0,depth-level)
                excess += area*max(0,level-depth)
                desired += area*depth
                actual += area*level
        return missing,desired,actual,excess

    def step(self, views):
        """Advance queued IO/transfer/draw completions and emit a covered frame."""
        views = tuple(views)
        if (not views or any(not isinstance(v, View) or type(v.name) is not str
                             or not v.name or any(type(x) not in (int,float)
                             or not isfinite(x) for x in (v.x,v.y,v.distance,v.budget_px))
                             or v.distance < 0 or v.budget_px <= 0 for v in views)
                or len(set(v.name for v in views)) != len(views)):
            raise ValueError('Expected valid uniquely named camera views')
        self.frame_index += 1
        now = self.frame_index
        for due,frame in tuple(self.draws):
            if due <= now:
                self.stream.retire(frame)
                self.draws.remove((due,frame))
        target = {f'q{cx}{cy}':0 for cx in range(2) for cy in range(2)}
        for view in views:
            if not isinstance(view,View):
                raise ValueError('Expected View')
            epoch=self.view_epochs.get(view.name,0)+1
            self.view_epochs[view.name]=epoch
            self.stream.set_view_epoch(view.name,epoch)
            for q in target:
                target[q]=max(target[q],self._desired(view,q))
        # A root split needs *all* quadrants resident, even for a single near view.
        for view in views:
            epoch=self.view_epochs[view.name]
            if any(depth >= 1 for depth in target.values()):
                for q in target:
                    self.stream.request(q,view.name,epoch,70)
            for q,depth in target.items():
                if depth == 2:
                    for key in self.cover.children[q]:
                        self.stream.request(key,view.name,epoch,95)
        cancelled = pages_loaded = evictions = 0
        for due,ticket in tuple(self.reads):
            if due <= now:
                result=self.stream.complete_read(ticket)
                if result in ('STALE','CANCELLED_VIEW','CANCELLED_RESET'):
                    cancelled += 1
                self.reads.remove((due,ticket))
        for due,ticket in tuple(self.uploads):
            if due <= now:
                result=self.stream.complete_upload(ticket)
                if result == 'RESIDENT':
                    pages_loaded += 1
                    evictions += len(self.stream.last_evicted)
                if result in ('STALE','CANCELLED_VIEW','CANCELLED_RESET'):
                    cancelled += 1
                self.uploads.remove((due,ticket))
        new_reads=self.stream.issue_reads(self.read_budget)
        new_uploads=self.stream.issue_uploads(self.upload_budget)
        self.reads.extend((now+self.read_latency,t) for t in new_reads)
        self.uploads.extend((now+self.upload_latency,t) for t in new_uploads)
        read_bytes=sum(t.size for t in new_reads)
        upload_bytes=sum(t.size for t in new_uploads)
        self.issued_read += read_bytes
        self.issued_upload += upload_bytes
        self.loaded += pages_loaded
        self.evicted += evictions
        self.cancelled += cancelled
        requested=set()
        if any(d>=1 for d in target.values()):
            requested.add('root')
        requested.update(q for q,d in target.items() if d==2)
        chosen=self.cover.select(self.stream.resident,requested)
        assert self.cover.verify_cover(chosen.patches)
        assert not self.cover.seams(chosen.patches)[0]
        missing,desired,actual,excess=self._quality(chosen.patches,target)
        frame_ticket=self.stream.submit(chosen.patches)
        self.draws.append((now+self.draw_latency,frame_ticket))
        assert self.stream.verify()
        report=FrameReport(now,chosen.patches,missing,desired,actual,excess,
                           len(chosen.suppressed),self.stream.resident_bytes,
                           self.stream.decoded_bytes,self.stream.read_bytes,
                           self.stream.staging_bytes,read_bytes,upload_bytes,
                           pages_loaded,evictions,cancelled,len(self.draws))
        self.log.append(report)
        return report

    def run(self, cameras):
        """Evaluate deterministic frames and report aggregate synthetic byte counts."""
        for views in cameras:
            self.step(views)
        return TraceReport(tuple(self.log),self.issued_read,self.issued_upload,
                           self.loaded,self.evicted,self.cancelled,
                           max((f.resident_bytes for f in self.log),default=0),
                           max((f.decoded_bytes for f in self.log),default=0),
                           max((f.staging_bytes for f in self.log),default=0))

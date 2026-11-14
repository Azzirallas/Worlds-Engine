# 30 — Original GPU instance state and visibility system: design specification

**Status:** **source-level specification plus a CPU-only reference implementation; still no GPU/engine prototype.** [45](45-visibility-reference-milestone-and-gpu-gates.md) records the implementation, 14 passing CPU tests and exact Godot RD API verification. [46](46-isolated-gpu-visibility-feasibility-fixture.md) records the isolated GPU-frustum fixture. [47](47-guarded-indirect-and-offscreen-raster-probe.md) adds a guarded GPU indirect packet and optional offscreen raster probe with 13 passing CPU ABI tests. The 12 GPU-source scenarios are **unexecuted**; neither an actual mesh renderer nor a conventional fallback draw is integrated. Built using standard GPU-driven rendering concepts and public Godot interfaces, not a translation of Unreal GPUScene or instance-culling code. Motivated by [29](29-renderer-subsystem-evidence-ledger.md) and [25](25-godot-renderer-gap-matrix.md).

## Precise goal

Reduce *per-frame per-instance CPU work and CPU-to-GPU traffic* when thousands of visual objects share meshes/materials, move at different frequencies, and only a subset contribute to the current view. Unlike a single MultiMesh, enable per-instance coarse visibility and (eventually) per-instance LOD. Continue rendering correctly with standard Godot controls on unsupported hardware.

## Baselines; why these exist

A. Separate ordinary `MeshInstance3D` nodes. B. One very large `MultiMeshInstance3D`. C. Spatially subdivided MultiMeshes with explicit AABBs. D. Experimental GPU-visible-instance path. Also compare C against a classical CPU-built candidate list; there is no guarantee a GPU pass wins.

For instance count `N`, view-visible count `V`, per-frame modifications `M`, our hope is that CPU scheduling costs track **dirty regions + coarse candidates** rather than `N`; GPU work tracks **candidate count** and output detail. No algorithm eliminates every O(N) operation, especially in pathological fully visible scenes.

## Conceptual state (proposed, choose actual ABI later)

`RenderHandle`: integer slot + generation counter. The slot is a temporary GPU presentation identity, not a durable entity ID. Generation bump on slot release prevents accidental stale results.

`InstanceRecord` fields required for first experiment:
- local-to-world transform in GPU-friendly precision (origin-relative if needed);
- conservative local bounding sphere or AABB and derived world radius;
- mesh and material key (first test: both constants);
- visibility flags, region key, optional changed epoch;
- optional previous transform for motion vectors, but defer actual temporal integration.

`RegionRecord`:
- conservative union of instance bounds, members/candidate reference, geometry type;
- current scene epoch and region-content revision;
- per-view visibility state only when safe to reuse.

`ViewRequest`:
- camera clip/frustum, viewport dimensions, projection type, layer flags;
- view generation/epoch and a camera-cut bit;
- optional depth pyramid, used only for a separately validated occlusion variant.

`VisibilityOutput`:
- visible instance indices or an independent compacted ID stream;
- count/indirect dispatch or draw payload compliant with RenderingDevice API;
- overflow indicator and diagnostic counters.

No fixed numeric packing/layout/queue structure is specified from Unreal. Choose layout based on Godot shaders, API alignment rules and benchmark outcomes.

## Frame lifecycle contract

1. **Acquire changes:** on the main thread, collect created/deleted/transformed/flagged presentation objects. No universal per-frame SceneTree walk if it can be avoided.
2. **Coalesce changes:** overwrite repeated changes to same handle within one frame; collect consecutive GPU buffer write ranges where practical; ensure latest generation wins.
3. **Finalize conservative regions:** update bounds and re-home objects that crossed region boundaries; never shrink bounds incorrectly while jobs race.
4. **Build view candidates:** include region list satisfying frustum and layer test; uncertain or recently teleported regions must be included.
5. **Upload:** send dirty records and compact candidate IDs, noting actual bytes/allocations.
6. **GPU visibility:** for each candidate, reject only provably outside frustum/disabled; optionally depth/HZB occlusion in a separate experiment with conservative fallback.
7. **Generate commands:** compact visible IDs, update a standards-compliant indirect draw/dispatch buffer or a CPU-fallback-visible count.
8. **Draw:** one or more material/mesh-compatible groups; fallback when overflow, unsupported feature, or visibility uncertainty.
9. **Recycle safely:** free handles/resources only after outstanding GPU references have retired; temporal buffers don't retain stale handles.
10. **Telemetry:** report counts, CPU stages, compute stages, upload bytes, VRAM and missed/false visible observations.

## Correctness invariants

- **No false-negative visibility:** if a box can intersect frustum, it must remain a candidate. Occlusion tests must use conservative bounds and guard against depth precision uncertainty.
- **Motion and invalidation:** sphere/AABB is expanded for maximum animation displacement or updated conservatively. Camera teleports invalidate history. Fast object movement is never hidden because previous frame thought it was occluded.
- **Stable identity:** generation checks prevent deleted+reused slots from being sampled.
- **Buffer capacity:** never silently drop geometry on overflow; fall back or split batches and increment an explicit counter.
- **Layer selection:** support render layer and visibility mask equivalence; test two cameras with different layers.
- **No undefined visibility reads:** producer compute pass and indirect consumer are ordered with correct barriers via Godot's graph semantics.
- **Multi-view:** results cannot be shared unless geometry and view projection match; start single-view.
- **Thread safety:** no unsynchronized mutation of SceneTree/RenderingServer objects.

## Research variants in increasing difficulty

**V0 — CPU control:** region-bounded MultiMesh; batch transforms using buffer upload where possible; validate harness.

**V1 — GPU frustum-only:** GPU records + conservative bounds; compute compaction + draw. No HZB, no LOD, no temporal history. This isolates the core GPU pipeline.

**V2 — incremental updates:** add dirty records and stable handle lifecycle; static 90% / moving 10%; measure fragmentation.

**V3 — occlusion:** independent depth-pyramid approach with safe fallback, new-visibility conservative policy and camera-cut support.

**V4 — LOD/material selection:** group visibility output by mesh/material/LOD; quantify binning and dispatch overhead.

**V5 — editor + SceneTree bridge:** optional opt-in node/component as presentation provider; standard nodes keep their behavior.

Never begin V4/V5 before V1/V2 are proven useful.

## GPU dispatch algorithm (original conceptual specification, not code)

For each candidate instance, evaluate an inclusion predicate from a conservative transformed bound and view frustum. Store inclusion flags in a bounded GPU array; use a standard parallel prefix-scan/compaction approach or atomic append depending on hardware and contention. Produce draw IDs and a count for an indirect call. Compare variants:
- atomic append (simple, possible contention);
- block prefix-scan + block offsets (more passes, predictable output);
- per-region bins (reduces global contention, increases overhead).

Always compare *total GPU time including compaction + draw* and CPU overhead, not only cull dispatch time. The exact data representation is to be independently chosen from open literature / first-party Godot design.

## Failure experiments

- Empty scene and one instance; 100 instances (must not regress badly).
- 1k / 10k / 100k objects, 10/50/90% visible, small/large radius.
- Camera behind large opaque wall, then turn 180 degrees.
- Jump between faraway viewpoints every frame.
- Delete/recreate 20% while GPU has in-flight frames.
- Move 1%, 25%, 100%, random and spatially clustered changes.
- Expand bounds due to wind/animation and switch material/visibility flags.
- Force tiny buffer cap to verify non-lossy overflow.
- Multiple viewports, though V1 can explicitly reject unsupported multiview.
- Disjoint material groups with different draw modes.

## Proposed integration points to inspect (not approved edits)

- `servers/rendering/rendering_server_default.cpp`: render-thread lifecycle.
- `servers/rendering/renderer_scene_cull.cpp/.h`: existing scene instance inventory/CPU candidate handling.
- `servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp`: MultiMesh records, indirect command storage, buffer uploads.
- `servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp`: material/LOD grouping, draw submission.
- `servers/rendering/rendering_device.cpp/.h` and `rendering_device_graph.cpp/.h`: dispatch, indirect and dependency correctness.
- `scene/resources/multimesh.cpp`: public resource behavior and import considerations.

For the first prototype, **do not edit these files** until a standalone RenderingDevice feasibility test establishes API availability and the baseline measurements demand it.

## Success gate

Measured reduction in total CPU/GPU frame time in defined high-density scenes, no missing geometry or buffer overflow, tolerable RAM/VRAM, and no ruinous slow path for mostly visible scenes. Maintain fallback C (regional MultiMesh) as a default for low instance count and unsupported devices.

Cross-reference: [32 streaming](32-residency-streaming-contract.md), [35 test procedure](35-phase-1-validation-and-next-actions.md).

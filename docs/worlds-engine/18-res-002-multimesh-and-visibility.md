# 18 — RES-002: MultiMesh, instance updates and visibility

**Status:** source-level audit complete for identified functions; runtime experiments **not yet run**. **Inspected source:** `master` at `660bec160a62ba9eab9836bb7349d139c52f5418`, Godot 4.8 beta lineage, 2026-11-13.

## Executive finding

Godot already has GPU instancing, separate spatial indexers, parallel CPU scene culling, CPU-side region-tracked MultiMesh uploads and indirect draw support. We should not recreate these. The measured opportunity may lie in *which instances are considered, how batches are partitioned, how many bytes are updated, and how often bounds are rebuilt*.

## What the source actually does

### 1. Each MultiMesh is one renderable scenario instance

`scene/3d/multimesh_instance_3d.cpp:69-77`: `set_multimesh` binds a resource RID with `set_base`. A large group becomes one geometry instance in the camera scene-cull path, with its own bounds and material/light interactions. Ordinary MultiMesh frustum/occlusion tests operate on this group; the standard API does not expose arbitrary individual visibility.

**Implication:** one huge mesh spanning the world makes visibility inefficient. Spatially sized batches create more culling opportunities at the cost of more scene instances/draw setup. The optimal partition size is workload-dependent.

### 2. Bulk updates use a full-size transform payload

`scene/resources/multimesh.cpp:198-210`: `MultiMesh::set_buffer` requires `instance_count × stride` floats. For 3D transforms, the minimal stride is **12 floats per instance**, with 4 floats added for color and another 4 for custom data. `servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp:2154-2199` issues a corresponding `RenderingDevice::buffer_update` across the provided buffer, with motion-vector considerations.

**Implication:** excellent for replacing all instance state as a batch, but full-array uploads can be wasteful if only a small fraction moved. Do not describe this as the behavior of *all* update APIs.

### 3. Per-instance changes already use dirty-region uploads

`mesh_storage.cpp:1743` sets **`MULTIMESH_DIRTY_REGION_SIZE = 512`**. `mesh_storage.cpp:1928-1964` caches a transform and marks its region dirty. `mesh_storage.cpp:2305-2350` uploads individual dirty regions or switches to a larger contiguous upload when **more than 32 dirty regions** or **more than half of visible regions** are dirty. Motion-vector data introduces additional copy/update paths.

**Implication:** dirty-region tracking is *already implemented* in the RenderingDevice backend. Do not waste time building a second generic dirty-region mechanism. Benchmark how 512-instance granularity affects sparse, spatially concentrated and random movement before proposing modifications.

### 4. A CPU cache may be materialized on the first individual update

`mesh_storage.cpp:1745-1780`: `_multimesh_make_local` establishes a CPU-side instance cache for individual access. If a GPU buffer has already been set and no local cache exists, the source calls `RenderingDevice::buffer_get_data` to populate it. This is a **possible one-time GPU readback/synchronization cost**, depending on call sequence and backend.

**Experiment:** measure transitions from `set_buffer` initialization to the first `set_instance_transform` update. Compare against creating/populating the local cache through per-instance setters from the beginning. Track one-time stalls and steady state separately.

### 5. Bounding boxes may be expensive for animated groups

`mesh_storage.cpp:1860-1903`: when bounds are not custom, `_multimesh_re_create_aabb` iterates each instance and merges its transformed mesh bounds. `mesh_storage.cpp:2305-2364` performs this work when AABB is dirty after processing changed instances. `mesh_storage.cpp:2272-2296` contains custom AABB paths.

**Implication:** for big moving MultiMeshes, AABB rebuilding may have O(visible-instance-count) work even if relatively few transforms change. Test **fixed conservative custom AABBs for stationary geographic regions** against dynamic computed bounds. The fixed bounds must remain correct for movement, elevation, wind/animation extent, teleport and region transfer. Too-large AABBs degrade culling, so test both CPU time and GPU overdraw.

### 6. Indirect draws are real but do not prove GPU culling

`mesh_storage.cpp:1905-1926` allocates indirect command buffers for an indirect MultiMesh. `mesh_storage.cpp:2235-2263` updates instance counts in the command buffer when visibility count changes; this path is CPU-driven. `renderer_rd/forward_clustered/render_forward_clustered.cpp:608-625` and `renderer_rd/forward_mobile/render_forward_mobile.cpp:2731-2748` call `draw_list_draw_indirect` when the indirect flag is set. `rendering_device_driver.h:695-702` and `rendering_device.cpp:6293-6390` expose driver/RenderingDevice indirect mechanisms.

**Implication:** the command infrastructure for future GPU-driven selection exists. However, **a GPU-generated per-instance visibility buffer or indirect count for general MultiMeshes is not proven by these calls**. Trace the producer and any GPU compute passes before claiming that capability.

### 7. Important backend limits

These source findings primarily concern the RD path (Forward+ and Mobile). Compatibility/OpenGL may differ. Backend support for indirect-count draws, compute, ray tracing, and all feature flags must be measured/checked per OS/GPU. The presence of a virtual API method does not guarantee universal support.

## Testable hypotheses (ordered)

| Hypothesis | Why plausible | Counterexample / failure |
| --- | --- | --- |
| H-01: Region-bounded MultiMeshes outperform one huge MultiMesh for partial visibility | Whole-MultiMesh culling and bounds | More draws/scene instances may cost more when nearly all visible |
| H-02: Stable custom AABBs reduce moving-group CPU cost | Current AABB rebuild visits all instances | Conservative bounds can worsen visibility and may be incorrect when migration occurs |
| H-03: Per-instance setters beat full buffers for sparse movement | Existing 512-instance dirty regions | Many touched regions trigger full upload; script calls may dominate |
| H-04: Full-buffer writes beat per-instance setters for dense movement | One bulk call; backend contiguous upload | Full upload plus AABB work may be expensive; motion vectors change cost |
| H-05: GPU visibility + indirect draws beat CPU selection for very large scenes | Indirect draw API already exists | Dispatch/compaction/readback/bandwidth and synchronization may outweigh savings |
| H-06: Candidate-list culling reduces CPU overhead in massive sparse scenes | Current camera path examines scenario instance array | BVH query, memory traversal and list construction could be slower; current parallel loop is cache-friendly |

## Benchmark design — RES-002

At a minimum compare:

- Representations: MeshInstance3D per object; direct RenderingServer objects; one MultiMesh; region MultiMeshes with 16/32/64 world-unit cells; optional more granular groups.
- Scene densities: 1k/10k/100k objects with identical mesh/material and stable seed.
- Camera states: all visible, 10–20% visible, almost all culled, urban occluded, close rapid movement and teleport.
- Movement: 0%, 1%, 25%, 100% per tick; spatially concentrated vs random; keep random sequences identical.
- Update modes: per-instance setters; whole `set_buffer`; cached, conservative custom AABB on/off.
- Rendering: Forward+ first; then Mobile; Compatibility treated separately.
- Quality: shadows off/on, TAA/motion vectors off/on, same resolution and material features.

**Measure:** process/render thread wall time, scene cull time, rendering list construction time, draw calls, GPU frametime, P50/P95/P99, CPU update time, buffer upload bytes/calls, AABB rebuild calls/time, peak RAM/VRAM. Use build configuration and profiling markers to separate CPU vs GPU limited scenes.

## Recommended first experiment

Run **static visibility and moving-instance AABB experiments** before adding GPU compute. Those use the existing engine unchanged and answer whether the dominant cost is coarse culling, CPU scene scanning, dirty uploads or bounds generation.

## What is not yet established

No benchmark has run. No numeric performance claim is justified. No automatic GPU compaction has been confirmed. No renderer rewrite, meshlet engine or alternative spatial index is approved. All conclusions are hypotheses until tested.

## Source links

- [MultiMesh instance bridge](../../scene/3d/multimesh_instance_3d.cpp)
- [MultiMesh resource](../../scene/resources/multimesh.cpp)
- [RD mesh storage](../../servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp)
- [Forward+ draws](../../servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp)
- [Mobile draws](../../servers/rendering/renderer_rd/forward_mobile/render_forward_mobile.cpp)
- [RenderingDevice draw API](../../servers/rendering/rendering_device.cpp)
- [RenderingDevice driver](../../servers/rendering/rendering_device_driver.h)

# 17 — RES-001: Initial rendering source audit

**Status:** first-pass source tracing completed; benchmark and deeper call-graph analysis pending. **Date:** 2026-11-13. **Source:** Worlds-Engine master at initial audit commit `c6711d9bc72e2e7f5c111492d70954b30a21a8c9` (Godot 4.8 beta lineage). All findings are from inspected source, not a runtime profile.

## Confirmed source entry points

| Layer | Source | Confirmed behavior / evidence |
| --- | --- | --- |
| Scene-facing mesh | `scene/3d/mesh_instance_3d.cpp` | MeshInstance3D source exists; next pass should trace GeometryInstance3D base RID and transform updates |
| Scene-facing batched mesh | `scene/3d/multimesh_instance_3d.cpp` lines 69–77 | `set_multimesh` forwards the MultiMesh RID to `set_base`, binding it into the normal GeometryInstance3D path |
| MultiMesh resource | `scene/resources/multimesh.cpp` lines 198–245 | `set_buffer` checks a full instance-sized stride and calls `RenderingServer::multimesh_set_buffer`; `set_instance_count` calls `multimesh_allocate_data`; visible count is forwarded separately |
| Server draw/sync | `servers/rendering/rendering_server_default.cpp` lines 439–460 | `sync` flushes or synchronizes a command queue; `draw` requires the main thread and either queues `_draw` to a render thread or executes it inline, depending on `create_thread` |
| Scene indexing | `servers/rendering/renderer_scene_cull.cpp` lines 1780–1805 | Geometry and volume instances are inserted into separate scenario spatial indexers using transformed bounds |
| Camera rendering | `servers/rendering/renderer_scene_cull.cpp` line 2709 onward | `render_camera` prepares per-camera rendering, including jitter handling; deeper trace of visibility lists, shadow passes and render submission remains pending |
| RD scene renderer | `servers/rendering/renderer_rd/renderer_scene_render_rd.cpp` | Renderer-specific implementation present; precise scene dispatch path requires follow-up |
| GPU abstraction | `servers/rendering/rendering_device.cpp` | RenderingDevice implementation present; exact GPU capability/indirect draw limits require follow-up |

The file paths above are references into this repository, not imported or newly implemented systems.

## First architectural findings

**F-001: Existing scene-to-server boundary.** MultiMeshInstance3D binds an existing MultiMesh RID to a geometry instance, so any batching improvement should first investigate current RenderingServer/scene integration. There is no need to design a replacement scene framework as the initial step.

**F-002: Rendering commands already have a thread-aware path.** The server can queue work to a render thread and synchronize commands. We must not assume rendering is wholly single-threaded, nor that additional threading will automatically help. Profile command queue waits, scene preparation, render-thread occupancy and GPU utilization separately.

**F-003: Spatial scene indexing already exists.** Scenario geometry/volume indexing uses AABBs; investigate how updates and visibility queries scale before proposing a second spatial index. Dynamic movement and conservative bounds may dominate cost.

**F-004: MultiMesh bulk buffer update is available.** The resource's `set_buffer` validates a buffer covering all allocated instances. This is a starting point for testing bulk vs sparse changes; it is not evidence that the backend always uploads the entire buffer. Trace storage/driver code and profile upload bytes before claiming that.

**F-005: Visible-instance count is not per-instance visibility.** `set_visible_instance_count` accepts a count, not an arbitrary sparse visible-instance mask. Research grouping, per-instance visibility and indirect drawing as distinct approaches. Do not assume all culling happens on CPU or that current backends lack GPU-side mechanisms until traced.

## Source call-graph hypothesis (requires verification)

    MeshInstance3D / MultiMeshInstance3D
      -> GeometryInstance3D base RID and transforms
      -> RenderingServer
      -> RenderingServerDefault command queue
      -> RendererSceneCull scenario indexers and render_camera
      -> renderer-specific scene preparation and draw lists
      -> RenderingDevice / backend
      -> GPU

This is a navigation sketch, not a verified exhaustive call graph; different renderers may have different paths.

## Candidate bottlenecks, not yet measured

1. SceneTree / instance management overhead for huge numbers of individually updated objects.
2. Spatial index update cost for rapidly moving geometry.
3. MultiMesh grouping granularity and per-region culling efficiency.
4. CPU-to-GPU transform update costs for scattered versus contiguous changes.
5. Draw preparation, material/state sorting and command submission overhead.
6. Shadow-pass duplication and visibility processing cost.
7. GPU overdraw, foliage shader cost, skinning and memory bandwidth.

## Next source-reading checklist

- Trace `GeometryInstance3D::set_base`, transform notification and instance RID ownership.
- Trace `RenderingServerDefault::_draw` into viewport and scene rendering.
- Trace `RendererSceneCull::render_camera`, scene culling and geometry lists.
- Inspect `MultiMesh` storage and per-instance setters in the active RenderingDevice backend.
- Identify GPU-side indirect draw/compute capabilities and actual use.
- Inspect existing mesh LOD, occlusion and render-thread settings.
- Document separate Forward+, Mobile and Compatibility paths.
- Find built-in profiling counters and tests that can be reused.

## Measurement plan: BENCH-02 and BENCH-03

Use equal meshes/materials and fixed camera paths. Compare 1k, 10k, 100k visible and partially visible objects with: individual MeshInstance3D nodes; direct RenderingServer instances if practical; one giant MultiMesh; spatially partitioned MultiMeshes. Vary static, 1% moving, 25% moving and 100% moving. Capture CPU P50/P95/P99, GPU frame time, draw calls, upload bytes, memory, visible bounds and visual correctness. Keep quality, resolution, hardware and renderer settings fixed.

**Gate:** no engine renderer rewrite or new culling path until the trace and baseline data identify a real bottleneck. A tiny prototype should target the most expensive demonstrated path, with existing Godot functionality preserved.

## Reference links

- [RenderingServerDefault](../../servers/rendering/rendering_server_default.cpp)
- [RendererSceneCull](../../servers/rendering/renderer_scene_cull.cpp)
- [MultiMesh](../../scene/resources/multimesh.cpp)
- [MultiMeshInstance3D](../../scene/3d/multimesh_instance_3d.cpp)
- [RD renderer](../../servers/rendering/renderer_rd/renderer_scene_render_rd.cpp)

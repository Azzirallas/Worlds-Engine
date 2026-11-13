# 20 — Phase 1: Verified renderer call graph (RD path)

**Scope:** source inspection of Worlds-Engine `master` at `660bec160a62ba9eab9836bb7349d139c52f5418`. This traces one conventional 3D viewport in the RenderingDevice path; it does not describe every XR, editor, mobile, shader or Compatibility variation. No runtime call trace has yet been collected.

## Frame and scene route

```text
Godot scene objects
  MeshInstance3D / MultiMeshInstance3D -> GeometryInstance3D / Resource RID
             |
             v
RenderingServer instance and resource APIs
             |
             v
RenderingServerDefault::draw()               rendering_server_default.cpp:447
  -> optional command queue / render thread
  -> RenderingServerDefault::_draw()         rendering_server_default.cpp:76
       -> RSG::scene->update()                line 95
       -> particles/probes updates
       -> RSG::viewport->draw_viewports()     line 109
             |
             v
RendererViewport::draw_viewports()           renderer_viewport.cpp:795
  -> _draw_viewport()                        :341
  -> _draw_3d()                              :315
  -> RSG::scene->render_camera()             :335
             |
             v
RendererSceneCull::render_camera()           renderer_scene_cull.cpp:2709
  -> _render_scene()                         :2810 / :3325
       -> visibility dependency pass
       -> scene culling/geometry/light lists
          if instance total > threshold:
             WorkerThreadPool::add_template_group_task()
             WorkerThreadPool::wait_for_group_task_completion()
          otherwise inline _scene_cull()
          _scene_cull()                      :2919
       -> shadows, GI data, probes
       -> scene_render->render_scene()       :3734
             |
             v
RendererSceneRenderRD::render_scene()        renderer_scene_render_rd.cpp:1364
  -> _render_scene(&render_data, ...)        :1512
             |
     +-------+-------------+
     |                     |
     v                     v
RenderForwardClustered     RenderForwardMobile
  ::_render_scene()         ::_render_scene()
  forward_clustered/        forward_mobile/
  render_forward_           render_forward_
  clustered.cpp:1782        mobile.cpp:862
     |                     |
     v                     v
  _fill_render_list()      _fill_render_list()
     :941                   :2221
     |                     |
     v                     v
  _render_list...()        _render_list...()
     |                     |
     +---------+-----------+
               |
               v
RenderingDevice draw_list_draw / draw_list_draw_indirect
               |
               v
RenderingDevice / RenderingDeviceDriver command graph
               |
               v
Vulkan / D3D12 / Metal driver (when supported)
               |
               v
GPU
```

The first scene-object arrow is high-level; detailed transform notification and RID ownership traversal remains a follow-up task.

## Important details

### Camera culling is a parallel scan, not simply a BVH query

In `renderer_scene_cull.cpp:3444-3480`, the camera setup takes `cull_to = scenario->instance_data.size()` and, if above `thread_cull_threshold`, parallelizes `_scene_cull`. In `renderer_scene_cull.h:1018`, the threshold is 200 by default. `_scene_cull` evaluates flags, layer masks, frustum intersection, visibility dependencies, and optional occlusion for array entries (`renderer_scene_cull.cpp:2919-2960`).

The scene also maintains geometry and volume DynamicBVH indexes (`renderer_scene_cull.h:341`). However, in the inspected main-camera path, those indexes are not used to generate the initial scan list; they are used elsewhere, including scene queries, pairing and shadow culling (`renderer_scene_cull.cpp:1203-1271`, `:1914-1940`, `:2452`). This distinction is crucial for huge sparse worlds.

**Not yet proven:** replacing the array scan with a BVH or hierarchy would improve total cost. The array scan can be fast, parallel and cache-friendly, while tree traversals have their own costs. Benchmark both.

### Submission already benefits from reuse

The Forward+ renderer sorts/builds lists and supports automatic instancing for compatible material/mesh combinations. `_fill_render_list` iterates `p_render_data->instances` (`render_forward_clustered.cpp:941-994`). Forward+ draws call `draw_list_draw` or `draw_list_draw_indirect` (`:608-625`). Mobile has a separate list builder/draw implementation.

**Not yet proven:** exact draw-call savings across transparent/opaque passes and material permutations in the fork.

### Existing observability

- `rendering_server_default.cpp:76-150` contains profiling scopes for frame begin, scene update, particles, probes, viewports and frame end.
- `renderer_viewport.cpp:1598-1616` provides measured viewport CPU/GPU render time functions.
- `renderer_viewport.cpp:1757-1763` exposes counts of objects, primitives and draw calls.
- `renderer_scene_cull.cpp:3348, 3444` has timestamp scopes for visibility updates and scene culling.
- `RenderingServerDefault::get_frame_profile()` and `RenderingDevice::get_perf_report()` exist for deeper profiling.

These are available instrumentation starting points; actual build/profile tools and device support must still be verified.

### New hardware interfaces are not completed features

`rendering_device.cpp` includes BLAS/TLAS and ray-tracing methods, subject to `SUPPORTS_RAYTRACING_PIPELINE` or `SUPPORTS_RAY_QUERY` checks. Driver interfaces also expose indirect draws and draw-count variants. These do **not** demonstrate a finished hardware ray-traced GI system or general GPU visibility-compaction path in the shipped renderer.

## Where we should instrument first

1. RenderServer command queue wait/flush and `scene->update`.
2. Visible instance count and duration of visibility dependency pass and `_scene_cull`.
3. Cost of shadow scene culling separately from main camera.
4. Time to build/sort Forward+ opaque/alpha render lists.
5. MultiMesh dirty regions, upload bytes, bounds regeneration counts/time.
6. Draw calls/GPU time as seen by actual graphics-capable driver and profiler.

## Remaining path gaps

- Scene nodes to RenderingServer transform/RID notification path, including editor interactions.
- Exact GPU command graph submission, barriers and driver support per renderer.
- Compatibility/OpenGL path.
- Built-in automatic instancing grouping rules and constraints.
- Potential GPU occlusion, indirect/compute integration elsewhere in the current branch.
- Versioned graphics feature detection for ray tracing and compute.

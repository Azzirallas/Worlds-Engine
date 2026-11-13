# 19 — Phase 1 rendering: executable research plan

**Status:** source audit underway; implementation and runtime benchmarks not yet started. This is the canonical short-term plan for Stage 1 of the [roadmap](12-roadmap.md).

## Objective

Identify the most valuable, least disruptive graphics scalability improvements for Worlds Engine while preserving Godot's scene/editor and standard rendering paths. Work should be driven by source evidence and reproducible benchmarks.

## What is confirmed so far

- The fork's checked source is Godot 4.8 beta.
- Render submission supports optional render threading; there are already profiling/timestamp markers.
- `RendererViewport::_draw_3d` calls `RendererSceneCull::render_camera`.
- `RendererSceneCull::_render_scene` builds culling results; it supports worker-pool parallelism above a threshold.
- `RendererSceneRenderRD::render_scene` prepares RD data and calls virtual `_render_scene` (implemented by Forward+/Mobile).
- Forward+ builds render lists, then calls RenderingDevice draw functions.
- MultiMesh has full-buffer and partial dirty-region upload paths, computed/custom bounds, motion-vector paths and indirect draw support.
- Source also includes BLAS/TLAS/ray-tracing APIs, **not a completed high-end GI solution**. Hardware availability and rendering integration remain unknown.

## Work packages

### WP-01: Finish source map — in progress

Trace and document:
1. Scene-facing `MeshInstance3D`/`MultiMeshInstance3D` -> `GeometryInstance3D` -> RenderingServer RID lifecycle and transform changes.
2. `RenderingServerDefault::_draw` -> `RendererViewport::draw_viewports` -> `_draw_3d`.
3. `RendererSceneCull::render_camera` -> `_render_scene` -> scene culling results, visibility/lights/shadows.
4. `RendererSceneRenderRD::render_scene` -> Forward+ / Mobile render-list and actual draw dispatch.
5. MultiMesh data flow through RD mesh storage and RenderingDevice. Check Compatibility backend separately.
6. Existing profiler markers, timestamp capture, render-info counters and hardware feature query API.

**Deliverable:** updated RES-001 source map with file/line anchors; no unverified assumptions.

### WP-02: Profile native baseline — next

Use a clean reference scene and the same scene/quality settings in this fork and a matched upstream build. Measure Node count, RenderingServer object count and instance groups, GPU time, CPU render/cull time, frame variance and upload behavior.

Do not compare editor debug runs with optimized exports. Run with VSync controlled and warm up shaders; record driver, GPU, OS, resolution, engine SHA and capture tooling. **Never use `--headless` to claim graphics performance** when a dummy rendering path is selected.

**Deliverable:** baseline data and captures for BENCH-01, BENCH-02 and BENCH-03.

### WP-03: Isolate dominant costs

Run controlled ablation tests:
- Spatial grouping vs one enormous MultiMesh.
- Custom AABBs vs dynamic AABB calculation.
- Whole-buffer vs individual instance updates at different change rates.
- Scene instance count and 3D cull scan cost.
- Shadows, temporal features and motion vectors independently on/off.
- GPU-limited heavy materials vs CPU-limited tiny meshes.

**Deliverable:** top three bottlenecks, with confidence and reproductions.

### WP-04: Architecture options and prototype gate

For each top bottleneck evaluate:
- Existing API/configuration or editor-level fix.
- Small engine change with unchanged Godot workflow.
- Optional high-throughput feature path.
- Larger GPU-driven solution with platform fallback.

Implement **only one targeted prototype** after the above identifies real value. Favor improvements in existing scene/server layers before new draw architectures.

### WP-05: Review and decision

Review visual correctness, CPU/GPU P50/P95/P99, memory, platform support and source divergence. Either adopt, revise or reject the prototype. Update [decision register](15-decisions-and-open-questions.md) and phase roadmap.

## Milestone gates

- **G1 Source map:** verified call graph and source-backed limits for both Forward+ and Mobile.
- **G2 Benchmark validity:** repeatable measurements; same scene and hardware; separate CPU/GPU time.
- **G3 Bottleneck proof:** one expensive path demonstrated in representative workload.
- **G4 Prototype justification:** specific expected win, measurable test, fallback and rollback.
- **G5 Regression review:** ordinary Godot scenes/editor and quality variants remain sound.

## Measurement tracks

| Track | Question | Scene |
| --- | --- | --- |
| A: Base cost | Does baseline launch/render have unnecessary frame work? | empty/default viewport |
| B: CPU instances | Does Node/instance tracking or camera scan dominate? | identical simple meshes, 1k–100k |
| C: GPU visibility | Are many invisible instances rasterized? | forest, city and partially hidden grid |
| D: Instance updates | Do dynamic movements cause transfer or bounds spikes? | static/1%/25%/100% moving |
| E: GPU features | Do shadows/foliage/lighting dominate instead? | high-quality vegetation and mixed materials |
| F: Frame pacing | What causes the worst stutters? | camera teleport, region changes, shader warm-up |

## What not to do yet

- No rewrite of RenderingServer, scene/editor, geometry types or low-level graphics driver.
- No meshlets/virtualized geometry implementation until ordinary mesh LOD, streaming, indirect and culling costs are measured.
- No new global spatial index merely because an existing BVH is present; camera culling already uses a fast parallel array scan.
- No claim that indirect drawing is automatically GPU-driven culling.
- No promise that ray-tracing API availability means modern dynamic GI is ready.
- No engine FPS claims without running tests.

## Immediate next work

1. Finalize RES-001 path/source map, RES-002 detailed data/visibility analysis.
2. Create a minimal reproducible Godot benchmark project or use suitable upstream benchmark scenes.
3. Run Phase 1 tests on a graphics-capable machine with known GPU/driver.
4. Choose first prototype from the results; update docs before code.

## Handoff notes

When resuming work, read this file, [RES-001](17-renderer-source-audit-res-001.md), [RES-002](18-res-002-multimesh-and-visibility.md), [benchmarks](11-performance-and-benchmarks.md), and [decisions](15-decisions-and-open-questions.md). Do not infer progress solely from the roadmap. At this stage all engine sources remain unchanged.

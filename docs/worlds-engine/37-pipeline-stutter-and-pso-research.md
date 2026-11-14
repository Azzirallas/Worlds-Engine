# 37 — Pipeline compilation, first-frame stutter and PSO readiness audit

**Status:** source survey, public-document comparison and original test design; **not** benchmarked or integrated. Audited 2026-11-13. Godot `master@be1999a0f532124705359e4c3dde0a3b3034a0bd`; licensed Unreal `release@f45729c0b6f097038e72b52d366a62baeca3275b`. Follow [27](27-license-and-independent-implementation-protocol.md).

## Problem statement

Our future GPU-driven geometry and lighting modes will change shader variants, render target formats, vertex data, pass coverage and material state. A feature that saves steady-state frame time can still make the engine feel worse if first-use pipeline creation causes hitches, if editor hot-reloads invalidate expensive pipeline variants, or if compilation competes with active simulation work.

**Optimization target:** stable user-visible frame latency during new object/scene/material discovery, not merely higher warm-cache FPS.

## What Godot already provides — source verified + public docs

- `servers/rendering/renderer_rd/pipeline_cache_rd.cpp/.h`: stores graphics pipeline versions keyed by render/vertex format, pass and specialization choices; regenerates or clears versions when relevant state changes. A cache is already present.
- `servers/rendering/renderer_rd/shader_rd.cpp/.h`: shader version/variant generation and compiled shader stage/binary infrastructure, with existing shader caching.
- `servers/rendering/renderer_rd/forward_clustered/scene_shader_forward_clustered.cpp` and `storage_rd/material_storage.cpp`: integration locations for shader/material choices; detailed pipeline-demand path remains to be traced.
- `servers/rendering/rendering_device.cpp`: API-level pipeline creation and GPU submission; backend behavior requires measurement.

**Do not claim that Godot lacks shader pipeline precompilation.** Its public performance guidance describes **ubershaders**, mesh/surface precompilation paths, on-demand cases, and specialization during gameplay. The documentation distinguishes compilation monitors such as Mesh, Surface, Draw and Specialization; these should be baseline telemetry. See [Godot: reducing stutter from pipeline compilations](https://docs.godotengine.org/en/stable/tutorials/performance/pipeline_compilations.html).

The existing internal `PipelineCacheRD` clears compiled variants after certain state changes. That identifies a **test case**, not evidence of an observed user hitch or a bug. The broader engine's shader precompilation may mitigate first-use costs.

## Unreal architecture lessons — no code translation

Private waypoints inspected:
- `Engine/Source/Runtime/RHI/Private/PipelineStateCache.cpp`
- `Engine/Source/Runtime/RenderCore/Private/ShaderPipelineCache.cpp`
- `Engine/Source/Runtime/RenderCore/Private/PipelineCacheUtilities.cpp` (inventory waypoint only)

Epic publicly describes automatic **PSO precaching** and separately recorded/bundled PSO caches. The public documentation explains anticipatory PSO requests, background compilation, first-use readiness, and validation of misses or requests that finished too late. Graphics and compute work must both be considered; driver cache behavior remains important.

- [Epic PSO precaching](https://dev.epicgames.com/documentation/en-us/unreal-engine/pso-precaching-for-unreal-engine)
- [Epic PSO caches](https://dev.epicgames.com/documentation/en-us/unreal-engine/optimizing-rendering-with-pso-caches-in-unreal-engine)

**Generalizable design question:** what pipeline states will an asset likely need *before* it becomes visible, and how much preparation can safely happen without harming loading time, CPU scheduling or memory? The answer should be built from Godot public interfaces and our own benchmark data, not the private implementation details above.

## Baseline protocol: no feature changes

P0 — pin engine revision, renderer backend, graphics driver and hardware. Capture Godot's pipeline compilation monitor categories and cold/warm startup.

P1 — one ordinary mesh with a standard opaque material. Repeat with different vertex layouts, alpha-masked material, a normal map, skinning, shadow casting, multiview (if supported) and editor hot reload.

P2 — stream in a cold region containing many distinct material/shader variants while moving the camera. Record frames before, during and after resource instancing.

P3 — repeat all scenes with a warm driver/cache state, then a controlled clean cache where safe. Never compare a debug build with a release build as if equivalent.

P4 — attach experimental geometry/indirect rendering only after the normal engine results are stable. Verify each required pass: depth, opaque/color, shadow, velocity/motion and other applicable material paths.

## Measurements and classification

Each test should record:
- frame CPU/GPU time distributions and **p95/p99** hitches; CPU profiling to identify where the stall occurred;
- first visible frame and first correct-material frame; number and severity of missed/late pipelines, where instruments expose them;
- compile jobs, queued/inflight pipeline requests, effective compile time and background CPU occupancy;
- shader/pipeline count and memory before/after hot reload and scene unload;
- warm vs cold startup and shader specialization duration;
- pop-in, temporary substitute material, missing depth/velocity/shadow contribution and visual mismatch;
- backend/driver-specific warnings and whether the measurement is actually supported.

Do not claim that all monitoring counters imply stutter, or that no logged compilation proves no driver stall. A background compilation can still contend for CPU cores or memory bandwidth.

## Proposed original experimental directions (not approved to implement)

**H1 — asset-informed prewarm:** when a scene/resource becomes likely to display, enumerate a *conservative, bounded* set of currently supported Godot pipeline requirements and request work ahead of first view. Compare against existing ubershader/surface precompilation before adding an alternative.

**H2 — interest-weighted compile scheduling:** allocate compilation effort based on impending visibility and a bounded CPU/IO budget, but always preserve correctness when a pipeline is late. Investigate whether this has a measurable advantage over Godot's existing behavior.

**H3 — variant growth controls:** reduce unnecessary experimental shader permutations through opt-in feature tiers, compile-time accounting and limited reusable material modes; do not silently drop material semantics.

**H4 — instrumentation-only improvement:** if Godot already performs adequately, upstream a portable profiler or diagnostics instead of introducing another PSO scheduler.

## Acceptance and rollback

- No regression in ordinary Godot project/material compatibility.
- No missing geometry, wrong depth, stale shader variant, mismatched shadow or motion output.
- Measurable improvement to cold/streamed p95/p99 *with* acceptable warm-frame performance and resource use.
- Disabled or unsupported feature cleanly returns to normal Godot path.
- No proprietary shader, pipeline cache, private layout or code translated from Unreal.

## Position in Phase 1

This is a **parallel audit**, not a replacement for R-001b baseline benchmark or R-003 GPU visibility feasibility. Before introducing a new geometry path, add a **shader/pipeline stutter fixture** to the benchmark plan so a headline GPU win cannot hide cold-start regression.

Related: [34 — materials, render graph, temporal](34-materials-graph-and-temporal-reconstruction.md), [35 — validation](35-phase-1-validation-and-next-actions.md), [36 — texture streaming baseline](36-texture-streaming-baseline-audit.md).

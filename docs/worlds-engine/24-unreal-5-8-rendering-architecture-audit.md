# 24 — Unreal Engine 5.8.4 rendering architecture audit

**Audit date:** 2026-11-13  
**Unreal source:** private, access-controlled `Azzirallas/UnrealEngine`, branch `release`, commit `f45729c0b6f097038e72b52d366a62baeca3275b`; `Engine/Build/Build.version` identifies **5.8.4**.  
**Comparison target:** `Azzirallas/Worlds-Engine`, `master`, audited at `6a8f3e91d98af788bcf7837e785b26b0500989c9`, `version.py` identifies **Godot 4.8 beta**.  
**Status:** direct source inspection and public documentation review; **not** a compiled build, hardware profiling, exhaustive algorithm verification, or permission to port source. See [license protocol](27-license-and-independent-implementation-protocol.md).

## Executive conclusions

1. Unreal's advantages arise from *interacting systems*: persistent GPU scene, instance-level culling, virtualized geometry, budgeted streaming, material binning, graph-scheduled passes, cached shadows, GI caches and temporal reconstruction. Treating one feature as a standalone magic algorithm is misleading.
2. Godot 4.8 already has a dependency-aware rendering command graph and indirect draw/dispatch; we should **not write a second generic render graph** in Phase 1 without proof that existing functionality is inadequate.
3. The high-value experiment is *GPU-resident visible work selection with persistent scene data*, contrasted against Godot's CPU scan and regional MultiMesh control—not simply adding another way to submit an indirect draw.
4. Some of the most attractive opportunities lie in weaknesses of existing methods: foliage/aggregate geometry, high dynamic-geometry update rates, bounded streaming during rapid camera motion, GI/shadow cache invalidation and material diversity.
5. Prioritize cross-vendor, non-hardware-ray-tracing experiments first. High-end RT solutions require supported GPU/test platforms and independent fallback paths.
6. This audit describes **general, publicly documented concepts** and source-file waypoints. It contains **no Unreal implementation or shader excerpts**. A source license does not grant permission to relicense, publish or translate that source into MIT Godot code.

## Source inspection coverage and findings

The paths below are **waypoints for licensed reviewers only**, not instructions to reconstruct Epic's implementation. High-level architecture is cross-referenced to public sources at the end.

### A. Scene visibility, GPU scene and indirect instance work

Private source files inspected:
- `Engine/Source/Runtime/Renderer/Private/SceneVisibility.cpp`
- `Engine/Source/Runtime/Renderer/Private/SceneOcclusion.cpp`
- `Engine/Source/Runtime/Renderer/Private/SceneCulling/SceneCullingRenderer.cpp`
- `Engine/Source/Runtime/Renderer/Private/GPUScene.cpp`
- `Engine/Source/Runtime/Renderer/Private/InstanceCulling/InstanceCullingContext.cpp`
- `Engine/Source/Runtime/Renderer/Private/Nanite/NaniteVisibility.cpp`

**Established architecture:** scene-level visibility is not a single pass; there are CPU visibility/LOD decisions, GPU-resident primitive/instance data, GPU instance work, occlusion/history, and separate fine-grained Nanite visibility. GPU scene storage and culling results can feed indirect commands. This is distinct from just drawing many instances through a single MultiMesh aggregate.

**Godot opportunity:** trial a *persistent GPU instance table*, stable indices, region-level dirty tracking, a GPU visible-list/compaction pass and indirect submission. Preserve CPU-side conservative fallback and scene/node semantics. Test GPU uploads, reallocation, compaction contention and readback stalls, not only draw-call count.

**Questions:** Does ordinary Godot instance-culling time scale materially with entity count if most are invisible? Will a GPU path save more than compute dispatch/extra memory cost? What is the crossover for 100, 1,000, 10,000 and 100,000 instances? Does occlusion history misclassify newly revealed or fast-moving objects?

### B. Nanite virtualized geometry and its limitations

Private files inspected:
- `Engine/Source/Developer/NaniteBuilder/Private/NaniteBuilder.cpp` (source organization and role examined)
- `Engine/Source/Runtime/Engine/Private/Rendering/NaniteResources.cpp`
- `Engine/Source/Runtime/Renderer/Private/Nanite/NaniteCullRaster.cpp`
- `Engine/Source/Runtime/Renderer/Private/Nanite/NaniteShading.cpp`
- `Engine/Source/Runtime/Renderer/Private/Nanite/NaniteStreamOut.cpp`
- `Engine/Shaders/Private/Nanite/NaniteClusterCulling.usf`, `NaniteInstanceCulling.usf`, `NaniteRasterizer.usf`, `NaniteShadeBinning.usf` (presence and subsystem roles audited, not reproduced)

**Publicly described approach:** preprocess opaque geometry into a hierarchical, compressed cluster representation; choose screen-appropriate detail and visibility; stream nonresident detail; use a rendering path designed for small on-screen primitives. Specialized raster and material processing paths are involved. See official [Nanite overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine) and [Nanite technical details](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-technical-details).

**Key constraints:** a virtual geometry data structure is a complete asset/rendering format, not a draw flag; visible detail, random page misses, rapid camera turns and material variability all affect performance. Public Epic docs identify aggregate geometry—leaves, hair, vegetation—as a difficult case for simplification and occlusion because many layers of partial coverage increase overdraw. Transparent and specialized materials complicate a universal solution. Do not claim the exact same constraints or feature set across all UE minor releases.

**Godot opportunity:** original *small* offline cluster prototype for static, opaque, one-material meshes; integrate GPU visibility with current RenderingDevice; compare with a quality-matched traditional mesh LOD + region MultiMesh. **No goal to implement a literal Nanite clone.** Distinct high-risk research: for aggregate foliage use representation switching (cluster, card, impostor, procedural) according to projected coverage.

### C. Page streaming, residency and feedback

Private files inspected:
- `Engine/Source/Runtime/Engine/Private/Rendering/NaniteStreamingManager.cpp`
- `Engine/Source/Runtime/Engine/Private/Rendering/NaniteResources.cpp`
- `Engine/Source/Runtime/Renderer/Private/DistanceFieldStreaming.cpp`

**Established concerns visible at architecture level:** asynchronous streaming requests, page dependencies, priorities, resident set management, GPU feedback/readback and resource updates; the distance-field side also has its own streamed data structures. These systems demonstrate that **residency and update policy** are major independent problems even with efficient draw submission.

**Godot opportunity:** implement a general-purpose *request/budget/asset-residency measurement layer* before locking in a geometry codec. Include predictive prefetch, emergency coarse LOD, page-dependency correctness and bounded IO/upload budgets; page tables and LRU are common techniques, not proprietary discoveries.

**Adversarial workloads:** teleport camera, rapid 180-degree turns, thrash two distant regions, constrained VRAM, disjoint material meshes, multiview, resource mutation while streaming. Measure first-visible latency and peak stalls rather than average frame rate only.

### D. Render dependency scheduling and resource lifetime

Private source inspected: `Engine/Source/Runtime/RenderCore/Private/RenderGraphBuilder.cpp`.

**Public RDG concept:** graph-defined resource dependencies facilitate pass culling, transitions, transient resource reuse, async compute scheduling and parallel recording; see [Epic RDG documentation](https://dev.epicgames.com/documentation/unreal-engine/render-dependency-graph-in-unreal-engine).

**Critical Godot finding:** `servers/rendering/rendering_device_graph.cpp` and `.h` already implement a graph of resource-dependent draw/compute commands. `rendering_device.cpp` defines command reordering (enabled in audited tree) and fine-grained synchronization options. Therefore **do not suggest rebuilding RDG from zero**. Instead profile graph compile/record time, transient resource allocation, pass scheduling and driver behavior. Any advanced async/parallel recording proposal must pass backend-specific validation.

**Concrete caution:** in the audited Godot tree secondary command buffers per frame are explicitly disabled by default due to unresolved driver issues. Treat automatic parallel command recording as a compatibility experiment, not a free optimization.

### E. Lumen global illumination and surface representations

Private files inspected:
- `Engine/Source/Runtime/Renderer/Private/Lumen/LumenScene.cpp`
- `LumenSceneRendering.cpp`, `LumenMeshCards.cpp`, `LumenSceneCardCapture.cpp`
- `LumenSceneGPUDrivenUpdate.cpp`, `LumenSurfaceCache.cpp`
- `LumenRadianceCache.cpp`, `LumenScreenProbeGather.cpp`
- `LumenReSTIRGather.cpp`, `LumenIrradianceFieldGather.cpp`

**Public concept:** use multiple representations and tracing methods, rather than ray trace the full final shading scene at every query. Surface cache/card data, radiance and probe caches, screen-space information, distance fields and optional hardware ray tracing serve different quality/performance requirements. Temporal and budgeted refresh are central. Epic describes the method and shortcomings in [Lumen Technical Details](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine). UE 5.8 documentation also describes **Lumen Lite** using irradiance-field/probe-occlusion techniques ([5.8 release notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes?lang=en-US)).

**Godot reality:** Forward+ already offers SDFGI, VoxelGI and SSIL, so 'add GI' is an inaccurate task statement. Godot's documented SDFGI does *not* fully update dynamic occluders or emissive surfaces. Candidate focus: incremental updates, dynamic geometry participation, adaptive probe/cache budgets and correctness under motion—possibly by augmenting an existing GI path rather than replacing it.

**Research differentiator:** use explicit scene-change metadata and visual importance to allocate GI work while handling disocclusion and lighting changes correctly. A precise invalidation system that reduces work without temporal artifacts could surpass a more aggressive—but stale—cache.

### F. Virtual shadow maps

Private files inspected:
- `Engine/Source/Runtime/Renderer/Private/VirtualShadowMaps/VirtualShadowMapArray.cpp`
- `VirtualShadowMapCacheManager.cpp`, `VirtualShadowMapClipmap.cpp`

**Public concept:** virtualize shadow-map texels into sparse physical pages; mark pages needed for visible receivers; cache previously rendered pages; invalidate affected regions on scene/light changes. Separating static and dynamic depth enables reuse. See [Epic Virtual Shadow Maps](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine).

**Risk:** widespread invalidation can overwhelm caching, especially continuously deforming foliage, moving lights and world-position-offset surfaces. Cache hit rate, invalidated surface area and spikes matter more than page count alone.

**Godot opportunity:** initially prototype one local light and one static/dynamic split under a standalone path. Avoid replacing all shadows; compare against Godot directional cascades and the local-light atlas in the actual target scene.

### G. MegaLights: bounded stochastic direct lighting

Private files inspected:
- `Engine/Source/Runtime/Renderer/Private/MegaLights/MegaLightsSampling.cpp`
- `MegaLightsResolve.cpp` (source entrypoints)
- `Engine/Source/Runtime/Renderer/Private/Lumen/LumenReSTIRGather.cpp` (separate GI research)

**Public concept:** use a bounded per-pixel light-sampling budget rather than work proportional to evaluating every affecting light; trade numerical variance/temporal reconstruction for stable costs as light counts rise. Epic's [MegaLights overview](https://dev.epicgames.com/documentation/unreal-engine/megalights-in-unreal-engine) explicitly explains the trade-off: constant-ish cost is **not** constant quality. Denoising, sample distribution and occluded lights cause limitations.

**Godot opportunity:** adaptive clustered-light vs stochastic-light switch. Use a fixed sampling budget only when light density warrants it; preserve normal clustered lighting for simpler scenes. This is a long-term shader/lighting experiment—not Phase 1's first code change.

### H. World Partition and rendering-adjacent streaming

Private files inspected:
- `Engine/Source/Runtime/Engine/Private/WorldPartition/WorldPartitionStreamingPolicy.cpp`
- `WorldPartitionRuntimeSpatialHash.cpp`
- `WorldPartitionSubsystem.cpp` (subsystem presence checked)

**Public concept:** use streaming sources, spatial cells and levels of detail to manage world representation and lifetime. See [Epic World Partition documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine).

**Worlds Engine distinction:** rendering stream-out must not delete the world entity, NPC memory or persistent item. This is a product requirement independent of Unreal. Prefer a general Godot scene streaming interface and an *optional* simulation-owned visibility/interest feed; avoid coupling rendering to Worlds-ECS.

### I. Ray tracing, skinning, foliage and animation

Private files inspected:
- `Engine/Source/Runtime/Renderer/Private/Nanite/NaniteRayTracing.cpp`
- `Engine/Shaders/Private/Nanite/NaniteClusterRayTracing.usf` (subsystem scope)
- `Engine/Source/Runtime/Renderer/Private/Nanite/NaniteCullRaster.cpp` (deformation/raster feature handling)

**Public issue:** full-detail geometry representation and a ray-tracing geometry representation often differ. Acceleration-structure memory, update/rebuild time and imperfect fallback geometry create mismatches. Godot 4.8 has BLAS/TLAS interface methods, but that alone is not hardware support, a complete RT scene or a shipping GI solution.

**Future option:** investigate independently published ray-tracing deformable cage and shared-geometry techniques, hardware permitting. For non-RT hardware prioritize selective updating and representations for moving vegetation.

## Cross-cutting architectural lessons

| Lesson | Generalizable concept | Do not assume |
| --- | --- | --- |
| Perceptual work | Match work to visible pixel detail and importance | Triangles are the only relevant budget |
| Persistent scene data | Keep GPU data stable and update only changed ranges | Incremental writes are always faster than bulk |
| Coarse + fine visibility | Region filtering then fine GPU selection | Hierarchies always beat linear scans |
| Budgeted residency | Request/priority/dependency/fallback across frames | No stutter or thrashing just because pages exist |
| Multiple render methods | Choose raster/compute/RT by workload | One path should replace every current material |
| Temporal caching | Refresh only stale, relevant shadow/GI work | Skipped work is free of visual error |
| Frame graph | Track dependencies and reusable resources | Godot lacks a graph |
| User-visible performance | Frame latency, memory and artifacts are objectives | FPS alone is a sufficient result |

## Explicit source coverage and non-coverage

**Performed:** direct reads of representative renderer, culling, Nanite, Lumen, VSM, MegaLights, streaming, GPU scene, world-partition and RDG source paths; inspected shader file inventory and representative shader roles. Cross-checked public Epic documentation.

**Not performed:** build Unreal; run any rendering benchmarks; analyze all shader branches; inspect entire import/compression pipeline, full skeletal animation system, texture streaming, PSO compilation or full cross-platform RHI; prove cache/LOD correctness; establish legal clearance for derived implementations. Source file presence and top-level entrypoints are not enough to assert algorithmic performance.

## Follow-on audits

The [texture streaming baseline audit](36-texture-streaming-baseline-audit.md) and [pipeline-stutter/PSO research](37-pipeline-stutter-and-pso-research.md) cover two previously under-specified domains. Both use licensed Unreal paths only as source-review waypoints and anchor public engineering concepts in published references. Godot's existing texture-streaming module and shader precaching must be profiled before proposing replacements.

## What this changes

Use the [Godot gap matrix](25-godot-renderer-gap-matrix.md), [experiment specifications](26-phase-1-prototype-priority-and-measurements.md) and [independent implementation protocol](27-license-and-independent-implementation-protocol.md). Strongest initial candidates: **incremental GPU instance state + culling**, **streaming and fallback budgeting**, and **update-driven rendering caches**. Original scene representation switching remains the frontier research hypothesis.

> This public document intentionally includes **no licensed Unreal source text, translated functions, detailed private data layout, private constants or shaders**. All technical mechanisms presented are high-level, publicly documented concepts or independent design hypotheses.

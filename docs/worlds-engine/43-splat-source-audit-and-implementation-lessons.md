# 43 — Gaussian-splat source audit: transferable engineering lessons

**Status:** public-source inspection, exact audited-file references, independent engineering conclusions. **Not an implementation, benchmark, or proof of faster rendering.** Reviewed 2026-11-13. All named third-party repositories remain unchanged. Worlds-Engine receives only original research prose. The private Unreal repository is not used as an implementation source.

This document goes deeper than [41 — project overview](41-gaussian-splatting-project-survey-2026.md) and [42 — proposed architecture](42-independent-hybrid-splat-rendering-architecture.md). Its objective is to preserve what we learned directly from code, and identify practical *cross-project integration gaps* before GPU work is possible.

## Short version: five high-value findings

1. **EA Mesh2Splat produces a material-aware Gaussian derivative from a triangle mesh** using the original triangle geometry and texture samples. Its exported PLY carries extra per-splat **normal, metallic and roughness** properties.
2. **GDGS currently discards those Mesh2Splat-specific PBR attributes on import.** Its standard PLY decoder and canonical 60-float resource only preserve position, shape, opacity and spherical-harmonic appearance. Therefore linking the two as-is is *not* a physically relightable mesh-to-splat pipeline, even if a converted splat becomes visible.
3. **PlayCanvas's latest unified path is more sophisticated than an ordinary splat viewer.** It has spatial streamed LOD, budget balancing, coarse-first requests, a persistent work buffer, allocation reuse/defragmentation and GPU frustum culling. We should treat this as a systems reference, not merely an alpha-sort implementation.
4. **Spark is already exploring splat animation *and* paging.** It demonstrates dual-quaternion/linear-blend skinning and page-bounded splat storage with independently managed fetching. Its WebGL/Three.js representation needs a new native backend strategy, not a direct engine copy.
5. **A splat budget is not a guaranteed device-memory cap.** The number of drawn Gaussians does not include tile duplication, sorting worksets, staging, replacement overlap, per-view state, lighting/collision data or allocations when even the coarsest LOD exceeds the configured splat target.

All claims below are sourced to the **public projects**, not proprietary Unreal. Pinned GitHub main HEADs at time of read are included for stable source retrieval; later commits may invalidate line ranges.

## A — EA SEED Mesh2Splat: how conversion actually works

**Repo** [electronicarts/mesh2splat](https://github.com/electronicarts/mesh2splat), public 2025 project. Audited entrypoints:
- `src/renderer/renderPasses/ConversionPass.cpp` (conversion orchestration and GPU buffers);
- `src/shaders/conversion/converterVS.glsl`, `converterGS.glsl`, `converterFS.glsl` (source attributes → samples);
- `src/parsers/parsers.cpp` `writePbrPLY` (serialized output);
- `src/renderer/renderPasses/GaussianRelightingPass.cpp` (demonstration material inputs and shading);
- `LICENSE.txt`, `NOTICE.txt`, `CITATION.cff` (actual licensing metadata).

**Verified design:** a conventional input `.glb` is parsed into triangle meshes. The conversion renderer projects triangles into sampling space, computes tangent-plane/covariance-related Gaussian orientation/shape, and rasterizes samples. The fragment path captures original albedo and optional normal + metallic-roughness textures. Conversion is an *asset build*, so an occasional GPU-to-CPU readback is less problematic than it would be in a per-frame renderer.

`ConversionPass::execute` allocates a capped Gaussian storage buffer, draws the input meshes, and reads a generated-primitive counter. It caps generation against a downstream fixed sort capacity. **Investigation requirement:** check how capacity exhaustion is reported, how the counter is interpreted when it exceeds reserved storage, and whether downsampling or buffer growth can safely preserve all source surfaces. This is a *test question*, not a reproduced overflow bug.

The `writePbrPLY` path exports standard-ish 3DGS position/opacity/scale/rotation/DC color **plus custom fields**:
- `nx`, `ny`, `nz`;
- `metallicFactor`;
- `roughnessFactor`.

These fields are a useful, concrete foundation for *material-aware* splat shading. **However**, ordinary 3DGS importers are not required to preserve them. A Gaussian file format is not automatically a portable PBR material format.

**Real advantage:** from an already-authored mesh, we can derive a Gaussian representation without needing a separately trained photographic scene. A splat does not magically add geometry not present in the model, and can be worse for crisp silhouettes, exact collision, skinning, specular highlights or memory.

**Licensing:** `LICENSE.txt` grants redistribution with conditions and mark restrictions, while `CITATION.cff` says MIT. Do **not** call the whole repository universally MIT without resolving this discrepancy and third-party NOTICE obligations. Its original algorithms can be studied and independently reimplemented; code adoption requires a precise file-by-file permission review.

## B — GDGS Godot plugin: two real renderers, incompatible PBR import

**Repo** [ReconWorldLab/godot-gaussian-splatting](https://github.com/ReconWorldLab/godot-gaussian-splatting) `main@c22024b33a24e06d8629c654825fabd0485b2dba`, MIT. Exact source:
- `addons/gdgs/importers/decoders/standard_ply_decoder.gd`;
- `addons/gdgs/importers/builders/gaussian_resource_builder.gd`;
- `addons/gdgs/runtime/resources/gaussian_resource.gd`;
- `addons/gdgs/runtime/render/backend/gaussian_backend_selector.gd`;
- `addons/gdgs/runtime/render/compute/gaussian_render_manager.gd`, `gaussian_gpu_state_cache.gd`, `gaussian_renderer.gd`;
- `addons/gdgs/runtime/render/raster/raster_render_backend.gd`, `raster_sorter.gd`;
- `addons/gdgs/runtime/compositor/gaussian_compositor_effect.gd`;
- `docs/rendering-backends.md`, `docs/relighting.md`.

### B1 — critical material data loss when combined with Mesh2Splat

The `standard_ply_decoder.gd` converts PLY to a canonical object with positions, linear scales, rotations, opacity and 48 spherical-harmonic floats per Gaussian. The `gaussian_resource_builder.gd` builds a **60-float32** runtime record (240 bytes/Gaussian). `gaussian_resource.gd` describes that same record.

**Source conclusion:** the decoder never reads Mesh2Splat's `nx/ny/nz`, `metallicFactor` or `roughnessFactor`, and the canonical record has no place to retain them. These properties are therefore **lost for rendering through this importer**. Material-aware splats require **all** of the following, not just choosing another shader:
1. Decode optional PBR fields and distinguish absent from zero/black.
2. Version a richer runtime splat record or sidecar buffer without breaking existing files.
3. Preserve tangent/normal conventions, sRGB/linear color and material identity.
4. Make whichever renderer supports PBR fetch these attributes.
5. Integrate light/shadow/depth/normal behavior with Godot's real scene data, and define a lower-quality fallback.
6. Keep standard photographic splats' baked radiance path separate; it cannot be blindly converted to albedo.

This is the first high-impact *integration blocker* we can address later with a focused, opt-in and CPU-testable importer experiment.

### B2 — backend comparison from source

**Compute:** `gaussian_render_manager.gd` snapshots SceneTree state on main thread and hands render work to GPU/render thread; the cache holds a limited number of render-size states. The `gaussian_renderer.gd` sequences projection, tile bounds, GPU radix-sort passes and compositing; the shader set is under `render/compute/shaders/`. `gaussian_gpu_state_cache.gd` uses **16×16 tiles** and reserves up to **10 sort elements per splat**. That maximum and its handling under a very large projected ellipsoid are a required overflow/quality test. This is **not** evidence of a crash or defect.

**Raster:** `raster_render_backend.gd` uses Godot's transparent pass and per-node `MultiMeshInstance3D` representations, with its own CPU worker for back-to-front order. `raster_sorter.gd` bins by camera-relative depth on the worker. It benefits from normal hardware depth testing and wider renderer support, but the order can be stale when a camera changes faster than worker results arrive.

**Fundamental trade-off:** tile-exact ordering, ROP blending, compositor depth behavior, color space and memory layout differ. A 'shared shader' or simple sort swap cannot guarantee equivalent pixels. GDGS author documentation estimates 240B/splat (compute core record), 144B/splat (raster data textures) **before other buffers**; these figures are not measured in our environment.

### B3 — format coverage and relighting are narrower than the marketing term

The bundled SOG decoder `addons/gdgs/importers/decoders/sog_decoder.gd` explicitly checks the metadata version is **2** and reports unsupported versions. This differs from newer SOG v3 and multi-file Streamed SOG emitted by PlayCanvas. A `.sog` filename is not enough to guarantee a valid read.

GDGS's optional relighting proxies can modulate a stored appearance and produce shadow-casting proxy meshes; `docs/relighting.md` explicitly warns that original captured highlights, hard shadows and indirect light cannot be removed. For photo-trained splats, do not promise full physically correct day/night support. For mesh-derived splats, the missing material-data problem can potentially be solved separately.

## C — PlayCanvas: actual production-grade splat streaming structure

**Repos:**
- [playcanvas/engine](https://github.com/playcanvas/engine) `main@9b2191916ff8607166e6e92fe0a952eb3aa31412` (MIT);
- [playcanvas/splat-transform](https://github.com/playcanvas/splat-transform) `main@6f642939dd5d5db3094bf749d5821ce84e3938da` (MIT);
- [PlayCanvas Streamed SOG specification](https://developer.playcanvas.com/user-manual/gaussian-splatting/formats/streamed-sog/) and [current unified runtime guide](https://developer.playcanvas.com/user-manual/gaussian-splatting/building/unified-rendering/lod-streaming/).

**Critical source distinction:** the *new unified* rendering and LOD path lives under `src/scene/gsplat-unified/`, **not just** the older `src/scene/gsplat/`. Audit that code for current architecture; the legacy path remains relevant for fallback/browser compatibility.

### C1 — streaming hierarchy and loading

- `gsplat-octree.js`: per-node bounds/LOD and file refs; per-instance requested-file sets; global highest-priority request handling, load/unload and cooldown/retention rules; prepared metadata supports a coarse-first draw strategy.
- `gsplat-lod-tree.js`: transforms a manifest with LOD variants at leaves into a hierarchical tree of renderable levels **without moving the original splat data**; its internal grouping target is 4,096 splats/node in the audited code, a tuning choice not a universal law.
- `gsplat-octree-instance.js`: per-camera distance preparation, cut selection, LOD underfill handling, file reference tracking and prioritized requests. Designed to render loaded coarser data while desired finer levels arrive, with explicit conditions and fallback.
- `gsplat-budget-balancer.js`: sweeps hierarchical refinement events using a priority heap over distance-derived thresholds and stops when further refinement exceeds the splat target.
- `gsplat-world.js`: orchestrates octree instances, LOD cadence, world states, work-buffer updates and camera-dependent work. The audited path drives streaming/LOD primarily with one camera; multiple viewports require explicit independent validity/priority planning.
- `gsplat-world-state.js`: allocates persistent block ranges, retains unchanged placements, computes incremental upload deltas and can perform bounded incremental defragmentation; a 30% fragmentation threshold appears in the audited allocator path.
- `gsplat-frustum-culler.js`: per-region bounds and transforms uploaded for GPU selection.
- `gsplat-work-buffer.js`: unified render-ready storage; separate full geometry/material or color-only updating paths avoid repeating unchanged work.

**Idea to adopt conceptually:** a **versioned scene-specific splat workset** assembled from resource chunks. Separate *content asset* (immutable compressed data), *regional level* (chosen visibility/quality), *GPU allocation* (where currently resident), and *view state* (ordering/lighting/temporal validity). Keep the conventional mesh rendering unaffected.

### C2 — correctness and limits

- The `splatBudget` default in `gsplat-params.js` is **1,000,000 splats**. A `target` mode tries to fill budget with detail; a `limit` mode only coarsens distance-chosen detail. Zero means uncapped selection, not a GPU memory limit.
- The balancer's tests confirm that **if even the coarsest levels exceed the target, they can still remain selected**. Therefore the count budget is *not* a hard guaranteed memory cap. A Worlds design needs a separate hard residency cap and a visible error/fallback policy for impossible budgets.
- The world performs a full LOD evaluation on a cadence (ten-frame counter) and on other invalidating conditions. It can defer work while a sorter has back-pressure. This reduces CPU work but is a camera-teleport/first-correct-detail latency test.
- **Docs/source disagreement:** some PlayCanvas guides still describe `GSPLAT_LODMODE_ERROR` or error-guided selection. In the exact pinned `gsplat-params.js`, `lodMode` is **removed** and the code explicitly states current LOD levels are chosen by distance. Do **not** base an implementation on an unverified guide feature; recheck source and docs for the desired release when work begins.
- `gsplat-octree.resource.js` releases CPU-side texture source data after upload, with a separate device-loss restore strategy. This can save memory but demands correct reload/rebuild behavior.
- Older `gsplat-sorter.js` uses worker-sort results and deferred uploads, keeping only the latest pending result; do not confuse that simple CPU sort with the unified GPU-sort path.

### C3 — importing/decimating at scale

`splat-transform` now has `src/lib/decimate/`, `decimate-uniform/`, `spatial/`, `chunk/` and `writers/write-lod.ts`. Its current `decimate/moment-match.ts` uses mass/area-weighted Gaussian merging with covariance/opacity treatment; `decimate-source.ts` has bounded chunk processing and an optional spill/resident-memory policy. `writers/write-lod.ts` gathers per-LOD, per-region splat data and validates finite geometry/colors before encoding.

**Design lesson:** naive uniform deletion often loses thin and varied-density surfaces. Replacing a group with a fit that preserves coverage/statistics may provide better visual LOD. This is not a free algorithm—merging two overlapping Gaussians generally changes the radiance/opacity distribution and can produce artifacts. Verify image error, multiview consistency and alpha behavior; never adopt a simplifier solely because the file becomes smaller.

**Format lesson:** [Streamed SOG](https://developer.playcanvas.com/user-manual/gaussian-splatting/formats/streamed-sog/) `lod-meta.json` is a **separate spatial-tree format version 1**. Its referenced leaf chunks may be SOG **version 2 or 3**. The bundle uses chunk ranges and explicit filenames, not an implicit filename convention. A decoder must validate that bounds, counts, offsets and totals are consistent before allocation or rendering.

## D — Spark: skinning and paged GPU splats

**Repo** [sparkjsdev/spark](https://github.com/sparkjsdev/spark) `main@ffe210dc0a45d0515a06c9235878108112827d61` (MIT).

- `src/SplatSkinning.ts`: experimental Gaussian skeletal deformation with **dual-quaternion** and linear-blend options; packs bone weights/indices and uses GPU texture data for per-splat animation. Dual-quaternion mode aims to preserve volume better for rotations, but cartoon/exaggerated deformation, nonrigid topology and motion vectors remain difficult. This is a *reference feature*, not proof that animated splats outperform skinning meshes.
- `src/SplatPager.ts`: a **256×256 splat/page** logical pool (65,536 splats); address mapping, LRU page ownership, pages to fetch/upload and dynamic texture arrays. Its default page pool capacity and fetching policy should be evaluated against actual VRAM, not copied unchanged.
- `src/PagedSplats.ts` and `src/PagedSplatsFetcher.ts`: fetch ranges or whole chunk files with cancellation hooks, optional supplied bytes/source, and progressive asset-page loading.
- `src/SplatMesh.ts`, `src/SparkRenderer.ts`: programmable transforms/modifiers, LOD/foveated selection and renderer-side paging controls. Adjustable screen-pixel thresholds and behind-camera/foveal policies are useful hypotheses for large scenes.

**Important relationship:** Spark's paging can serve *deformed visual representations*, while PlayCanvas's spatial hierarchy serves *large scene detail selection*. They solve complementary issues. A future Worlds system should separate **storage paging** from **LOD selection** and **animation deformation**, rather than forcing all three into a single asset format.

## E — NVIDIA Vulkan: quality and architecture research, not our mandatory backend

**Repo** [nvpro-samples/vk_gaussian_splatting](https://github.com/nvpro-samples/vk_gaussian_splatting) `main@d2f603251b1b007c94ee07dd9c5579b7492af6fe` (Apache-2.0; check dependencies/assets).

Relevant source:
- `src/gaussian_splatting.cpp` creates and switches among raster/hybrid/ray paths, render targets, profiling and resource lifetimes. A GBuffer carries material/depth-related data used by hybrid modes. The project creates a Vulkan pipeline cache for variants.
- `src/splat_sorter_async.cpp` has a dedicated CPU sorting thread and records stage timing.
- `src/splat_set_vk.cpp` stores splats in buffers or images and explicitly handles device texture-dimension constraints, refusing unsupported large allocations in texture mode.
- `shaders/threedgs_raster.*.slang`, `threedgut_raster.*.slang`, `threedgrt_raytrace.*.slang`, `shaders/shading.h.slang`, `shaders/deferred_shading.comp.slang`: multiple render/shading families, not interchangeable simple 'Gaussian pixel' operations.
- [Public project deep dives](https://nvpro-samples.github.io/vk_gaussian_splatting/) cover splat rasterization, unscented transform projection, lighting/shadows and ray-tracing tradeoffs.

**Transferable lesson:** choose the representation, transparency/visibility model and physically meaningful material contract **together**; independently correct GPU sorting alone does not make a renderer PBR-compatible. Keep paths for alpha accumulation, RT and PBR as optional experiments. Require capability flags and measured per-feature regressions across AMD/NVIDIA/other GPUs.

## F — What we should build ourselves, and what we should reuse

| Topic | Best existing baseline | Proposed Worlds-specific research outcome |
| --- | --- | --- |
| Simple Godot rendering | MIT GDGS Compute + Raster | Run unchanged in standalone Godot 4.8 project; identify real RD/compositor ABI divergences |
| Mesh → splat | EA Mesh2Splat (license review) | Independent opt-in source-mesh derivative that retains normal/PBR attribute semantics |
| PLY/PBR import | EA writer vs GDGS reader | Versioned canonical material-aware splat record, explicit attribute negotiation, safe fallback |
| Large-scene loading | PlayCanvas unified streaming | View-aware spatial demand and hard **GPU byte**/IO budget, with resident coarse fallback |
| Splat LOD | splat-transform decimation and PlayCanvas balancer | Explicit spatial bounds, provenance, quality error, coverage and temporal validity |
| Dynamic splat data | Spark pager/skinning | Optional deformable visual representation with present/previous transforms and shadow controls |
| Alternate renderer quality | NVIDIA Vulkan and stochastic papers | Quality reference scenes for lighting/transparent/occlusion and feature-gated experiments |
| GPU update economy | PlayCanvas work-buffer + Worlds sparse update research | Persistent presentation buffer + generational IDs, coalesced updates, bounded staging |
| Compatibility | Normal Godot mesh/material/SceneTree | No mandatory changes to regular games, physics or Worlds-ECS |

## G — Source-only proof queue

### P0: synthetic import semantics

Make one small **independent** CPU test fixture that includes both standard 3DGS PLY and PBR-extended PLY attributes. Expected decoded/retained fields must be explicit: `position, rotation, scale, opacity, SH/color` plus optional `normal, metallic, roughness`. Verify that unknown attributes are preserved in metadata or explicitly reported *ignored*. Reject NaNs, invalid lengths/strides and unsafe counts. A source-only analyzer can prove which fields the existing GDGS importer ignores, but cannot prove its actual rendering.

### P0: independent spatial residency invariants

Using synthetic bounding volumes and LOD levels (not real camera content), test:
- selected LOD represented by resident data or a visible coarse fallback;
- node bounds enclose full ellipsoid extent, not just mean positions;
- requests are deduplicated by resource identity; old requests cannot revive released generations;
- current, staging and retiring allocations stay under a separately specified **hard byte budget**; if the lowest LOD cannot fit, report/route to conventional mesh proxy rather than silently exceed;
- camera teleport and two cameras do not reuse stale view-dependent order/history.

### P1: direct material-aware conversion

Derive a reference from a *simple, freely authored triangle mesh* with known UVs and PBR material. Record expected normals and roughness across texture seams. No claim about renderer benefit until physical lighting and alpha artifacts are tested. Preserve source geometry for collision and fallback.

### P2: rendering evaluation, deferred

GPU tests eventually compare sorted quad, tile compute and stochastic/ray alternatives on the same meshes/captured assets, including depth, color, lighting, transients and P95/P99 time. Estimate peak sort/tile buffer memory, avoid source-specific hard-coded capacities, include rapidly moving camera and thin alpha foliage.

## H — Anti-patterns and license boundaries

- Do not make every textured mesh a splat at import: conversion may increase raster/temporal overhead and can obscure sharp hard edges.
- Do not claim Mesh2Splat PBR material fields survive a GDGS import **without an extension**; they currently do not.
- Do not equate `lod-meta.json`, `.sog`, `.spz`, `.ply`, `.glb` or GDGS's internal serialized Resource merely because all describe Gaussians.
- Do not use a *splat count* or compressed file size as the sole VRAM budget.
- Do not replicate a WebGPU/RTX-specific rendering path into Godot without a portable, shader/material-correct fallback.
- Do not distribute imported copyrighted scans/demo assets unless independently allowed.
- Do not transplant noncommercial INRIA code or AGPL OpenSplat implementation into an MIT-distributed module.
- Do not assume a permissive project license resolves its vendored third-party dependencies and brand/trademark permissions.
- Private Unreal fork is **read-only**, unrelated to any of these code reviews.


## I — Offline capture, tools, and compressed interchange (additional code audit)

The complete asset pipeline is not just runtime rasterization. We also studied the following public-source modules because **asset memory and training/authoring throughput** affect real-world feasibility.

### I1 — Niantic SPZ v4: robust compressed interchange

**Source:** [nianticlabs/spz](https://github.com/nianticlabs/spz) `main@d5abdee9b37c426a0b66b961c3d43b5857a24f4f`, MIT; `src/cc/load-spz.cc` and `src/cc/zstd-batch.cc`.

- The v4 file path uses a fixed-size header and independent, Zstandard-compressed attribute streams; older gzip-based formats retain a separate legacy read path.
- Source validates packed attribute lengths against the declared point count and SH degree. It also constrains implausibly large declared point counts relative to compressed file size to avoid obvious allocation explosions. These are **useful format-validation requirements**, not proof that every malicious file is harmless.
- It supports parallel compress/decompress of independent streams, which is useful at import time and can enable selective *attribute* decoding. This does **not** automatically enable view-dependent spatial streaming: the file still needs chunk/index data and renderer-defined residency semantics.
- **For Worlds:** keep SPZ as optional **offline interchange** initially. If decoding at runtime, use explicit hard maximum points, decompressed bytes, attribute stride, failure states, checksum/provenance and backend-supported SH bands. Do not assume compressed bytes approximate peak VRAM.

### I2 — SuperSplat editor: shared resource lifetime and GPU-side authoring

**Source:** [playcanvas/supersplat](https://github.com/playcanvas/supersplat) `main@b4f3b2557f8761170150f4766fa08c3ddcdfd5c5`, MIT; `src/editor-splat-resource.ts`, `src/import-analysis.ts`, `src/data-processor/`, `src/io/`.

- Editor resources are separate from scene *instances* and can be shared by several editing layers. This is highly relevant to preventing massive duplicate GPU allocations when many objects reuse one splat source.
- Its source handles independent import components, material-data encoding and staged upload/sorting. Input import analysis recognizes sequences versus multi-file scenes rather than treating every file as one asset.
- SuperSplat/PlayCanvas's **editor heap usage** and runtime GPU memory are different measurements. Published editor wins are not automatically rendering improvements.
- **For Worlds:** first support familiar Godot import/editor workflows; a new splat-specific inspector can expose provenance, source/canonical attributes, compression quality, resident vs full count and preview. Build conversion/optimization asynchronously and cache derived assets by content hash.

### I3 — Brush and gsplat: keep reconstruction optional

**Sources:** [ArthurBrussee/brush](https://github.com/ArthurBrussee/brush) `main@1388f74c6fe0236f68ee4915564bf00e9d2e3747` (Apache-2.0), [gsplat](https://github.com/nerfstudio-project/gsplat) `main@512d366b67073d77ca099ede742683c165dfc23b` (Apache-2.0).

- Brush provides reconstruction/training plus visualization using Rust/Burn/portable GPU tooling; its README covers COLMAP/Nerfstudio datasets and image masks, including mobile/browser experiments. Benchmark/realtime claims belong to the author and differ by platform.
- gsplat contains CUDA/PyTorch differentiable kernels and several raster/compositing configurations. `gsplat/rendering.py` exposes a mixed-batch versus parallel-batch distinction for tile processing. Useful as a published *quality/algorithmic reference*; not a reasonable mandatory production dependency for a Godot multi-vendor engine.
- **For Worlds:** model importers should accept output from **several independently chosen** reconstruction tools; ordinary game use should not require CUDA, a trained model, PyTorch or downloading a proprietary pretrained dataset.

### I4 — Combined pipeline insight

A scalable import stack has at least **four different roles** that should not be conflated:

1. **Capture or source mesh:** photos/videos/trajectory (offline reconstruction) or GLB/mesh/material (Mesh2Splat-style conversion).
2. **Art direction/quality:** SuperSplat-style editing, filtered bounds, opacity cleanup, per-material PBR attributes and offline quality estimation.
3. **Storage/streaming package:** PLY/SPZ interchange, SOG versioned textures or a versioned Worlds regional asset with explicit chunk dependencies.
4. **Runtime:** Godot-native backend, per-view sorting/depth/compositing, priority residency, shadows and temporal correctness.

Adapting step 3 does not automatically improve step 4, and a physically correct source mesh does not ensure a downstream splat shader is relightable. This separation lets the engine preserve standard scenes, editor imports and independent simulation state.

## Continuation when no GPU is available

The next independent work that is actually feasible is a **small, testable CPU-only import record + spatial residency model**, not production renderer integration. First compare manifest/field validation and memory caps against the source research above; record PASS/FAIL but **not GPU speedups**. Source-verify the current Godot 4.8 `Image`, `RenderingDevice`, `CompositorEffect`, texture/asset importer contracts once a native experiment is justified.

See [41 project/license survey](41-gaussian-splatting-project-survey-2026.md), [42 hybrid architecture](42-independent-hybrid-splat-rendering-architecture.md), [40 temporal quality](40-representation-continuity-and-2026-rendering-research.md), [27 legal source separation](27-license-and-independent-implementation-protocol.md), [28 AI handoff](28-ai-research-handoff-and-implementation-map.md).

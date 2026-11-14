# 42 — Worlds Engine: independent hybrid Gaussian-splat rendering architecture

**Status:** original engineering specification, source-verified integration candidates, unimplemented/unmeasured. Authored 2026-11-13 without GPU hardware. Read the [project/source survey](41-gaussian-splatting-project-survey-2026.md) first. Godot renderer architecture and [format/temporal quality](40-representation-continuity-and-2026-rendering-research.md) remain authoritative for normal scene behavior. **Do not translate proprietary Unreal code**; no Unreal source has been used as a public implementation specification.

## Objective

Make splats an **optional visual asset class** with depth-correct coexistence with meshes, predictable memory use, correct temporal state, streaming and editor import. Splats should be attractive for photographic/static/distant scenery, not forced onto every dynamic game object. The engine must remain a normal general-purpose Godot and Worlds-ECS remains optional/engine-independent.

The core scientific question is whether a source-correct, quality-controlled hybrid representation yields **higher visual quality for equal or lower total frame time and memory** than an optimized mesh + material + existing LOD/impostor arrangement under the *same* scene and camera path. This can only be established with later hardware testing.

## Existing Godot plugin code audit (not benchmarked)

The MIT [GDGS 3.3 plugin](https://github.com/ReconWorldLab/godot-gaussian-splatting) already separates:
- `addons/gdgs/importers/gaussian_import_plugin.gd` and decoders/builders: decode many file formats into shared resource data.
- `runtime/render/backend/gaussian_backend_selector.gd` and `gaussian_render_backend.gd`: select Compute or Raster once at startup; gracefully fall back.
- `runtime/render/compute/gaussian_scene_registry.gd`, `gaussian_gpu_state_cache.gd`, `gaussian_render_manager.gd`, `gaussian_renderer.gd`: scene management, stable GPU state, batching, projection, sort, render and compositor output.
- `runtime/compositor/gaussian_compositor_effect.gd`: compositor/depth interaction, debug overlays, offscreen GPU texture and render-thread setup.
- `runtime/render/raster/raster_data_textures.gd`, `raster_sorter.gd`, `raster_sort_job.gd`, `raster_render_backend.gd`: packed data textures, camera-relative global sort, worker lifecycle and Godot transparent-pass integration.
- `runtime/lighting/` and editor `lighting/bake/`: per-splat irradiance modulation with baked normal/AO proxies; meshes capture shadows from a proxy, but splats do not have generally valid BRDF inputs.
- Headless and visual tests in the external project's `tests/` directory.

**Source-specific lessons for our prototype:**
1. SceneTree access and render-thread work must be separated. GDGS Compute manager deliberately collects node state on the main thread, then transfers a snapshot to rendering; no SceneTree mutation inside renderer callbacks.
2. The two backends have **different depth, sorting and color-space semantics**. Their outputs are not mathematically interchangeable simply by pointing at the same data.
3. A raster compatibility implementation may reduce memory and benefit from hardware depth, but camera sorting can lag and output is view-dependent.
4. GDGS uses its own assets/resources and startup backend selection. Its importer recognizes SOG but current decoder documents v2; future versions/formats need explicit conversion/version gates.
5. The plugin's API contract and tests are a valuable baseline. We do **not** need to recreate all of its functionality before testing it.

## Suggested optional engine-facing contracts (no classes landed)

### `WorldsSplatAsset` — immutable content derivative

| Field/category | Purpose |
| --- | --- |
| Source identity | content hash, size, copyright/provenance, import-tool version, originating coordinate convention |
| Core data model | Gaussian count, position/orientation/scale convention, opacity, covariance, available SH bands and color-space assumptions |
| Content variants | static, animated/time-sampled, relightable-with-proxy, physically authored material, collision-proxy availability |
| Storage | source/container type + format version, optional compressed streams/chunks, integrity hash, decompression parameters |
| Spatial structure | conservative world/local bounds per region, stable per-region IDs, parent/fallback/LOD relationships, render visibility masks |
| Budget | serialized bytes, estimated decoded CPU bytes, packed GPU bytes, expected temporary sorting/tile memory per view |
| Quality | per-level error descriptor and quality capability flags; unknown ≠ zero error |
| Platform | required RD features, endianness, float precision, decoder version and safe downgrade/fallback policy |

**Do not embed Worlds-ECS entity IDs in the asset format.** A visual instance may reference a durable simulation entity through an optional bridge but its buffers and lifetimes are separate. Imported assets must validate lengths, counts, overflows, byte offsets, NaN/Inf, scale bounds, unsupported SH degrees, and third-party metadata before allocation.

### `WorldsSplatVisual3D` — opt-in scene representation

A normal scene node/provider (name tentative) holds `WorldsSplatAsset`, transform, visual layers, visibility and effect-quality requirements. It does not own physics/world simulation. Maintain independent presentation handle + generation, and optional regular mesh representation as fallback. For initial work, **use GDGS's existing `GaussianSplatNode`** in a standalone project instead of introducing a redundant node type.

### `WorldsSplatView` — each view owns its sort/history

A camera/viewport record includes projection, clip planes, output size, camera movement/cut epoch, origin transform, exposure/color-space, render mode, z convention, depth buffer identity, desired resolution and resource budget. Each view (game camera, stereo eye, editor view, reflection/shadow view) requires its own visibility and sorting assumptions; never share stale sorted indices across unrelated views without correctness proof.

### `WorldsSplatResidency` — coordinated but isolated from whole-mip streaming

Resource states: `Absent → Requested → Downloaded → Decoded → UploadPending → Resident → Retiring`; unexpected failures transition to `Failed` or fallback. All pages/chunks have dependency reference counts and an identity generation. A resident coarse fallback is preferred whenever fine detail is missing. Actual GPU buffer lifetime and visibility fence integration must use Godot's real RD ownership mechanism, not guessed execution order.

**Budget independently:** compressed disk bytes, CPU decoded bytes, staging upload bytes, persistent GPU splat data, per-view sort/candidate buffers, per-tile duplicate lists, temporary old+new frames and shared lighting/collision proxies. Never report 'splat data size' as total VRAM.

### `WorldsSplatRenderer` — backend adapter interface

Proposed modes to **compare**, not prematurely implement:
- **R0 — existing GDGS Raster** (control): hardware quad splats in Godot transparent pass with global CPU ordering. Maximum compatibility, imperfect ordering and potential camera lag.
- **R1 — existing GDGS Compute** (control): GPU sort/tile blend with compositor depth handling. May use more VRAM; Forward+ only.
- **R2 — selective GPU-owned sort/compaction** (original experiment): portable RenderingDevice compute passes with bounded work and no mandatory CPU readback; compare against R1/R0, and leverage existing Godot indirect capabilities. Use conservative bounds, size-based skipping and safe overflow behavior.
- **R3 — sorting-free stochastic transparency** (separate research): investigate ICCV 2025 [StochasticSplats](https://ubc-vision.github.io/stochasticsplats/) via public paper and MIT demo. Must account for noise, temporal accumulation, ghosting and per-pixel sample cost; it is **not** an automatic performance win.
- **R4 — ray/hybrid Gaussian PBR** (longer-term): public NVIDIA Vulkan renderer reference; strictly feature-detect and use normal raster controls on devices without ray tracing.

R2/R3/R4 are **not approved runtime patches**, not expected to outperform R0/R1 automatically, and not proposed as platform-wide replacements.

## Frame lifecycle and invariants

1. **Acquire view and state:** on main thread gather visible visual providers, transforms, dirty epochs, resource identity and view/projection settings.
2. **Coarse spatial selection:** choose conservative candidate regions, with unknown bounds included and new/teleported regions never skipped.
3. **Budget/stage:** pin required coarse fallback; request desired fine chunks, coalesce IO and GPU uploads; use explicit max byte/work budgets with graceful quality degradation.
4. **Project/cull:** for resident candidate Gaussians, reject only provably invisible and respect original pixel scale/SH rules. Model splat coverage cost (screen tiles, alpha overdraw) rather than just number of Gaussians.
5. **Select method/order:** use correct per-view transparency semantics; global alpha ordering approximations and tile-exact sort must be tracked as separate quality modes. Do not mix alpha-sorted and weighted/stochastic transparency blindly.
6. **Shade/composite:** integrate depth and color spaces; preserve opaque Godot meshes, sky, exposure, transparency, motion and TAA/upscalers; avoid accidental double-lighting of captured radiance.
7. **Track temporal validity:** camera cuts, changes in mesh/splat representation, opacity/animation, depth, illumination, residency, and SH/color revisions must invalidate the affected history. Crossfade only with explicit quality and motion guarantees.
8. **Retire resources:** wait for outstanding GPU use, remove old views/pages without stale resource refs, report exact memory/counters and fallback events.

## Hard visual/correctness gates

- **Opaque interop:** splats entirely behind a Godot wall are not visible; near splats appropriately appear in front without depth halos or perspective mismatch.
- **Transparent interop:** glass/water/particles and splats have explicit ordering/approximation; if physically accurate mixing is impossible, document a restriction and fallback.
- **Camera cuts:** no stale per-view ordering; no ghosts from reused projection/sort buffers; bounded first-correct-frame latency.
- **Animation:** current and previous transforms and per-splat motion/deformation validity prevent TAA smearing; do not claim a position-only velocity field captures deformation.
- **Day/night:** capture-time shadows/lighting remain visible for baked-radiance 3DGS unless material decomposition exists. A proxy modulation is not a physically accurate shadow receiver. Full PBR and cast/receive shadows are an independent asset-authoring problem.
- **Geometry/collision:** generated collision mesh is approximated geometry, not authoritative splat collision; gameplay collision and navigation remain separate and validated.
- **Large-world precision:** do not encode vast coordinates without a documented origin/precision model; camera-relative positions can help but require stable view and physics transforms.
- **Scene validity:** independent view/layer behavior, editor vs runtime, multiview, texture import/reimport, hot shader reload, malformed assets and buffer-capacity exhaustion.
- **Small-scene fallback:** no expensive GPU sort/raster infrastructure for a tiny object if conventional impostor/mesh is better.

## Mesh-derived Gaussian splats: important additional asset path

[EA SEED Mesh2Splat](https://github.com/electronicarts/mesh2splat) provides a published example of converting `.glb` meshes directly to Gaussian surfaces using existing triangles/material/texture data and exporting splat `.ply`. This suggests an additional opt-in importer path: `Godot mesh/GLB → geometry/material-aware splat derivative → independent shader/sorting/backend`, **always preserving the original polygon mesh**. A renderer capable of per-splat PBR channels/normal/shadows could relight mesh-derived Gaussian surfaces more plausibly than ordinary photographically baked Gaussian radiance. The conversion cannot improve source geometric truth and does not necessarily improve render throughput or peak memory. Tightly curved triangles, UV seams, skeletal deformation, dense alpha foliage, collision, motion vectors, transparency and per-splat sorting must remain independent correctness gates.

**Verified integration blocker:** Mesh2Splat's PLY writer exports `nx/ny/nz`, `metallicFactor` and `roughnessFactor`; GDGS's `standard_ply_decoder.gd` and 60-float runtime asset do **not** retain them. Any material-aware pipeline needs a versioned optional per-splat material payload, importer validation, shading integration and fallback, not just a conversion utility. Also preserve ordinary captured-radiance rendering as a separate material class. See [43](43-splat-source-audit-and-implementation-lessons.md).

**Licensing caveat:** Mesh2Splat's actual `LICENSE.txt` differs from the MIT label in `CITATION.cff`; do not include its code until the applicable redistribution terms/marks and dependency licenses are resolved. Its authors' sub-ms conversion report is hardware/workload-specific. [41](41-gaussian-splatting-project-survey-2026.md) includes the source-level finding.

## Formats and import architecture

**Initial neutral interchange:** binary PLY with documented properties; external conversion via permissively licensed [splat-transform](https://github.com/playcanvas/splat-transform) or [SPZ](https://github.com/nianticlabs/spz). Avoid implementing every codec at once.

**Recommended asset-flow design:**

`Asset capture / offline training (Brush or gsplat) → optional SuperSplat cleanup → splat-transform/SPZ export → Godot project importer → versioned WorldsSplatAsset → optional per-region compressed chunks → renderer backend`

- Maintain source format and license/provenance; preserve raw source data when necessary.
- Distinguish **SOG v2** (GDGS parser), **newer SOG v3** (PlayCanvas), **Streamed SOG** multi-file metadata (`lod-meta.json`) and **SPZ v4**. Decoder acceptance is version-specific; no 'all Gaussian formats supported' promise.
- `Streamed SOG` is a concrete **reference design**, not necessarily a format for direct engine-native runtime. We can pre-convert offline and keep a separate stable game-ready manifest.
- Compressed size does not predict GPU working set; unpacked splat coefficient and sorting buffers must be measured.
- Support an *empty but valid* asset and corrupt-content recovery; no unchecked allocation from untrusted headers.

## Scalability hypotheses and costs

For each candidate representation compare **total** costs:
- Geometry/visual bytes = packed Gaussian fields + SH + CPU metadata + visibility/LOD hierarchy + texture/proxy data.
- GPU frame = projection/culling + sorting/binning + overlap compositing + material shading + depth + temporal cleanup + synchronization.
- Streamed scene = IO + decompression + staging/copies + sort index rebuild + visual fallback, **including transients**.
- Editing = importer and derived asset rebuild time + editor VRAM + cache invalidation and render-thread stalls.
- Quality = silhouette/depth, view-dependent colors, opacity errors, temporal noise, lighting consistency and normal/roughness fidelity.

**Performance can scale poorly despite low draw calls** when Gaussians cover large portions of the screen, alpha overlap grows, tile list duplicates explode, or every camera move changes order. It can also excel at photographic detail in captured static assets that require complex geometry/material authoring otherwise.

## Hardware-free experiments feasible immediately

1. **Format validator test:** inspect header/version/metadata with synthetic benign and malformed PLY, SPZ v4 and SOG v2/v3 samples. Test caps on point counts, byte offsets, SH and decompression expansion. This tests decoders only, not image quality.
2. **LOD hierarchy state model:** generate synthetic 2D/3D region bounds, view frusta, memory budgets and camera cuts. Assert conservative coverage, fallback existence, no use-after-free and bounded load queues.
3. **Ordering model:** for synthetic overlapping Gaussians, compare CPU reference exact per-pixel compositing to global/depth-bucket and alternative approximations. Record alpha/color error with known ground truth and deterministic seed.
4. **Asset provenance manifest:** automated license/source references, content hashes and missing-format reporting; no bundled third-party scan dataset until reuse permission is established.
5. **Interop call graph:** compare GDGS with Godot `RenderingServer`, `CompositorEffect`, `RenderingDevice`, `MultiMeshInstance3D`, view depth, transparency and motion vectors. Identify which points actually require engine modifications.
6. **Design review:** estimate peak buffer memory using actual candidate formats and conservative worst-case tile duplication; this is an analytical cap, not expected measured VRAM.

All results must label **CPU-only** or **analytical**, and cannot be used to claim real-time frame performance or physical correctness.

## First practical future GPU experiment (when hardware is available)

Use a **standalone** Godot 4.8 fork project, not a default engine patch. Pin GDGS version/commit and import a redistributable test capture. Compare:
- one ordinary textured mesh LOD control, one well-tuned billboard/impostor, GDGS Compute and Raster, with the same output resolution/scene dimensions;
- one 50/50 splat+mesh collision/occlusion setup;
- static, walk-by and instant 180° camera cut;
- changing directional/point lights and capture-time baked illumination;
- small/large splat counts, memory pressure, multiple viewports, and scene unload/reload;
- cold vs warm, p50/p95/p99 CPU & GPU frame time, actual peak VRAM, sort and tile temporary bytes, color/depth and temporal error.

Do not count 'frames per second' in isolation, or compare a relit mesh with a baked-radiance splat as if their material representations were equivalent.

## Adoption gates and decision tree

**Gate 1: compatibility** — plugin/test runs on 4.8 fork and a fallback method always renders regular Godot projects. **Gate 2: quality** — scene depth and ordinary materials are not silently broken. **Gate 3: memory and latency** — measured frame and VRAM can meet target budgets without uncontrolled allocation. **Gate 4: streaming** — large scenes can be progressively loaded with stable fallback and bounded IO/transient memory. **Gate 5: production workflow** — imported assets have clear provenance, editor support, collision constraints and stable serialization.

If a gate fails, **keep splats as optional imported background content** or defer. Do not make Worlds Engine depend on splat rendering for NPCs, ordinary lighting, or physics.

## Sources and relationship to earlier work

- [41 — evaluated projects and licenses](41-gaussian-splatting-project-survey-2026.md)
- [30 — stable GPU instance identity/visibility](30-gpu-instance-visibility-design.md)
- [32 — resource streaming lifecycle](32-residency-streaming-contract.md)
- [38 — Godot whole-mip streaming pipeline](38-texture-streaming-end-to-end-trace-and-validation.md) (**distinct** from splat-region paging)
- [39 — sparse transform update data transport](39-sparse-instance-update-cost-and-gpu-selection.md)
- [40 — representation continuity and temporal lighting](40-representation-continuity-and-2026-rendering-research.md)
- [27 — licensed source separation](27-license-and-independent-implementation-protocol.md)

**Decision currently:** add an **independent, optional splat research lane**; **do not** merge a renderer or promise superiority until feature/fallback/hardware gates pass.

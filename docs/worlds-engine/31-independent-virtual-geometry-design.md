# 31 — Independent virtualized geometry experiment and geometry research

**Status:** proposed; no geometry format, shader or importer code committed. **Not a Nanite reverse-source port.** The specification uses published cluster/meshlet/LOD concepts, existing MIT meshoptimizer and our independent requirements.

## Research question

Can an optional Godot-compatible *adaptive detail asset* render very high source-detail environments at lower CPU/GPU time and/or memory than ordinary imported meshoptimizer LODs, at comparable pixels, shadows and material quality? If yes, can it handle dense foliage/procedural geometry where conventional continuous surface clustering can suffer?

This does not mean arbitrary polygon count becomes free. It reallocates work and can increase preprocessing, memory or material costs.

## Public and permissive starting points

- Godot already vendors `thirdparty/meshoptimizer` **version 1.3** (confirmed in bundled `meshoptimizer.h`, and `thirdparty/README.md` records MIT license and 2026 upstream revision). APIs include meshlet builders, flexible/spatial variants and cluster bounds. Upstream's `demo/clusterlod.h` is a **separate example**, not automatically part of the Godot vendor tree. Review original provenance/license before integrating an external file.
- Open meshoptimizer project (MIT): https://github.com/zeux/meshoptimizer . Public APIs cover meshlets, bounds, simplification and `clusterlod.h` clustered LOD experiments. **Prefer reuse with attribution to independently recreating mature meshlet algorithms.**
- Khronos Vulkan `VK_EXT_mesh_shader`: https://www.khronos.org/blog/mesh-shading-for-vulkan . Optional hardware path only; portable compute+indirect must be first-class.
- Epic's *public* Nanite overview: https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine . It demonstrates a use case, not a source license or mandatory implementation structure.
- Epic's aggregate geometry caveat: https://dev.epicgames.com/documentation/unreal-engine/working-with-naniteenabled-content .

## Prototype progression

**G0 — instrument imported LOD:** Godot meshoptimizer LOD, visibility ranges and multi-region MultiMesh are strong preexisting baselines. Record triangle count, projected coverage, temporal edges, CPU/GPU load, memory and import time.

**G1 — fixed clusters without streamable hierarchy:** offline partition an imported static mesh using a documented MIT meshlet builder; calculate conservative bounds and render with an independent GPU cluster visibility pass. Use the *same single opaque material* across control/test. Prove compaction, draw, bounds and camera traversal.

**G2 — independent multi-level detail:** create multiple simplification levels with a public algorithm; bound per-level screen-space error and ensure every fine region maps to valid fallback detail. Start with **whole-mesh** LOD selection and then evaluate independent region selection once transition consistency is verified. Avoid introducing cracks from independently simplified neighboring clusters.

**G3 — streaming and residency:** make only a high-level subset resident; demand/prefetch fine detail using [32](32-residency-streaming-contract.md), render coarse fallback while waiting. Measure cold camera cuts.

**G4 — material and geometry classes:** multiple surfaces/materials, two-sided alpha masked foliage, procedural/deformed meshes, terrain, skinning and shadow participation. Never claim G4 support while only G1 works.

**G5 — alternate representations:** deliberately compare leaf-card, whole-canopy impostor and procedural fine detail against dense-triangle clustering. Route per content class, not according to ideology about meshlets.

## Proposed asset contract (our own, version to be designed)

`AdaptiveMeshAsset` consists of:
- a stable source mesh reference plus **unmodified ordinary Godot fallback**;
- derived geometry chunks each with conservative bounds and a documented simplification error metric;
- parent/fallback relationships independent of the runtime GPU traversal design;
- material-group identity and any required vertex-attribute compatibility;
- optional streaming chunks with checksums and dependencies;
- import metadata: source hash, meshoptimizer version, build settings, builder version, platform feature variant and provenance;
- debug stats: original triangles, per-level triangles, bytes, build seconds, max surface error, valid seams.

This is a functional contract, *not* a fixed proprietary codec, cluster size or file structure.

## Error and LOD decision specification

For an object-space approximation error `e`, a simple conservative projected error is proportional to `e * projection_scale / camera_distance`, with special handling for near-plane crossing, orthographic projection and bounds visibility. Real implementation must use appropriate camera and bound conventions and validate against reference imagery.

Selection goals:
- use a user-set pixel-error budget rather than fixed world distance;
- avoid oscillation with hysteresis and temporal stability;
- never select a nonresident chunk without fallback;
- detect non-manifold boundaries, degenerate triangles, normal divergence and UV/material discontinuities;
- make skirts/seams or compatible simplification choices where discontinuities would otherwise appear;
- allow a higher-cost reference mode to measure true visual error.

**Crack-free is a test obligation**, not something hierarchy automatically provides.

## Data path separation

**Import/build thread:** read Godot `ImporterMesh` / mesh surfaces; validate indices, bounds, transforms, attributes, materials; build derived clusters/LODs using permitted algorithms; write versioned artifacts. Keep source resources intact.

**Runtime scene:** attaches an optional adaptive-asset reference to a normal scene object; maintains object transform and material override; collects view requests.

**Work selection:** CPU coarse object candidates; GPU fine cluster choice only when justified; maintain bounds and resident state.

**Submission:** prefer existing Godot RenderingDevice graph/indirect. Start hardware raster; do not assume mesh shader availability. A specialized compute raster path is a separate, evidence-driven experiment.

**Shading:** keep standard material fallback. Do not render an unlit custom shader then claim parity with a full PBR Godot mesh.

## Metrics and counterexamples

- **Contiguous surfaces:** high-resolution terrain, scanned stone wall, detailed sculpture, architecture.
- **Aggregate surfaces:** dense tree canopy, intersecting grass clumps, strands/ropes.
- **Dynamic content:** transform-only movement vs vertex deformation vs skeletal skinning.
- **High material entropy:** many unique materials/textures, transparency, decals.
- **Cameras:** tiny distant object, flythrough, near-plane contact, teleport, stereo pair.
- **Residency:** near-full VRAM, missing chunk, corrupt chunk, cold-start, repeated backtracking.

Score total GPU/CPU ms, import/build time, resident bytes, disk bytes, visible and processed triangle counts, pixels shaded more than once, percent of violated error bounds, P99 stalls, incorrect/missing primitives, shader compile variants and editor editability.

## Important negative findings

- Whole-MultiMesh LOD selection already exists and is highly efficient in many cases; the cluster system must outperform the **best subdivided** arrangement, not only an intentionally poor single giant MultiMesh.
- Vegetation aggregation and masking can resist standard simplification; representation switching may be more appropriate than increasing cluster granularity.
- Mesh shader support is optional and varies across GPUs; the user's Radeon RX 5700 may not support every advanced path. Query hardware capabilities rather than guessing.
- Custom raster visibility must integrate motion vectors, shadows and materials before being considered production-capable.
- Geometry residency thrashing can consume all gains from fine-grained clustering.
- A scene with few triangles but expensive pixels is shading-bound; a geometry path might have little effect.

## First development ticket

Build G1 as a single opt-in benchmark with a documented imported mesh set, a meshoptimizer-based meshlet derivative, conservative GPU frustum visibility and standard shading baseline. Publish geometry overlay and 100%-visible cost before implementing hierarchy, streaming or exotic rasterization. If the project lacks supported GPU functionality, prepare source-only feasibility notes and wait for actual hardware benchmark data.

Cross-reference [30 visibility](30-gpu-instance-visibility-design.md), [32 residency](32-residency-streaming-contract.md), [34 materials](34-materials-graph-and-temporal-reconstruction.md).

# 40 — Representation continuity: high-detail geometry, foliage, animation and temporal lighting

**Status:** original engineering research hypothesis with source/public-paper audit; **not implemented, benchmarked or demonstrated superior quality**. Written 2026-11-13. Complements [21](21-frontier-rendering-research.md) and [31](31-independent-virtual-geometry-design.md), which explain the *portfolio* and meshlet prototype. This document addresses the previously underspecified problem of keeping quality and temporal history correct **while the representation changes**.

## Design motivation: geometry and lighting cannot be optimized independently

We can render fewer polygons and still create **worse** images: moving silhouettes pop, alpha-masked canopies lose density, reflections shift, temporal denoisers retain stale history, and a new level of detail can invalidate previously reused lighting samples. Optimizing only cluster count or triangle count risks an illusion of improvement.

Worlds Engine's ambitious long-term differentiator should be *appropriate representations with explicit continuity requirements*, not one universal technique. Unreal's publicly documented Nanite/Lumen systems demonstrate the value of specialized pipelines; the publicly documented weaknesses of aggregate geometry show why no single format wins everywhere.

This is independent research. Private Unreal source is read-only comparison material and **does not supply implementation instructions, copied shader logic or data layouts**. Source policy: [27](27-license-and-independent-implementation-protocol.md).

## What the current Godot fork already contains

**Godot 4.8 beta source-verified at the audited checkout:**
- `thirdparty/meshoptimizer/meshoptimizer.h` identifies **meshoptimizer 1.3**. It exposes meshlet construction, flexible/spatial clustering, cluster bounds, simplification and related geometry utilities. `thirdparty/README.md` records MIT licensing and upstream provenance. The fork's vendored source contains library routines; the **separate `demo/clusterlod.h`** example from upstream is *not automatically bundled* into the fork.
- `scene/resources/mesh.cpp` has mesh-surface LOD metadata and APIs; ordinary imported LOD is an existing control.
- `servers/rendering/renderer_rd/effects/taa.cpp` uses depth, motion, previous motion and history in a temporal resolve; `fsr2.cpp` has motion-vector and history integration. New rendering paths **must** preserve valid velocity/depth or explicitly invalidate unsafe history.
- `servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp` tracks prior/current MultiMesh transforms when motion vectors are enabled.
- `servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp` supports ordinary scene materials, passes and MultiMesh indirect draws. GPU cluster-only geometry is not enough to claim general compatibility.

**Correct inference:** a new virtualized asset format must be integrated with depth, motion, shading, shadow and streaming lifecycles. The fact that Godot has an existing temporal/upscale path is not proof that it supports arbitrary geometry-topology changes.

## What 2026 public research adds

### A. Continuous clustered LOD is available from a permissive source

The upstream [meshoptimizer project](https://github.com/zeux/meshoptimizer) publishes a standalone [clustered LOD demonstration](https://github.com/zeux/meshoptimizer/blob/master/demo/clusterlod.h). It provides a useful **independently licensed comparison implementation**; the library is MIT licensed, but any files integrated must carry appropriate copyright/license notices. Pin the specific upstream commit and audit any transitive code when prototyping.

**Implication:** do not spend months recreating meshlet partitioning before comparing against meshoptimizer's published cluster+LOD approach. Still evaluate actual geometry seams, compression, material splits, source import integrity and memory. Upstream experimental APIs may evolve; keep a versioned adapter instead of depending on internal details throughout the renderer.

### B. July 2026: LOD changes can break temporal lighting reuse

[Wang et al., *Real-Time Level-of-Detail Rendering with ReSTIR*, SIGGRAPH 2026](https://research.nvidia.com/labs/rtr/publication/wang2026levelofdetail/) addresses a specific problem: prior sample reuse can become invalid when a mesh changes topology between detail levels. The authors report a method for continuity across topology-changing LODs. This establishes that **geometric approximation and temporal lighting history are coupled**, not that their method is immediately compatible with Godot or should be copied into the engine. The paper publication/license is not an automatic software-license grant to its possible implementations.

**Worlds Engine research response:** establish a *general temporal continuity contract* first; use conservative invalidation for changes without independently verified correspondence. Study published cross-LOD correspondence/temporal reuse as a later optional advanced experiment. The expected benefit and complexity remain unmeasured.

### C. September 2026: deformable ray-tracing representations can be much cheaper

AMD GPUOpen's [Holger Gruen overview of tetrahedral cages](https://gpuopen.com/learn/how-tetrahedral-cages-significantly-reduce-bvh-memory-usage/) describes research in which coarse deformable cages allow large detailed geometric data to remain shared/static while animation modifies a lightweight enclosing representation. AMD's demonstration reports major BVH update/memory reductions for a high-end RT workload; **those are AMD's results on its own hardware**, not Worlds Engine estimates. This is related to animated high-detail vegetation, crowds and creatures but is **RT-capability gated** and not a reason to make ordinary animation depend on ray tracing.

**Research response:** eventually compare deformable proxies, ordinary skeletal skinning and non-RT raster foliage on relevant hardware. Avoid declaring billions of triangles fast in our fork because a published specialized demo achieved that in another engine/hardware environment.

### D. Public Unreal aggregate-geometry warning

[Epic's public Nanite guidance](https://dev.epicgames.com/documentation/unreal-engine/working-with-naniteenabled-content) explains why leaves/hair/grass may resist contiguous-surface simplification and fine occlusion: discontinuous layers become partially covering volumes. **Research response:** compare foliage representation switching (instanced blades, alpha cards, opacity-preserving impostors, procedural generation, clusters) rather than treating dense triangles as always preferable.

## Proposed independent architecture: representation contract

**Goal:** a conventional Godot mesh can continue to work unchanged. Only opt-in assets register alternative derived representations.

Conceptual entities, **not defined runtime structs**:

| Contract | Required state | Why |
| --- | --- | --- |
| Source asset identity | source content hash, material revision, importer/version, transform-space convention | deterministic rebuild and cache invalidation |
| Candidate representation | class, valid material modes, geometric error, displacement envelope, content size, supported backends | avoid selecting an incompatible path |
| Draw continuity | current and previous transforms; view/projection epoch; render layer, motion-vector availability | support TAA/upscalers and scene queries |
| Representation continuity | previous and current derivative, transition epoch and confidence of correspondence | identify changes that invalidate history |
| Lighting participation | whether material/depth/shadow/RT/GI proxies are valid and quality-matched | prevent mismatched shadow or reflections |
| Residency state | ready coarse/fallback, optional higher detail, dependency version and in-flight references | avoid missing geometry and stale GPU data |
| Temporal effects | per-effect validity decision, disocclusion flag, history owner/view lineage | do not reuse incorrect results after swaps |

Proposed general interfaces:
- `WorldsRepresentationRegistry`: independent asset-derived candidates; *no* simulation entity ownership.
- `WorldsRepresentationSelection`: choose cost/quality-valid candidates per view/region; default ordinary Godot mesh.
- `WorldsContinuityReport`: changed bounds, material/deformation/representation epochs, motion certainty and whether prior history remains usable.
- `WorldsEffectHistoryGate`: individual effects decide retain/reproject/invalidate using public contracts. Avoid global invalidation on harmless changes; default to invalidation when unsure.

Names are tentative and deliberately not recreations of private Unreal class names or formats.

## A quality requirement is multidimensional

For a representative frame sequence, track independently:
1. **Silhouette/depth:** screen-space edge displacement, cracks, lost geometry, overdraw and depth accuracy.
2. **Materials:** tangent/normal correctness, roughness/specular stability, alpha coverage, UV derivatives and shader parity.
3. **Temporal appearance:** shimmer, LOD popping, ghosting, blur persistence, view cuts and fast motion.
4. **Lighting:** shadow silhouette, penumbra consistency, GI radiance changes, reflections and emissive contribution.
5. **Presentation:** first-correct-detail latency, memory/VRAM residency, cross-fade artifacts, animation mismatch and renderer feature fallback.

A single weighted 'looks good' score cannot replace these axes until calibrated and validated against visual reference sequences. A representation must satisfy **hard error limits** for relevant axes before being chosen, and unsupported effects default to the current Godot path.

## Original staged research plan

**S0 — controls and formal provenance.** Validate unmodified meshoptimizer imported LOD and a high-quality reference sequence. Record original assets and whether they are legally reusable. No proprietary shaders/material tables from Epic.

**S1 — continuous solid surfaces.** Compare classic mesh LOD, current meshoptimizer 1.3 meshlets and an independent grouped-cluster derivative. Preserve standard opaque material; verify bounds, no cracks and equivalent pixels. Keep initial 'all resident' variant separate from streaming.

**S2 — transient representation switching.** Alternate conventional LOD and experimental geometry on a moving camera. Verify depth and motion outputs, then add conservative invalidation of temporal history on the transition. Prefer visible but temporarily less accumulated image to stale, incorrect ghosting.

**S3 — foliage and opacity tests.** Use an independently authored tree/grass fixture, wind animation and multiple light/view directions. Compare card/instanced/procedural/cluster/impostor representations at *equal alpha coverage and shadow appearance*, not only triangle reduction.

**S4 — per-effect history validity.** Add versioned dependency reasoning for TAA, reflections, shadow caches and GI probes, one effect at a time. Test invalidation and camera cuts before attempting sophisticated reuse across LODs. Study Wang et al. only via its public paper and independent technical design.

**S5 — RT deformables (optional).** Only if hardware/backend capabilities exist; compare coarse cage representation against skinned/fully updated BVH and raster controls, including construction time, deformation error and ray/shadow fidelity.

**S6 — adaptive selection (last).** Introduce rule-driven per-view selection based on measured quality, cost and resource residency. Never use a learned cost predictor without a robust fallback and independently measured training data.

## Formal transition correctness

A representation change is **valid** only if:
- current pixels are drawn from resident, correctly synchronized data, or a visible fallback;
- bounds conservatively include both possible variants during crossfade/dynamic transition;
- old and new material attributes meet their declared compatibility requirements;
- an effect reuses history only if its input identity/geometry/material/view dependencies remain valid; uncertain inputs invalidate;
- multi-view and reflection/shadow cameras have independent validity, not a single shared 'visible' bit;
- emitted motion vectors correspond to the actually rendered surface where support is claimed, not merely object origin;
- cache generations prevent a streamed-out, replaced or reused asset handle from reviving stale data.

A render path may **opt out** of a particular feature with a clear conventional fallback. It must not silently disable required shadows or produce different image quality while claiming a speed improvement.

## Decision priorities without hardware

| Priority | Can resolve from source or CPU logic now | Blocked until graphics profiling |
| --- | --- | --- |
| P0 | Source inventory, license provenance, representation contracts, bound/error validation, asset metadata | cross-path GPU draw and culling cost |
| P1 | meshoptimizer import compatibility, original reference hierarchy and opaque-only asset plan | equal-quality pixel error in actual moving scenes |
| P1 | per-effect history validity state machine and deterministic epoch tests | temporal ghosting, TAA/FSR motion quality |
| P2 | foliage fixture plan, continuity/error requirements | alpha overdraw, animation and shadows |
| P3 | cage-RT literature and feature-gating requirements | real RT BVH cost and speed |

**Research outcome:** our ambition to surpass existing rendering engines is not just a geometry-throughput problem. Improving **representation continuity and cache correctness** is an independent route to higher visual quality at comparable budgets. It is currently a **hypothesis**, not a demonstrated result.

Related: [39 — sparse scene update costs](39-sparse-instance-update-cost-and-gpu-selection.md), [31 — virtual geometry](31-independent-virtual-geometry-design.md), [33 — lighting/shadow invalidation](33-lighting-shadow-and-temporal-cache-design.md), [34 — material/temporal integration](34-materials-graph-and-temporal-reconstruction.md), [38 — texture streaming](38-texture-streaming-end-to-end-trace-and-validation.md).

# 28 — AI engineering handoff: durable rendering research record

**Research note:** implementation contracts [30](30-gpu-instance-visibility-design.md)–[34](34-materials-graph-and-temporal-reconstruction.md), benchmark queue [35](35-phase-1-validation-and-next-actions.md). No private Unreal code was used as a public implementation specification.

**State as of 2026-11-13:** Phase 1 research, not an implemented renderer upgrade. This file is the **first file to read in a fresh AI session** after the [documentation index](README.md). The intent is to preserve *decisions, rationale, implementation proposals, dependencies, and unknowns* rather than rely on memory.

## Latest priority decision (2026-11-13)

The user explicitly chose **stability and conventional mesh rendering as the default**. Next focus is normal Godot renderer baseline/correctness, GPU-driven instance visibility, clustered/virtualized geometry, and shared streaming/residency, with benchmark/feature-flag/fallback gates. Gaussian splatting is **optional and deferred**, not a dependency or replacement; [44](44-splat-asset-foundation-implementation-plan.md) is a research-ready splat plan only. No GPU benchmark exists to justify preferring splats for general-purpose scenes. See [DEC-012](15-decisions-and-open-questions.md) and [35](35-phase-1-validation-and-next-actions.md).

## Hardware-unavailable continuation (2026-11-14)

**Hardware testing is unavailable; it is a future acceptance gate, not the next actionable work item.** Continue deep public source audit and CPU-only correctness/performance-theory models. [48 — frame-safe rendering lifetimes](48-inflight-presentation-lifetimes-and-hardware-free-validation.md) now contains a **committed CPU reference** for generation-safe slot recycling, deletion tombstones, deferred upload packets, multiple in-flight camera frames and explicit fallback eligibility. **14 new CPU tests passed; 41 tests passed in a local rerun across the three visibility/indirect/lifetime suites.** A tombstone publication revision bug was found and fixed. GPU shaders, Godot parser, renderer integration and measured performance still have **no hardware validation**. **Completed next step:** [49](49-refcounted-slots-and-u32-upload-packet-contract.md) adds **O(1) per-slot frame reference tracking**, terminal-generation/revision wrap guards and an independently defined versioned 32-byte upload descriptor. **17/17 additional CPU tests passed** locally and checked against the committed source. This is a host-side contract, not an integrated shader format. Next hardware-free research: scene-epoch/world-reset integration, CPU instance-identity raster oracle and geometry-cluster/residency models. Do not keep suggesting GPU benchmarks as the immediate task while hardware remains unavailable.

## Scene-reset and CPU image-identity milestone (2026-11-14)

[50 — scene-epoch safe reset and full RGBA8 instance-ID oracle](50-scene-epoch-reset-and-cpu-instance-identity-oracle.md) extends `FrameSlots` to tag **slot+generation handles with a scene epoch** and use **begin_reset → drain prior frame tickets → complete_reset**. It refuses new experimental draws/uploads and late old-scene packets, preserves in-flight data, prevents epoch ABA, and retains monotonic frame ticket IDs. A second CPU-only model draws uniquely coloured triangles per slot in nonoverlapping tiles and compares **all pixels + exact missing/unexpected IDs** rather than a single green center pixel. **24 new CPU tests passed locally**; their three newly committed files match the tested local files, while the edited `FrameSlots` was source-patched from a locally tested equivalent. No Godot/GPU execution or renderer changes. **Next hardware-free work:** CPU-owned staging/upload budget with epoch+revision validation, then geometry clusters/residency. Hardware tests remain deferred.

## Latest CPU-only rendering prototypes (2026-11-14)

**[51 — immutable upload staging](51-bounded-immutable-staging-upload-reference.md)** implements a bounded queue of versioned, 16-byte-aligned payloads with 32-byte `WSP1` descriptors. It coalesces superseded writes, refuses unsafe in-flight slot mutations, retries failed simulated transfers, and holds staging allocations through a two-phase scene reset. **19/19 new CPU tests passed**, including 800 seeded interleavings. 

**[52 — geometry-page residency](52-geometry-page-residency-cpu-contract.md)** adds an independent synthetic page hierarchy with permanent coarse roots, per-view demand/epoch tracking, parent-first whole-page loading, strict resident/upload byte limits, transactional eviction planning and per-frame dependency holds. **14/14 new CPU tests passed**, including 500 seeded camera changes. The first draft failed dependency and unnecessary-eviction stress cases, which were fixed before commit. The local research directory ran **57/57 tests** across scene reset, image ID, staging and geometry suites; **this is not a complete repo-wide checkout/CI result**. Both new models' committed source is verified identical to locally tested bytes. Godot/GPU runtime and throughput are unmeasured; the normal renderer remains unchanged.

**Immediate hardware-free continuation:** add asynchronous page lifecycle with cancellation, failures and stale generation/scene completion guards; then experiment with LOD screen-space error and stable transitions. Preserve standard Godot meshes and the already-existing texture-streaming module. GPU tests are a later validation gate, not a blocker.

## Latest native source integration — ImporterMesh and Mesh LOD diagnostics (2026-11-14)

[59 — imported and runtime mesh topology adapter](59-imported-mesh-readonly-topology-adapter.md) maps source-verified Godot `ImporterMesh::get_surface_arrays/get_surface_lod_indices/get_surface_lod_size` and `Mesh::surface_get_arrays/surface_get_format/surface_get_lods` directly onto the portable `WorldsMeshTopology` auditors **without modifying importer resources or changing meshoptimizer simplification**. New `mesh_surface_source.h/.cpp` validates indexed/unindexed triangle streams, creates temporary sequential indices only for unindexed triangles, and rejects unsupported primitives, malformed counts and out-of-range indices. The standalone native fixture passed strict GCC and Clang C++17 builds plus GCC UBSan (17 assertions); files verified against GitHub hashes. The opt-in Godot `analyze_mesh_surface` and `analyze_importer_mesh_surface` methods and XML are committed, including LOD reports, but **native Godot compilation and the committed headless script smoke test are not run**. Module remains disabled by default. Next acceptance: enable module in a full Godot build and run `benchmarks/native_geometry/godot_mesh_source_smoke.gd`; then inspect real glTF import surfaces and derived meshlet edges. No GPU speedups measured.

## Latest CPU + native research milestone — hybrid proxy and true-position borders (2026-11-14)

[58 — hybrid coarse proxy and C++ position-aware border audit](58-hybrid-root-proxy-and-3d-mesh-border-audit.md) adds `benchmarks/theory/hybrid_topology_reference.py` (**12/12 newly committed CPU tests passed; 23/23 alongside earlier 11 root-policy tests**). Hybrid regional coarse roots are permanently drawable, while a lazily loaded distant aggregate proxy can represent the entire group with a single *synthetic* coarse submission. The new proxy consumes explicit extra memory; in-flight far frames pin it, admission is transactional, and camera cuts cancel stale proxy uploads. A far12→near12→far12 trace (4×4 regions, 88-byte resident cap) requires 22 model upload bytes, ends at 54 resident model bytes, and recovers one far submission, versus regional-only 12 upload/44 resident bytes and 16 far submissions. **Not GPU measurements or final quality evidence.**

The optional Godot module at `modules/worlds_geometry/` now also has portable C++17 `mesh_border_audit.h/.cpp` and a 13-fixture native test covering **exact-position welded topology** (distinguishes UV-split index edges from actual open geometry) and reverse-oriented 3D boundary sample comparisons (T-junction refusal; explicit distance tolerance). Both the normal strict-warning native build and UBSan run passed; the `WorldsMeshTopology` Godot-facing wrapper was extended with `analyze_position_surface` and `compare_border_samples`, and its XML parsed, but **Godot SCons/editor/GDScript execution is unverified**. Disabled-by-default module stays opt-in until the full build gate. Next: audit real `ImporterMesh`/`ArrayMesh` ingestion and validate aggregate proxies against actual mesh/material geometry before connecting to renderer work.

## Latest engineering milestone — regional roots and native Godot source (2026-11-14)

[57 — global/regional root comparison and native mesh topology audit](57-regional-geometry-roots-and-native-mesh-edge-audit.md) has two independently tested additions. `benchmarks/theory/root_topology_reference.py` compares one pinned global root with 16 pinned regional roots on **identical synthetic coarse bytes**, camera inputs and 24-byte/tick upload limit (**11/11 tests passed, including 1,200 seeded camera changes**). Regional roots can refine one focus region with 12 model upload bytes versus a global hierarchy's 44, but the unbatched far-view global root needs one coarse submission versus sixteen regional submissions; do not convert to measured speedups. A recommended **hybrid** combines independent regional streams with optional distant aggregate proxy geometry, with explicit extra proxy memory budget.

The Godot repo now contains an **opt-in native module** at `modules/worlds_geometry/` (`config.py:is_enabled() == False` so default builds are unaffected). Its C++17 `mesh_edge_audit.cpp` detects index-based open/nonmanifold edges, winding conflicts, duplicate/zero-area triangles and bad indices; **ten C++ fixture scenarios compiled and passed locally with g++ strict warnings**. The `WorldsMeshTopology` Godot scripting wrapper, registration and XML class docs are committed but **the full Godot engine was not compiled or run**. Later native build must enable `module_worlds_geometry_enabled=yes`. The original Godot renderer/texture-streaming paths remain unchanged. Next: native build gate when possible, geometric border equivalence, hybrid coarse proxy scheduler and real importer integration. Do not treat index topology as watertight triangle proof.

## Latest milestone — 2D coverage and camera workload simulation (2026-11-14)

[56 — 2D patch edge ownership and synthetic camera traces](56-2d-cluster-edges-and-synthetic-camera-traces.md) adds `cluster_2d_reference.py` and `geometry_camera_trace.py`, plus 13 + 10 passing CPU tests. The new layer rejects rectangular gaps/overlap, nonresident ancestry, mismatched adjacent edge profiles, T-junction vertex omissions and invalid/stale stitch certificates. It composes 21-page patch ownership with the independent async residency and projected-error LOD models across delayed IO/upload/frame completions, camera teleports and two-view demand. The trace distinguishes **missing requested LOD quality** from **excess sibling detail required to split a coarse root**, and reports byte budgets, safe evictions and cancelled tickets. **23/23 new local CPU tests passed; 96/96 in the available local directory including earlier uncommitted exploratory tests.** The exact four committed source/test files were checksum-matched to local executed bytes. **No native mesh import, Godot rendering or GPU hardware was tested.** Next: compare global versus regional coarse roots, validate actual mesh border triangles and describe an optional importer adapter. Keep standard Godot rendering default.

## Latest cluster review and seam-safe refinement (2026-11-14)

[55 — cluster ancestry bug and seam guard](55-cluster-seam-correctness-and-dependency-audit.md): **reviewed and locally ran** the prior ten coverage tests. Discovered the selector permitted resident grandchildren when their intermediate parent was nonresident; fixed and added one regression (**11/11 coverage tests passing**). Added `cluster_seam_reference.py` with canonical ordered quantized boundary profiles, optional exact-signature resident stitches, deterministic refinement suppression when adjacent profiles mismatch, and fail-closed irreparable coarse-root seams (**10/10 seam tests passing**, including 2,000 randomized masks). **73/73 available local Python tests passed**, including earlier exploratory async tests. This remains a synthetic 1D ownership/edge model, not a crack-free 3D mesh renderer. Next: 2D edge ownership and synthetic camera/residency/churn traces. Preserve normal Godot rendering; no GPU hardware tests available.

## New cluster coverage CPU contract (2026-11-14)

[54 — exact cluster coverage](54-cluster-coverage-cpu-contract.md) adds `cluster_coverage_reference.py` and `test_cluster_coverage_reference.py`. The independently authored model rejects overlapping/gapped child partitions, retains a resident coarse parent unless all requested child subtrees can cover the same region, and checks the selected union with an independent interval oracle. Ten deterministic tests including 2,000 randomized residency/refinement combinations are committed; **they have not been run in this turn**. This synthetic 1D interval contract does **not** prove 3D meshlet seam safety or GPU behavior. Next priority: execute tests, add shared-edge/seam compatibility, then compose page streaming + projected LOD + coverage under synthetic camera traces.

## Latest experimental milestone — async geometry and LOD (2026-11-14)

[53 — async geometry and screen-error LOD CPU models](53-async-geometry-lifecycle-and-lod-error-cpu-milestone.md) adds independent reference code to `benchmarks/theory/`. Simulated read/decoded/upload/resident stages have independent byte budgets; immutable generation/scene-epoch tickets reject stale IO/upload completions, and page reload invalidates derived descendants only after draw frames retire. Camera cuts cancel outdated demand but preserve requests from other cameras. Permanent coarse roots and transactional evictions ensure missing detail does not silently hide objects. A new LOD chain selector estimates conservative perspective/orthographic pixel error, handles near-plane crossing, enforces resident-parent prerequisites and uses hysteresis for stable transitions. **13 committed async tests + 14 committed LOD tests passed locally (27 total); a separate broader 25-test local async exploratory suite also passed but is not committed.** Exact committed source/test bytes match the locally executed versions. A hard-impossible-budget gate prevents futile read/retry loops. Godot/GPU hardware tests remain unavailable; no renderer C++ changes or speed claims.

**Next useful CPU work:** page streaming workload traces (fallback quality, fairness and eviction churn) and region/cluster LOD coverage and seam invariants. Do not ask for hardware as the next step.

## Project identity and non-negotiables

- Product: **Worlds Engine**, a public Godot fork and general-purpose engine, not solely a renderer for our simulation.
- Preserve Godot's editor, Node3D/scene workflow, C#, GDScript, import pipeline, conventional render paths, 2D and normal project compatibility.
- Aspirational target: scale scenes, animation, streaming and visual fidelity beyond present engines *in measured workloads*. This is not currently achieved.
- Worlds-ECS / WorldSim remains a separate, optional, engine-agnostic simulation. Renderer must never mistake an invisible visual for a destroyed simulation entity.
- Engine improvements are optional and backend-appropriate; fallback on standard Godot methods is mandatory.
- Never copy, transliterate, summarize into executable steps from private Unreal source, reproduce shaders, or infer permission to publish proprietary files. See [27](27-license-and-independent-implementation-protocol.md).
- Notes are written so a future AI can create an **original engine system based on open/public technical knowledge**, not reconstruct Epic's exact implementation.

## Pinned repositories and baselines

| Role | Repository / revision | Meaning |
| --- | --- | --- |
| Public output | `Azzirallas/Worlds-Engine` `master`, pre-audit baseline `6a8f3e91d98af788bcf7837e785b26b0500989c9` | `version.py`: Godot 4.8 beta |
| Licensed comparison | private `Azzirallas/UnrealEngine` `release` at `f45729c0b6f097038e72b52d366a62baeca3275b` | `Engine/Build/Build.version`: Unreal Engine 5.8.4 |
| Native benchmark | `benchmarks/rendering/` | Deterministic static/dynamic scenes, fixed/orbit/cut cameras and raw CSV + Python validator; **not executed or smoke tested on graphics hardware**. Four synthetic validator unit tests passed locally. |
| CPU-only research | `benchmarks/theory/` | Independent MultiMesh dirty-region/estimated-byte model; six deterministic tests passed locally. **Not actual engine transfers or GPU timing.** |

Do not assume either branch has remained unchanged. Recheck HEAD and engine version before every code change. Treat the private fork as legally controlled source, not a public dependency.

**GPU indirect drawing research (2026-11-14):** [47](47-guarded-indirect-and-offscreen-raster-probe.md) adds a 16-byte fail-closed indirect draw packet, compute finalizer and **separate offscreen indirect raster probe** (`benchmarks/gpu_visibility/offscreen_draw.tscn`). **13/13 new Python command tests passed** locally; the 12-scenario local RD fixture and raster shaders remain **unexecuted in Godot / on GPU**. It does *not* implement automatic fallback draw submission or production integration. Source enum detail: the fork binds `RenderingDevice.DRAW_CLEAR_COLOR_ALL`. Standard meshes remain default.

**GPU fixture follow-up (2026-11-14):** [46](46-isolated-gpu-visibility-feasibility-fixture.md) adds `benchmarks/gpu_visibility/` as an opt-in local RenderingDevice compute-frustum parity experiment, with bounded atomic output, diagnostics and ten test scenarios (including stale-generation diagnostics). Source-level shader/runner ABI checks passed **8/8**. **It has NOT been parsed, compiled or GPU-executed by Godot**; no FPS or actual GPU correctness claimed. Keep main renderer untouched and test with Forward+ graphics hardware later.

**Executable Phase 1 update:** [45 — generation-safe regional visibility reference](45-visibility-reference-milestone-and-gpu-gates.md) and [Python implementation/tests](../../benchmarks/theory/) added on 2026-11-13. **14 standard-library CPU tests passed** in a research container; includes multiview correctness, conservative bounds, coalesced writes, stale handle prevention, and non-lossy overflow fallback. This does **not** mean GPU-driven rendering is implemented or faster. The source check identified existing Godot `storage_buffer_create`, `buffer_update`, compute dispatch, indirect draw and graph resource usage APIs; their correct integration needs a Godot GPU smoke test. Keep ordinary mesh renderer default and do not route standard scenes through this model.

## What was actually established

- Godot has `RenderingDeviceGraph`, indirect draw/dispatch, multi-renderer pipelines (Forward+, Mobile, Compatibility) and existing meshoptimizer mesh LOD generation; rewriting these systems in Phase 1 is unmotivated.
- Godot's MultiMesh can reduce draw submission, but a MultiMesh is one spatial object and uses an aggregate LOD decision; a vast one can cause wasteful visibility and detail.
- Godot camera culling includes a parallel scan of scene instances; `DynamicBVH` is already used in other contexts. Both alternatives deserve measurements, not assumptions.
- MultiMesh per-instance setters use cached data and dirty-region uploads; bulk/mixed update behavior needs a benchmark, including possible initial readback transition. **New exact source finding:** dirty upload regions are 512 instances; exceeding 32 dirty regions (or half the visible regions) can trigger a full visible-buffer upload. Scattered low-percent edits might therefore cause disproportionate transfer; see the *unmeasured mathematical model* in [39](39-sparse-instance-update-cost-and-gpu-selection.md).
- Unreal's documented approaches combine GPU scene/instance data, fine geometry visibility, streamed hierarchical detail, material separation, cached GI and shadowing, and per-pixel bounded many-light evaluation. They solve different bottlenecks, with documented artifacts and memory costs.
- Godot's SDFGI is already a GI solution but has documented limitations with dynamic occluders and emissive surfaces.
- **New baseline discovery:** Godot 4.8 beta in this fork already includes a disabled-by-default texture-streaming module with GPU feedback, mip scheduling and optional memory budget. Do not propose building a texture streamer from zero; read [36](36-texture-streaming-baseline-audit.md) and the completed [38 — end-to-end source trace](38-texture-streaming-end-to-end-trace-and-validation.md); Forward+ **and Mobile** have feedback paths. Their practical correctness/throughput still need GPU testing.
- Godot already documents ubershader and pipeline precompilation strategies; Unreal's public PSO guidance suggests additional *measurement questions*, not justification to replace these systems. See [37](37-pipeline-stutter-and-pso-research.md).
- Godot's graph and 3D rendering already have nontrivial backend portability and shader/material constraints. Integrating advanced features is a product problem, not just writing a compute shader.
- Bundled **meshoptimizer 1.3** already exposes meshlet/cluster utilities; its publicly available external clustered-LOD demonstration is a distinct reference. New 2026 research on LOD-aware temporal reuse and deformable RT is covered in [40](40-representation-continuity-and-2026-rendering-research.md). Neither is a GPU benchmark of our engine.
- **Gaussian splats new research lane (no implementation):** [41](41-gaussian-splatting-project-survey-2026.md) audits public project licensing; [42](42-independent-hybrid-splat-rendering-architecture.md) specifies an optional hybrid system; **[43](43-splat-source-audit-and-implementation-lessons.md) now gives exact source paths and implementation lessons**. Most important verified blocker: EA Mesh2Splat's exported PLY stores `nx/ny/nz`, `metallicFactor`, and `roughnessFactor`, but GDGS's standard PLY importer only retains geometry/opacity/SH appearance, so it **drops that PBR material information**. PlayCanvas's current unified engine has hierarchical LOD, persistent GPU work buffer and incremental allocation reuse; splat-count budget does not guarantee VRAM cap. Spark implements paging and experimental dual-quaternion skinning. GDGS supports SOG v2 specifically; newer SOG/Streamed SOG needs version-specific conversion. **No GPU results or engine patch**.

## Reading sequence for a new developer/AI

1. [Vision and compatibility](01-vision-and-scope.md), [compatibility principles](02-principles-and-compatibility.md), [roadmap](12-roadmap.md).
2. [Phase 1 execution plan](19-phase-1-rendering-execution-plan.md), [Godot source map](20-renderer-call-graph.md), [existing renderer audit](17-renderer-source-audit-res-001.md).
3. [Unreal concept comparison](24-unreal-5-8-rendering-architecture-audit.md), [gap matrix](25-godot-renderer-gap-matrix.md), [source boundaries](27-license-and-independent-implementation-protocol.md).
4. **Deep subsystem specs:** [29 audit ledger](29-renderer-subsystem-evidence-ledger.md), [30 GPU scene](30-gpu-instance-visibility-design.md), [31 virtual geometry](31-independent-virtual-geometry-design.md), [32 residency](32-residency-streaming-contract.md), [33 shadows/GI](33-lighting-shadow-and-temporal-cache-design.md), [34 shading/compositor](34-materials-graph-and-temporal-reconstruction.md).
5. [39 sparse update/source cost model](39-sparse-instance-update-cost-and-gpu-selection.md), [40 cross-LOD/temporal continuity research](40-representation-continuity-and-2026-rendering-research.md), [41 splat project/licensing survey](41-gaussian-splatting-project-survey-2026.md), [42 independent hybrid-splat architecture](42-independent-hybrid-splat-rendering-architecture.md) and **[43 detailed public-code audit](43-splat-source-audit-and-implementation-lessons.md)**.
6. [35 validation and implementation sequence](35-phase-1-validation-and-next-actions.md).
7. [Research references](23-frontier-evidence-register.md) and primary public technical documents in each spec.

## Status definitions; no implicit promotions

- **Verified Godot source:** confirmed in fork; not necessarily validated on GPU.
- **Verified public documentation:** independently documented published technique or limitation.
- **Private source observation:** comparison context only, never a public algorithmic specification.
- **Proposed:** a Worlds Engine architecture we designed; unimplemented and unmeasured.
- **Prototype:** code exists, compiles and can run, but need not be production ready.
- **Measured:** controlled CPU/GPU hardware benchmark with full environment and quality notes.
- **Integrated:** engine feature landed with tests, fallback, documentation and regression guard.

When work advances, update *the status line and evidence* in this handoff; do not just modify random plan bullets.

## Principle: three orthogonal axes, not one large renderer rewrite

**Scene representation:** persistent render proxies and resources identify what exists (without determining simulation ownership).

**Work selection:** CPU/GPU decide what geometry, effects and detail actually contribute to each view; stream/check validity for missing data.

**Work execution:** Godot's RenderingDevice/graph executes the required draws and compute. Materials, lights, shadows, temporal buffers and platform fallbacks are consumers of this data.

This layering makes it feasible to try new geometry or lighting methods *without* replacing scene nodes or disabling the standard renderer.

## Suggested modules (names are original proposals; none exist)

- `WorldsRenderScene` — optional pool of stable presentation handles; lifecycle events; per-view data access.
- `WorldsChangeJournal` — coalesced per-frame state changes and epochs for rendering consumers.
- `WorldsRegionIndex` — coarse spatial grouping and candidate enumeration, separate from Godot's existing BVH until benchmarked.
- `WorldsVisibilityLab` — GPU-visible IDs, independent culling tests, indirect draw setup.
- `WorldsGeometryAsset` — experimental hierarchical cluster derivative of an existing mesh with always-available conventional fallback.
- `WorldsResidencyLab` — request priority, load/upload budgets, safe eviction and telemetry.
- `WorldsPresentationPolicy` — controlled representation choice with hysteresis and quality error bound.
- `WorldsLightingLab` — isolated invalidate/refresh prototype for one shadow or GI effect.

No module is approved to merge merely because it appears here.

## Main research decisions

1. **Don't rebuild RenderingDeviceGraph.** First measure missing functionality and command-graph CPU cost.
2. **First engineering control:** improve/validate `benchmarks/rendering` for high count, visibility fractions, dynamic updates, and shadow/material variants.
3. **First experimental candidate:** GPU resident instance table and GPU fine visibility, compatible with ordinary mesh rendering.
4. **Second experimental candidate:** static opaque clustered mesh lab with independent meshlet preprocessing and conventional mesh fallback; use Godot's already-vendored MIT meshoptimizer where appropriate.
5. **Parallel architectural research:** explicit resource residency and scene-change epochs to budget costly work.
6. **Lighting later:** one cached effect experiment, with correctness/quality gates. Avoid rebuilding full Lumen/MegaLights.
7. **Feature flags and fallback** from day one. No surprising change to ordinary Godot projects.
8. **Optional splat representation research:** GDGS as the Godot baseline, PlayCanvas unified streaming and Spark dynamics as public-permissive references, NVIDIA Vulkan for advanced graphics, Mesh2Splat for material-derived conversion. Read the **source-to-source import compatibility finding** in [43](43-splat-source-audit-and-implementation-lessons.md) before selecting asset formats. No default-engine integration yet.

## Implementation contracts that must survive context loss

- **Stable handle:** an implementation-defined handle plus generation; never a durable NPC or simulation identity. Deleting/reusing slots must not resurrect previous visuals.
- **Bounds:** conservative under transforms, skinning, WPO and motion; uncertainty defaults to visible.
- **Visibility:** false-positive draw is allowed; false-negative missing geometry is a correctness bug.
- **LOD:** enforce pixel-error/camera constraints, hysteresis and crack-free seam handling; selected data must be resident.
- **Residency:** a dependency cannot be evicted while referenced; low-detail fallback must always render.
- **Temporal data:** caches carry their input epochs and view lineage; camera cuts, material/light changes and dependency changes invalidate relevant history.
- **Threading:** no Godot SceneTree calls from worker/GPU code unless explicitly allowed; RenderingServer ownership and render-thread requirements are respected.
- **Platforms:** check features; use conservative compatibility path for unsupported devices.
- **Metrics:** CPU and GPU timings, P50/P95/P99, upload bytes, VRAM/RAM, output quality, correctness, cold-start and streaming stalls; report *unmeasured*, never invented metrics.

## Explicit unresolved questions

- Does Godot 4.8 RenderingDevice expose the synchronization/indirect/compute capability needed for an isolated proof without changing internal renderer code?
- Is the bottleneck on our actual low/midrange GPUs CPU scene culling, draw submission, GPU overdraw, memory upload, shading, or some other effect?
- What practical threshold should switch from plain MultiMesh to GPU selection?
- Can the experimental meshlet path preserve Godot shader semantics and surface/material variation without multiplying compilation variants?
- Can scene-change journals reduce shadow/GI work without invalidation bugs?
- Which Vulkan/Direct3D/Metal graphics features can be relied on in tested hardware?
- Does the proposed representation portfolio outperform meshoptimizer LOD on foliage and dense static meshes, or does complexity outweigh wins?

## Next action

**Hardware temporarily unavailable.** Continue exact source call-path audits, extend the existing [CPU-only model](../../benchmarks/theory/README.md) for generation-safe visibility/bounds, license/provenance review and design specifications [39](39-sparse-instance-update-cost-and-gpu-selection.md)–[40](40-representation-continuity-and-2026-rendering-research.md). Those can validate logical properties, *not* graphics speed or pixel quality. Keep the existing native benchmark ready but marked **not run**. When suitable graphics hardware becomes available, resume [35](35-phase-1-validation-and-next-actions.md): baseline first, then an independently designed GPU instance visibility proof. Do not rewrite the production renderer, translate proprietary Unreal internals, or claim superiority without actual measurements.

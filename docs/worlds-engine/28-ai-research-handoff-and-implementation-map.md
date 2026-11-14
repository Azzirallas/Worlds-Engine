# 28 — AI engineering handoff: durable rendering research record

**Research note:** implementation contracts [30](30-gpu-instance-visibility-design.md)–[34](34-materials-graph-and-temporal-reconstruction.md), benchmark queue [35](35-phase-1-validation-and-next-actions.md). No private Unreal code was used as a public implementation specification.

**State as of 2026-11-13:** Phase 1 research, not an implemented renderer upgrade. This file is the **first file to read in a fresh AI session** after the [documentation index](README.md). The intent is to preserve *decisions, rationale, implementation proposals, dependencies, and unknowns* rather than rely on memory.

## Latest priority decision (2026-11-13)

The user explicitly chose **stability and conventional mesh rendering as the default**. Next focus is normal Godot renderer baseline/correctness, GPU-driven instance visibility, clustered/virtualized geometry, and shared streaming/residency, with benchmark/feature-flag/fallback gates. Gaussian splatting is **optional and deferred**, not a dependency or replacement; [44](44-splat-asset-foundation-implementation-plan.md) is a research-ready splat plan only. No GPU benchmark exists to justify preferring splats for general-purpose scenes. See [DEC-012](15-decisions-and-open-questions.md) and [35](35-phase-1-validation-and-next-actions.md).

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

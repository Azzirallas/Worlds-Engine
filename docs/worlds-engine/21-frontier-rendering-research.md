# 21 — Frontier rendering research: beyond contemporary engine limits

> **Status:** research strategy / speculative architecture. No claims of implementation, scientific novelty, or outperformance. Date: 2026-11-13. Complements [Phase 1 plan](19-phase-1-rendering-execution-plan.md), not a replacement for honest benchmarking.

## The actual ambition

Worlds Engine is not only an attempt to make Godot faster. We want to research rendering architectures that *may surpass contemporary engines on relevant, measurable workloads*: dense living worlds, effectively unlimited detail under bounded resources, large amounts of individually moving content, high quality lighting, fast streaming, and minimal content-authoring overhead.

Keep the *user interface and ordinary API* near Godot while allowing experimental rendering modes to diverge under the hood. Do not mistake catching up to an existing commercial feature for an original innovation.

**Technical principle:** performance scales with *perceptible work*, not the number of things in the simulated world. The engine should spend cycles where they change the output or user experience.

## Two concurrent Phase 1 tracks

### Track A — Baseline engineering (must continue)

Reproduce Godot 4.8 GPU/CPU bottlenecks and characterize RenderingServer, culling, instance update, dynamic meshes, lighting and streaming; exploit existing GPU compute/indirect paths and measure against conventional Godot primitives. This is the **control group**, not the ceiling. It is how we establish credibility and avoid replicating working technology.

### Track B — Frontier research (starts immediately, design only)

Research and independently prototype alternative representations, GPU-generated work, temporally amortized scene updates, intelligent residency, deformable acceleration structures and advanced lighting. Compare against both Godot and strong contemporary techniques where comparable reference implementations are legal and available.

The existence of a published paper warrants a hypothesis, not a decision to transplant its code or claim its demo speed.

## Core research hypothesis: representation-adaptive rendering

Instead of assuming every object must be a traditional mesh draw, consider **a representation portfolio**. An asset may have zero or more representations:

- Standard mesh with existing material, import and LOD.
- Cluster/meshlet hierarchy with page-wise residency and projected-error selection.
- Parametric/implicit surface generating local detail on demand.
- Region-batched instances or a compact instance/visibility representation.
- Coarse impostor / field / billboard for tiny projected objects.
- Highly dense geometry rendered through a compute/software path where advantageous.
- Ray-tracing-friendly deformable cage + shared static fine geometry, on supported hardware.
- Optional specialized point/gaussian representation for suitable background/scanned content; never assumed to replace ordinary game geometry or interaction.

**Selection inputs:** projected coverage, depth/occlusion, camera speed, motion/deformation, importance, ray/lighting participation, expected draw/compute cost, memory residency, cache state, hardware feature support, required shading correctness and transition stability.

**Original architectural proposal:** a *renderer representation registry* can associate asset derivatives and costs, and a *work selector* can choose implementation per camera and region. Start with offline choice and explicit authoring, not a hypothetical perfect learned scheduler. Later research adaptive online decisions with stable hysteresis.

**Potential advantage:** different classes of content receive more effective rendering than a single geometry path. **Risks:** shader/material incompatibility, transition artifacts, extra asset memory, duplicated pipelines, hard-to-debug performance cliffs. Every experiment must justify its complexity.

## Candidate F-01 — GPU-resident geometry work selection

Goal: multi-level cluster/page hierarchy + conservative visibility; GPU compaction and indirect dispatch with bounded CPU involvement. Distinguish:

1. CPU coarse region selection / predictive streaming.
2. GPU fine-grained cluster visibility.
3. Error-controlled level selection with crack-free transitions.
4. Visibility-buffer or traditional shading path.
5. Shadow/reflection use of geometry with independent quality budgets.

Research both mesh shaders (where supported) and compute + indirect fallbacks; do not assume mesh-shader availability on all GPUs. A cluster system is not automatically the proprietary Nanite architecture.

**Gate:** on a dense, partially visible scene, beat an optimized ordinary MultiMesh + mesh LOD baseline on CPU cost and total frame time with equivalent quality; no unacceptable popping or VRAM growth.

## Candidate F-02 — Hybrid hardware/software rasterization

Recent research shows software rasterization can outperform fixed-function rasterization on *specialized very dense opaque triangle* workloads. Research a dispatch rule that routes these workloads to a compute path while preserving hardware rasterization for mixed materials, transparency and ordinary meshes.

Potential differentiator: editing and procedurally generated ultra-dense surfaces without requiring full offline LOD preprocessing.

**Gate:** characterize crossover points: projected triangle size, mesh counts, material complexity, geometry edits and GPU architectures. Must not force CUDA on a general-purpose multi-vendor engine. Reject if compute overhead erases benefit in actual game scenes.

## Candidate F-03 — Deformation-independent ray tracing

Research low-cost *deformation proxies* (e.g., tetrahedral cages) allowing many copies of high-resolution deforming assets to share static fine-geometry acceleration data, where ray-tracing hardware supports it.

Possible applications: wind-responsive foliage, animated distant creatures, high-detail crowds, dense flexible objects.

**Gate:** compare acceleration-structure memory/update cost, visual deformation error, ray cost and total frame time versus conventional hardware RT and rasterized animation. Cross-vendor capability plan essential. A non-RT fallback is required.

## Candidate F-04 — Persistent-world-aware temporal work

**Hypothesis:** in a world where much of the landscape and scene knowledge changes slowly, many expensive computations could have an explicit refresh policy instead of rebuilding each frame.

Research a unified *change/relevance budget* for geometry residency, shadows, GI probes/cache, visibility history, animation updates and distant materials.

- Event/dirty-driven updates must be conservative and versioned.
- Screen-space motion, camera movement and unexpected interactions can invalidate prior results.
- Importance is determined by perceptual error and gameplay relevance, not only camera distance.
- Physics, persistence, and rendering have distinct validity periods; never freeze critical interactions.
- Per-region history may support predictive prefetch and amortization, but memory and correction costs count.

**Potential advantage:** stable dense worlds might have better P95/P99 frame times than implementations that redo unnecessary work. **Risk:** stale shadows, ghosting, missed visibility and temporal invalidation spikes. Use explicit error budgets and emergency fallbacks.

## Candidate F-05 — Quality-preserving dynamic lighting

Evaluate reservoir sampling, radiance caching, cross-LOD sample reuse, hybrid traced/probe lighting and progressive shadow updates. Keep temporal stability and disocclusion as first-class metrics. The *research aim* is equivalent or higher perceived lighting quality at lower compute/VRAM cost in moving, streaming worlds, not merely copying an existing GI product.

**Gate:** under moving camera/light/geometry and LOD changes, improve image quality per millisecond with less visible ghosting or similar error; report limitations in reflective/translucent scenes.

## Candidate F-06 — Procedural detail as an alternative to stored geometry

Research adaptive parametric surfaces and compact basis/field representations for vegetation, terrain detail, architectural repeats and deformable organic geometry. Generate only enough detail for visible coverage, not an entire tessellated world. Study convergence with collision/physics authored at lower resolution.

**Gate:** compare content size, generation cost, render cost, artist control, temporal stability and material compatibility versus imported LOD meshes and meshlet hierarchies.

## Candidate F-07 — World-aware, renderer-agnostic interest system

Explore a world-level interest interface that supplies visual, physics, audio and simulation interests **without** making Worlds-ECS mandatory. Render infrastructure uses interest to predict asset residency and representation transitions.

A persistent NPC can remain simulated even when it has no GPU representation. The renderer need not know the NPC's knowledge or goals. A bridge can provide relevant metadata; ordinary Godot games may use scene/camera-based heuristics.

**Potential benefit:** scale measured in *simulated entities per visible presentation cost*; lower Node and GPU handle churn while crossing streaming boundaries.

## High-risk future avenues

- Learned materials / neural shading / neural radiance caching: promising but inference cost, training complexity, determinism, portability and licensing require scrutiny.
- Work graphs / mesh nodes: expressive GPU scheduling on supported APIs, but cross-vendor/backends need fallback strategies.
- Sparse geometric/radiance data structures and meshless representations: evaluate after simple assets and workloads prove a gap.
- New image reconstruction algorithms: avoid treating AI as inherently superior; compare motion artifacts and net frame cost.

## What would count as surpassing another engine?

A scoped, independently reproducible result, for example:
- More *visible* moving foliage at same quality, output resolution, hardware, frame-time percentile and memory budget.
- More effective geometric detail at equivalent visual error and VRAM.
- Fewer worst-case stutters when streaming massive scenes, at the same traversal speed.
- Better GI error/temporal stability at comparable GPU time.
- Faster procedural editing and incremental rendering of extremely dense geometry.

Avoid generic 'better than Unreal' claims. Compare the actual task, assets, device, driver and build, and publish regressions.

## Research directions and source provenance

Source list in [frontier evidence register](23-frontier-evidence-register.md). The papers' reported metrics are not predictions for Worlds Engine. Directly copying proprietary algorithms or source is prohibited; licenses of all open-source sample code must be reviewed before any integration.

## Priority

Near-term: candidate F-01 with a **tiny GPU cluster visibility prototype**, informed by source audits and benchmarks, plus F-04 region/temporal budgeting. Medium-term: F-02 and F-06 where they show a measurable comparative advantage. Longer-term: F-03 and F-05 when adequate RT hardware and a rigorous image comparison suite are available.

The first prototype should be *bounded*: simple static opaque meshes, one viewport, one backend, no shadows or transparency; preserve standard rendering as a fallback. Expand only after measured success.

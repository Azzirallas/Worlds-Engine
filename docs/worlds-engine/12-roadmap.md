# 12 — Roadmap, sequencing and milestone gates

> This roadmap specifies investigation order, not a release schedule. No code milestone should be considered funded or approved merely by appearing here.

## Why rendering investigation first?

High-quality graphics and scalable environments are central to the project. However, the first task is not replacing the renderer; it is an accurate audit of where Godot spends CPU/GPU time and which newer features already exist. Improvements should add value to ordinary projects while keeping the editor almost unchanged.

## Stage 0 — Documentation and fork baseline (NOW)

- Preserve upstream README and project notices; introduce dedicated Worlds Engine documentation.
- Record source commit, branch, version, rendering paths and included physics modules.
- Define compatibility rules, architecture boundaries, testing methodology, research/licensing rules and open questions.
- Verify source inventory against actual fork files before citing implementation internals.
- Output: coherent reviewable plan and source map, with no engine code modifications.

**Exit gate:** documentation links resolve, design choices are labeled provisional or decided, current Godot features are not misrepresented.

## Stage 1 — Rendering and geometry baseline audit (CURRENT TECHNICAL MILESTONE)

Active source findings are in [RES-001](17-renderer-source-audit-res-001.md), [RES-002](18-res-002-multimesh-and-visibility.md) and the [renderer call graph](20-renderer-call-graph.md). Follow the [Phase 1 execution plan](19-phase-1-rendering-execution-plan.md); benchmarks are still pending.

- Trace SceneTree -> RenderingServer -> renderer/backend -> GPU.
- Map culling, MultiMesh, geometry LOD, material dispatch and GPU resource residency.
- Inspect what is possible through RenderingDevice, engine modules and existing APIs.
- Compare Godot's renderers and their hardware requirements.
- Construct repeatable reference scenes and initial profiling runs, beginning with unmodified fork/upstream-equivalent settings. A standalone scene-generation benchmark has been committed at [benchmarks/rendering](../../benchmarks/rendering/) and still needs a smoke run.
- Identify actual CPU draw submission, GPU shading, geometry, animation and streaming bottlenecks.

**Exit gate:** a documented list of problems ranked by severity, reproduction cases, upstream baseline data and at least two possible solutions per major bottleneck.

## Stage 2 — Low-risk rendering improvements

- First evaluate configuration and content-level gains.
- Consider improved batching/region MultiMesh management, reduced update overhead, better culling and profiler instrumentation.
- Favor isolated engine changes or extension APIs over sweeping rewrites.
- Ensure fast paths remain optional.

**Exit gate:** measurable benefit on at least one target scene with acceptable P99, correctness, compatibility and maintenance cost. Reject work that only improves synthetic peak FPS.

## Stage 3 — Advanced graphics proof of concepts

Parallel research tracks:
- Hierarchical geometry/meshlets/indirect draws/virtualized geometry.
- Better shadows and dynamic GI/reflections.
- Animation density, GPU skinning and representation LOD.
- GPU-driven visibility and residency.

**Exit gate:** measured visual-quality and cost comparisons; demonstrated fallbacks and capability gating; a decision whether to productize, defer or discard each track.

## Stage 4 — Large-world streaming and physics

- Budgeted world partitioning, terrain/region asset residency and coordinate precision.
- Jolt/GodotPhysics profiling, physics activation and optional destruction.
- Validate that existing scene workflow remains usable with large-world additions.

**Exit gate:** long traversals and stress runs without uncontrolled memory growth, unacceptable streaming stalls, lost persistent state or gameplay physics errors.

## Stage 5 — External simulation integration

- Introduce an optional independent connector to Worlds-ECS.
- Validate data ownership, deltas, representation transitions, thread safety and stable identity.
- Keep standard Godot development entirely functional without connector.

**Exit gate:** integration tests with realistic simulated/visible ratios, acceptable frame cost and no simulation data loss.

## Stage 6 — Productization and maintenance

- Cross-platform builds and rendering fallbacks.
- Importer/editor UX, comprehensive docs and compatibility testing.
- Rebase/upstream synchronization and publication of measured findings.
- Establish a stable feature/support matrix before releases.

## Priority policy

1. Correctness and compatibility are gating conditions.
2. Profiled renderer/geometry bottlenecks outrank speculative major rewrites.
3. World-streaming and physics paths may move earlier if benchmarks reveal they block rendering scenarios.
4. The optional ECS bridge should not dictate general-purpose engine architecture.
5. No promise of parity with specific proprietary features without independent tests.

## Next immediate actions

1. Finish documentation set and verify repo links.
2. Review fork renderer entry points and exact baseline version.
3. Produce an audit worksheet and benchmark definitions for SceneTree/RenderingServer/MultiMesh/culling.
4. Decide which single measured bottleneck is worth a first prototype.
5. Only then make an engine code plan.
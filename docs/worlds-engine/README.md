# Worlds Engine — engineering plan

> Status: research and planning, with source-level audits and an untested benchmark scaffold. No new rendering features are claimed implemented or measured.

Worlds Engine is a Godot-based, general-purpose game engine project aimed at substantially better scalability and modern 3D capabilities without sacrificing Godot's familiar user experience. This documentation is the durable project reference for development, review and handoff.

**Current source baseline (2026-11-13):** the fork's version.py identifies the checked branch as Godot 4.8 beta. Verify version.py and the commit before implementing; the baseline is not assumed frozen. This document set is specific to the fork and independent of upstream Godot's doc/ reference documentation.

## Start here

1. [Vision, scope, success criteria](01-vision-and-scope.md)
2. [Principles and compatibility contract](02-principles-and-compatibility.md)
3. [Existing Godot baseline and audit checklist](03-godot-baseline-and-audit.md)
4. [Proposed architecture and extension boundaries](04-architecture.md)

## Subsystem plans

- [Rendering, geometry, culling, materials](05-rendering-and-geometry.md)
- [RES-001: first renderer source audit](17-renderer-source-audit-res-001.md)
- [RES-002: MultiMesh and visibility source audit](18-res-002-multimesh-and-visibility.md)
- [Phase 1 rendering execution plan](19-phase-1-rendering-execution-plan.md)
- [Verified renderer call graph](20-renderer-call-graph.md)
- [Lighting, shadows and image quality](06-lighting-and-visual-fidelity.md)
- [Physics, destruction and collision scalability](07-physics-and-destruction.md)
- [Large worlds, streaming and procedural content](08-large-worlds-and-streaming.md)
- [Worlds-ECS and external simulation integration](09-ecs-and-simulation-bridge.md)
- [Editor, developer experience and backward compatibility](10-editor-and-workflows.md)

## Frontier research (beyond baseline)

- [Beyond contemporary engine limits: rendering research strategy](21-frontier-rendering-research.md)
- [Experimental renderer lab and prototype charter](22-experimental-renderer-lab.md)
- [Frontier research evidence and source register](23-frontier-evidence-register.md)

## AI implementation handoff and detailed original module contracts

- [AI engineering handoff: source baselines, decisions, next actions](28-ai-research-handoff-and-implementation-map.md)
- [Renderer subsystem evidence ledger](29-renderer-subsystem-evidence-ledger.md)
- [Original GPU instance and visibility design](30-gpu-instance-visibility-design.md)
- [Independent adaptive/virtual geometry design](31-independent-virtual-geometry-design.md)
- [Resource residency and streaming contract](32-residency-streaming-contract.md)
- [Lighting, shadows, and temporal invalidation](33-lighting-shadow-and-temporal-cache-design.md)
- [Materials, frame graph, and temporal reconstruction](34-materials-graph-and-temporal-reconstruction.md)
- [Phase 1 validation queue and AI continuation procedure](35-phase-1-validation-and-next-actions.md)
- [Existing Godot texture streaming audit and Unreal virtual-texturing comparison](36-texture-streaming-baseline-audit.md)
- [Shader pipeline, first-frame stutter and PSO readiness research](37-pipeline-stutter-and-pso-research.md)
- [Godot streaming end-to-end source trace, failure modes and test gates](38-texture-streaming-end-to-end-trace-and-validation.md)
- [Sparse instance movement, dirty uploads and GPU work-selection cost model](39-sparse-instance-update-cost-and-gpu-selection.md)
- [Geometry/foliage/animation continuity and 2026 temporal rendering research](40-representation-continuity-and-2026-rendering-research.md)

## Unreal rendering architecture audit (licensed-source research)

- [UE 5.8.4 rendering architecture audit](24-unreal-5-8-rendering-architecture-audit.md)
- [Godot-to-Unreal renderer gap matrix](25-godot-renderer-gap-matrix.md)
- [Phase 1 prioritized prototype specifications](26-phase-1-prototype-priority-and-measurements.md)
- [License and independent implementation protocol](27-license-and-independent-implementation-protocol.md)

## Execution and governance

- [Performance metrics, benchmark methodology](11-performance-and-benchmarks.md)
- [Phase 1 runnable rendering benchmark (not yet executed)](../../benchmarks/rendering/README.md)
- [Roadmap and stage gates](12-roadmap.md)
- [Research, sources and intellectual property](13-research-and-legal.md)
- [Upstream synchronization and release strategy](14-upstream-and-releases.md)
- [Decision log, unknowns and research backlog](15-decisions-and-open-questions.md)
- [Testing, correctness and validation](16-testing-and-validation.md)

## Project vocabulary

- **Verified existing:** observed directly in the fork or authoritative upstream documentation, with version/context recorded.
- **Proposed:** desired capability or architecture, not yet selected or implemented.
- **Hypothesis:** possible optimization requiring a benchmark or prototype.
- **Decision:** an explicitly chosen direction with rationale and revisiting criteria.
- **Implemented:** landed code with linked tests, benchmark data and documentation.
- **Deferred:** out of current scope, not abandoned.

Never convert a hypothesis into a performance claim without evidence. Do not claim Unreal-equivalent, Nanite-equivalent, Lumen-equivalent or Chaos-equivalent behavior by name alone.

## How work should be done

For each initiative: establish current upstream capabilities; write a narrowly scoped problem statement; construct a reproducible baseline; compare lower-maintenance options; prototype behind a feature flag; test correctness and performance; review regressions and platform impact; then adopt, revise or reject. Small changes should be preferred to wholesale rewrites when they achieve the same result.

No engine source changes are authorized by this documentation alone. Execution requires a separate implementation decision.
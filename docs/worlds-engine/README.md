# Worlds Engine — engineering plan

> Status: planning only. This directory describes intentions, hypotheses, evaluation criteria and future work. It does not claim these features have been implemented.

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
# Worlds Engine — engineering plan

> Status: source audits, CPU rendering-policy reference models, and an opt-in native mesh-diagnostic module now exist. There is **no validated replacement renderer or measured GPU speedup**; full Godot native integration and rendering benchmarks remain untested.

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
- [Gaussian-splat open-source project survey, comparative licenses and 2026 priorities](41-gaussian-splatting-project-survey-2026.md)
- [Original optional hybrid splat asset, streaming, rendering and quality architecture](42-independent-hybrid-splat-rendering-architecture.md)
- [Public splat-code deep audit: Mesh2Splat → GDGS material gap, PlayCanvas unified streaming, Spark paging and NVIDIA rendering](43-splat-source-audit-and-implementation-lessons.md)
- [CPU visibility correctness milestone: 14 passing tests, Godot RD integration requirements and GPU validation gates](45-visibility-reference-milestone-and-gpu-gates.md)
- [First isolated GPU compute visibility feasibility fixture: generation-safe selection and guarded command, awaiting hardware smoke test](46-isolated-gpu-visibility-feasibility-fixture.md)
- [Guarded indirect draw and opt-in offscreen raster probe: 13 passing CPU tests, full compute→draw path awaiting Godot/GPU execution](47-guarded-indirect-and-offscreen-raster-probe.md)
- [Frame-safe rendering lifetimes: CPU implementation, 14 new tests and 41-test combined pass without GPU hardware](48-inflight-presentation-lifetimes-and-hardware-free-validation.md)
- [Refcounted render slots and 32-byte versioned upload packet: 17 additional CPU tests, no GPU hardware required](49-refcounted-slots-and-u32-upload-packet-contract.md)
- [Scene epoch reset and CPU instance identity raster: 24 additional deterministic tests with no GPU](50-scene-epoch-reset-and-cpu-instance-identity-oracle.md)
- [Bounded immutable instance-table staging uploads and completion protocol: 19 CPU tests](51-bounded-immutable-staging-upload-reference.md)
- [Geometry-page residency, pinned fallback and safe eviction: 14 CPU tests](52-geometry-page-residency-cpu-contract.md)
- [Async geometry page lifecycle and conservative LOD transitions: 27 committed CPU tests](53-async-geometry-lifecycle-and-lod-error-cpu-milestone.md)
- [Exact cluster coverage and safe all-or-nothing refinement (11 CPU tests passing)](54-cluster-coverage-cpu-contract.md)
- [Cluster ancestry audit and seam-aware safe refinement (10 further CPU tests passing)](55-cluster-seam-correctness-and-dependency-audit.md)
- [2D patch coverage and integrated synthetic camera streaming traces (23 new CPU tests)](56-2d-cluster-edges-and-synthetic-camera-traces.md)
- [Regional versus global coarse geometry roots and opt-in native mesh audit (11 Python tests, standalone C++ checks)](57-regional-geometry-roots-and-native-mesh-edge-audit.md)
- [Hybrid regional streaming and distant proxy; C++ position-welded topology and 3D border checks (12 new Python tests, 13 C++ fixtures)](58-hybrid-root-proxy-and-3d-mesh-border-audit.md)
- [Read-only imported/runtime Mesh and LOD diagnostics, portable C++ tests and pending headless Godot smoke gate](59-imported-mesh-readonly-topology-adapter.md)
- [Offline meshoptimizer meshlet generation and independent exact-triangle verification (portable CPU tests; real vendor build pending)](60-offline-meshoptimizer-meshlet-validation.md)
- [Automatic triangle boundary extraction and derived cluster cache contract (portable CPU tests)](61-automatic-mesh-boundary-extraction-and-cache-contract.md)
- [WGC1 versioned meshlet-cache codec, strict decoder and 700 mutation tests](62-portable-meshlet-cache-codec.md)
- [SHA-256 source identity, atomic cache storage and automatic cache-miss regeneration](63-geometry-source-hashing-and-cache-store.md)

## Unreal rendering architecture audit (licensed-source research)

- [UE 5.8.4 rendering architecture audit](24-unreal-5-8-rendering-architecture-audit.md)
- [Godot-to-Unreal renderer gap matrix](25-godot-renderer-gap-matrix.md)
- [Phase 1 prioritized prototype specifications](26-phase-1-prototype-priority-and-measurements.md)
- [License and independent implementation protocol](27-license-and-independent-implementation-protocol.md)

## Execution and governance

- [Performance metrics, benchmark methodology](11-performance-and-benchmarks.md)
- [Phase 1 graphics rendering benchmark (not yet executed)](../../benchmarks/rendering/README.md)
- [CPU-only theoretical rendering models (no GPU hardware required)](../../benchmarks/theory/README.md)
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
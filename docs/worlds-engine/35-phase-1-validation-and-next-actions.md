# 35 — Phase 1 executable research queue, test gates and AI continuation procedure

**Status:** execution specification, **not a claim that tests or render prototypes have run**. Written 2026-11-13. Read [AI handoff](28-ai-research-handoff-and-implementation-map.md) first.

## Confirmed implementation priority (2026-11-13)

**Decision:** retain Godot's standard mesh renderer as the stable default. Prioritize **R-001/R-002 baseline and correctness**, then **R-003 GPU instance visibility**, **R-004 virtualized/cluster geometry**, and **R-005 shared residency / existing texture streaming verification**. R-009 Gaussian splats remain **optional, isolated research** and must not block or replace these core tasks. A splat asset importer is not the next mandatory coding milestone. Any fast path must be feature-flagged, have an unmodified baseline comparison, and fall back safely to conventional rendering. When GPU hardware is unavailable, work on source-verified renderer contracts and CPU-only correctness models rather than claiming performance wins. This decision supersedes the previous suggested execution order in [44](44-splat-asset-foundation-implementation-plan.md).

## CPU-only milestone and research mode (2026-11-14)

Graphics hardware is still unavailable, so **do not block development on GPU tests or position them as the immediate next action**. The optional GPU visibility/raster fixtures remain unexecuted for later. Meanwhile, [48](48-inflight-presentation-lifetimes-and-hardware-free-validation.md) implements the frame-safe presentation-slot reference model and documents a full **41-test local pass** across the visibility, guarded indirect-command and lifetime suites. The newest **14 tests** cover stale/out-of-order upload packets, multi-camera in-flight frames, deferred updates, quarantined slot reuse, buffer exhaustion and explicit fallback eligibility. No production renderer C++ edits have been made. **Those first two tasks are now implemented and tested** in [49](49-refcounted-slots-and-u32-upload-packet-contract.md): O(1) per-slot reference checks, 32-bit generation/revision exhaustion safeguards, a versioned 32-byte upload descriptor and **17 new passing CPU tests**. Next CPU/source tasks: world-reset scene epochs, CPU identity-raster oracle, and residency/virtual geometry contracts. GPU validation remains deferred.

## Epoch reset and identity image oracle (2026-11-14)

[50](50-scene-epoch-reset-and-cpu-instance-identity-oracle.md) adds a two-phase scene-reset contract with stale-epoch handle/packet rejection, 12 new CPU lifecycle tests and a per-instance full-frame image-identity oracle with 12 further tests (**24/24 new tests passed**). This addresses scene-reset ABA risk and the earlier single-green-pixel oracle's inability to detect missing instances. **No GPU availability or performance claims.** The next actionable research tasks remain CPU-only: simulate versioned staging/upload residency budgets and prototype geometry cluster correctness. GPU validation is a later gate.

## CPU staging and geometry residency milestones (2026-11-14)

[51](51-bounded-immutable-staging-upload-reference.md) adds safe versioned staging-upload packets, byte limits, per-slot busy/published gating, acknowledged completion and reset draining (**19 new CPU tests passed**). [52](52-geometry-page-residency-cpu-contract.md) implements a geometry-only parent/child page scheduler with pinned coarse fallbacks, multi-camera demand coalescing, hard resident/upload budgets and transactional eviction (**14 new CPU tests passed**). The CPU research directory reran **57 tests**, all passing, but the older full repository suite was not cloned in this environment. The page scheduler is *synthetic*; it does not load actual meshes or replace Godot's texture-streaming module. **Next tasks remain CPU-only:** model asynchronous page state/IO completion and per-page generation validity, then LOD error/transition correctness. Actual graphics testing stays deferred.

## High-level ranking

| Task | Dependency | Outcome | Status |
| --- | --- | --- | --- |
| R-001 Audit Godot source control and benchmark project | existing 4.8 beta checkout | known baseline, runnable harness | source audit done; graphics test pending |
| R-002 Measure normal nodes / one MultiMesh / regional MultiMesh | R-001 | strong baseline under visibility and motion | pending |
| R-003 Explore GPU instance visibility feasibility | RD API + R-002 | no-missing-geometry compute proof | [30 design](30-gpu-instance-visibility-design.md), [39 sparse-update audit](39-sparse-instance-update-cost-and-gpu-selection.md) and **[45 CPU reference + 14 passing tests](45-visibility-reference-milestone-and-gpu-gates.md)**; **[46 local RD compute fixture](46-isolated-gpu-visibility-feasibility-fixture.md)** plus **[47 guarded indirect + isolated offscreen draw fixture](47-guarded-indirect-and-offscreen-raster-probe.md)** committed. 13/13 new CPU command tests passed; 12 scenario GPU test source exists but has NOT been Godot-parsed or executed; native correctness and visual/performance validation pending |
| R-004 Explore static opaque mesh clusters | R-002 / MIT meshoptimizer | minimal isolated high-detail comparison | design in [31](31-independent-virtual-geometry-design.md), code pending |
| R-005 Validate existing texture streaming; then streaming budget *test harness* | module audit + resource state model | measure existing behavior, fallback/teleport stalls before adding a new manager | source trace completed in [38](38-texture-streaming-end-to-end-trace-and-validation.md), baseline in [36](36-texture-streaming-baseline-audit.md); GPU tests pending |
| R-005e Cold pipeline/PSO stutter fixture | baseline + material fixture | detect shader first-use hitch and variant regression under scene loading | source audit in [37](37-pipeline-stutter-and-pso-research.md); tests pending |
| R-006 Shadow invalidation experiment | shadow baseline + telemetry | quantified cache reuse / artifacts | design in [33](33-lighting-shadow-and-temporal-cache-design.md), code pending |
| R-007 Material and temporal integration | experimental win from R-003/R-004 | true shader/light/motion compatibility | designs in [34](34-materials-graph-and-temporal-reconstruction.md) and [40](40-representation-continuity-and-2026-rendering-research.md), code pending |
| R-008 Extend engine behind feature flag | measured win + legal review | safe optional Godot improvement | not approved yet |
| R-009 Optional Gaussian splats — source/format/backend study | public MIT/Apache projects and Godot integration APIs | hybrid rendering, LOD streaming, temporal/light correctness; no simulation coupling | [41 survey](41-gaussian-splatting-project-survey-2026.md), [42 architecture](42-independent-hybrid-splat-rendering-architecture.md), **[43 code audit](43-splat-source-audit-and-implementation-lessons.md)** done. Mesh2Splat→GDGS PBR data loss source-verified; GPU/format tests pending |

## Hardware-unavailable research mode (active 2026-11-13)

No local GPU runtime or reliable graphics benchmarking setup is currently available. **Continue meaningful source-level research**, but do not report hardware speedups or 'Godot test passes'. Add [41—42](41-gaussian-splatting-project-survey-2026.md) splat renderer/asset research to the independent representation portfolio, with GDGS code audit, public PlayCanvas streaming and careful SOG version/asset licensing review. **Do not** merge an untested splat plugin into the engine.  Prioritize: (1) source-verified camera culling, MultiMesh upload policy and immutable renderer interfaces; (2) deterministic CPU-only reference models for handle generations, bounds/culling conservative coverage, page residency and update-locality occupancy; (3) public independently licensed meshoptimizer clustered LOD and 2026 temporal/foliage literature; (4) precise original algorithm contracts and adverse-case tests. See [39](39-sparse-instance-update-cost-and-gpu-selection.md) and [40](40-representation-continuity-and-2026-rendering-research.md). The [committed model](../../benchmarks/theory/README.md) currently covers Godot MultiMesh update locality and dirty-region byte estimates; **six CPU-only unit tests passed locally**. CPU model results can test algorithmic logic **only**; they cannot predict actual GPU cost, render quality or hardware portability. Resume native work in this file once hardware is available.

## Native benchmark must be validated first

`benchmarks/rendering` has a Godot project with `nodes`, `one_multimesh`, and `regional_multimesh` modes plus deterministic `--move` (0–100%) and `--camera` (fixed/orbit/cut) controls, raw per-frame CSV exports, and a Python CSV validator. Four synthetic Python validator tests passed locally. **The GDScript benchmark has not been executed with Godot or shader/GPU hardware** and may contain API, syntax or profiling issues. Actual graphics validity remains pending.

Before treating any output as evidence:
1. Check the fork HEAD, `version.py`, debug/release build and render backend.
2. Launch the benchmark in a graphics-capable build, not `--headless`; perform a 1k object smoke test.
3. Inspect resulting CSV headers, row count, finite time values, draw/visible counts and reproducible camera.
4. Correct script/API errors and commit fixes separately from experimental optimizations.
5. Record GPU, CPU, OS, driver, display resolution, API, VSync, sample count and code revision.
6. Warm shader/asset compilation; measure initialization separately.
7. Repeat tests enough to establish variance and P50/P95/P99. Store raw frame samples as well as summaries.
8. Add dynamic transform updates (1/25/100%), camera cuts, actual visibility fractions, memory, GPU uploads and traceable fixtures.
9. Publish failures and incomplete instrumentation; *missing telemetry is not zero work*.
10. Decide bottleneck using CPU/GPU profiling, not anecdotal FPS.

## Comparable workloads

**S1 — dense visible field:** 1k, 10k, 100k; proportion visible 90%; shared simple mesh/material, with static and moving variants.

**S2 — mostly invisible city:** same population, 1%-10% visible because of walls/occluders; regular camera travel and 180-degree turns.

**S3 — mixed foliage:** partially transparent/alpha-masked leaf clusters, grass with wind and sparse opaque trunks; compare raster/overdraw and invalidations.

**S4 — high-detail continuous surface:** imported dense sculpture, rocks and terrain-like surface. Ordinary Godot meshoptimizer LOD vs experimental cluster path.

**S5 — streaming stress:** two large separated regions with total working set exceeding VRAM budget, camera teleport and ping-pong traversal.

**S6 — dynamic lighting:** one moving light, changing emissive material, large moving shadow caster, static ground; measure shadow/GI error and temporal stability.

**S7 — editor and ordinary project:** normal Godot scene/script, runtime mesh edits, resource hot reload and multiple viewports; new features disabled and enabled.

**S8 — low-count regression:** 1, 10, 100, 1,000 objects, several material variations. Any GPU pass can lose to direct rendering; a cheap bypass is necessary.

All fixtures should be authored independently or use permissively licensed assets with recorded provenance; no Epic demo meshes/assets copied into the public repo.

## Exact telemetry schema to adopt

A per-run manifest with:
- engine/experiment git SHA, fixture version and asset hash;
- OS, GPU, graphics driver, CPU, RAM, VRAM reported by driver/tool, render mode and API;
- camera path seed, instance count, visible fraction, material/mesh complexity, lighting and shadow configuration;
- warmup/sample interval, VSync, display scaling, graphics quality and any upscaling;
- frame CPU time, render-thread time, GPU time (where supported), P50/P95/P99;
- shadow/GI/cull/compaction GPU pass times;
- draw calls, dispatch calls, triangles processed vs visible (where measurable);
- GPU uploads bytes/frame, staging allocations, in-flight buffer size;
- GPU resident bytes/peak bytes, RAM/peak, IO and page misses;
- error images/sequence vs comparable reference, missing geometry count, overflow/fallback count;
- compile/import/startup/cache warmup times;
- confidence, known missing measurements, driver warnings and caveats.

Use `benchmarks/results/` with deterministic text manifests and scripts that consume raw samples. Avoid committing massive binaries unless explicitly needed; preserve small fixtures and reference images according to license.

## Comparison requirements

A claimed performance win must:
- use *equivalent pixel quality*, resolution, lighting, material variety and acceptable temporal error;
- compare against **the strongest reasonable Godot control** (including spatially tuned MultiMesh);
- include scenes favorable and unfavorable to the experiment;
- report CPU vs GPU bottleneck and memory/stalls;
- show repeated runs with same hardware/software configuration;
- remain valid for a clear range of instance counts/material types;
- disclose disabled effects and unsupported platforms;
- carry a reversible fallback and change risk assessment.

Our ambitious candidate targets (not requirements or empirical findings): materially lower P95/P99 frame time at equal quality, or 2x more *visible* world detail at comparable frame/memory budgets. An improvement isolated to triangle count or draw calls alone is not sufficient.

## Research and decision template

For every ticket record:
- **Question**: what observable bottleneck or missing capability?
- **Baseline**: what existing Godot/Open technique already addresses it?
- **Source**: public reference URL, license and commit/version where applicable.
- **Original design**: module interfaces and algorithms described without proprietary translations.
- **Fallback**: what happens when unsupported or slower?
- **Test**: reproducible fixture + metrics + invariants.
- **Result**: actual recordings, uncertainty and visualization.
- **Decision**: adopt, narrow, rework, discard or defer.
- **Maintenance**: cross-platform/editor compatibility, upstream merge burden and support owner.

## Recommended minimal engineering ticket for next continuation

**Ticket R-001b — benchmark graphics smoke and dynamic measurement validation.**

Target: `benchmarks/rendering/`.

Definition of done: benchmark runs on a graphics-capable Godot 4.8 build; all three modes produce valid summary **and raw sample** CSVs; movement and camera cases run without visual/culling losses; `validate_results.py` checks sample counts/timing percentiles; per-frame CPU/GPU times and P95/P99 are credible; missing counters are explicitly marked; README commands work on Windows and Fedora. Script and parser are committed, but **GPU/engine run is pending**.

If no graphics environment is available, inspect script against `RenderingDevice` and `Performance` APIs and write an explicit *unverified* code review; **do not claim benchmark correctness from static reading**.

## Suggested session workflow for any AI successor

1. Read [28](28-ai-research-handoff-and-implementation-map.md), [35](35-phase-1-validation-and-next-actions.md) and pertinent module spec. Check repo HEAD and current source.
2. Choose one *small* ticket and state one-sentence outcome, constraints and test gate. Do not start a global renderer rewrite.
3. Verify public method docs/licenses and Godot APIs against pinned target. Restricted Unreal source is for comparison only; no code translation.
4. Implement independently with concise file/function header comments, deterministic tests, explicit opt-in and fallback.
5. Run available test tooling. If GPU test unavailable, mark **not tested**, don't substitute synthetic benchmark numbers.
6. Review for correctness/races, shader compilation, material behavior, GPU lifetime and platform divergence.
7. Update affected docs, source provenance, test results and this handoff *in the same commit as the substantive change*, whenever possible.
8. Keep a clear `what changed / what was verified / what remains untested / next action` note.
9. Do not conflate code committed, tests defined, tests passing, and measured performance.
10. Revisit planning assumptions when Godot/UE version changes or new rendering literature appears.

## Documentation hygiene

- Index documents from [README](README.md); use short descriptive titles and stable numbering.
- Keep *facts, hypotheses, decisions and measurements* visibly different.
- Prefer direct primary references, exact tested version and concise rationale.
- When contradicting older docs, update them or add explicit superseding note.
- Avoid duplicating entire source files, private implementations and speculative performance claims.
- Future AI should not have to search conversation logs to know why a module exists or what its acceptance criteria are.

## Hardware note

A source-only audit is possible using GitHub connection, but actual graphics data must come from a capable machine. Users may test on Windows 11 laptop or Fedora desktop; confirm graphics hardware/backend before setting performance baselines. Do not compare data between those machines as if differences measured the renderer design.

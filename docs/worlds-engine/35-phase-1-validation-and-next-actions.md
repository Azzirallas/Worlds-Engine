# 35 — Phase 1 executable research queue, test gates and AI continuation procedure

**Status:** execution specification, **not a claim that tests or render prototypes have run**. Written 2026-11-13. Read [AI handoff](28-ai-research-handoff-and-implementation-map.md) first.

## High-level ranking

| Task | Dependency | Outcome | Status |
| --- | --- | --- | --- |
| R-001 Audit Godot source control and benchmark project | existing 4.8 beta checkout | known baseline, runnable harness | source audit done; graphics test pending |
| R-002 Measure normal nodes / one MultiMesh / regional MultiMesh | R-001 | strong baseline under visibility and motion | pending |
| R-003 Explore GPU instance visibility feasibility | RD API + R-002 | no-missing-geometry compute proof | design in [30](30-gpu-instance-visibility-design.md), code pending |
| R-004 Explore static opaque mesh clusters | R-002 / MIT meshoptimizer | minimal isolated high-detail comparison | design in [31](31-independent-virtual-geometry-design.md), code pending |
| R-005 Validate existing texture streaming; then streaming budget *test harness* | module audit + resource state model | measure existing behavior, fallback/teleport stalls before adding a new manager | source trace completed in [38](38-texture-streaming-end-to-end-trace-and-validation.md), baseline in [36](36-texture-streaming-baseline-audit.md); GPU tests pending |
| R-005e Cold pipeline/PSO stutter fixture | baseline + material fixture | detect shader first-use hitch and variant regression under scene loading | source audit in [37](37-pipeline-stutter-and-pso-research.md); tests pending |
| R-006 Shadow invalidation experiment | shadow baseline + telemetry | quantified cache reuse / artifacts | design in [33](33-lighting-shadow-and-temporal-cache-design.md), code pending |
| R-007 Material and temporal integration | experimental win from R-003/R-004 | true shader/light/motion compatibility | design in [34](34-materials-graph-and-temporal-reconstruction.md), code pending |
| R-008 Extend engine behind feature flag | measured win + legal review | safe optional Godot improvement | not approved yet |

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

**Ticket R-001b — benchmark smoke and dynamic update controls.**

Target: `benchmarks/rendering/`.

Definition of done: benchmark runs on a graphics-capable Godot 4.8 build; all three existing modes produce interpretable CSVs; dynamic movement is deterministic; camera can run static/orbit/cut paths; measurement scripts report per-frame CPU/GPU values and P95/P99; missing counters are explicitly marked; README records exact commands for Windows and Fedora.

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

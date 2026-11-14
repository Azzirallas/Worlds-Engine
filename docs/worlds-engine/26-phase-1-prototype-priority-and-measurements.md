# 26 — Phase 1 rendering experiments: prioritized implementation specifications

**Status:** research complete enough to prioritize, but no new code prototype or graphics benchmark executed. Date: 2026-11-13. See [architecture audit](24-unreal-5-8-rendering-architecture-audit.md), [gap matrix](25-godot-renderer-gap-matrix.md) and [legal protocol](27-license-and-independent-implementation-protocol.md). Keep the existing [baseline project](../../benchmarks/rendering/) as a control; it is **not yet validated on hardware**.

## Portfolio decision

Instead of spending months cloning an existing proprietary feature, start with **two independent, interoperable original paths**:

- **P0-E02: incremental GPU scene/instance update and visibility** — general dense living-world scalability with conventional meshes.
- **P0-E01a: tiny cluster geometry lab** — frontier test for very fine static geometry using GPU visibility and indirect rendering.

Run a cheap corrected baseline and build both designs in parallel. Actual code begins only with a bounded implementation ticket, no default renderer changes. The first *measured* winner earns an integration candidate.

## Ticket P0-00 — establish honest native baseline

**Starting scaffold:** `benchmarks/rendering/{project.godot,benchmark.gd,main.tscn}`, untested.

**Deliverables:** smoke-test GDScript on Godot 4.8 beta; record video driver, GPU, CPU, shader mode, profiler settings; fix errors; add dynamic instance updates, fixed camera paths, visibility fractions, raw frame samples and memory output.

**Scene matrix:**
- 1k, 10k, 100k entities; 1%, 10%, 50%, 90% visibly on-screen.
- Nodes vs one giant MultiMesh vs bounded MultiMesh regions (e.g., 16/32/64 scene units; actual unit scale fixed in report).
- Static vs 1% / 25% / 100% transforms changing; contiguous vs randomly distributed changes.
- Computed vs conservative/custom bounds; camera orbit, straight travel and teleport.
- Low-poly, medium and dense meshes; simple and varied materials; shadow on/off.
- Frame-time P50/P95/P99 and cold/warm resource behavior.

**Critical controls:** cap display/VSync, avoid editor overhead when measuring runtime, avoid shader warmup confounds, record native resolution and quality. Do not use `--headless` to claim GPU results.

**Outputs:** `benchmarks/results/<machine>/<revision>/` CSV/JSON summaries, config manifest, notes on unsupported features. Nothing is a result until a real GPU run.

## Ticket P0-01 — persistent GPU instance table and fine visibility

**Hypothesis:** preserving GPU-side instance records across frames, updating only changed portions, selecting visible instances with compute and submitting indirectly will reduce render CPU and update cost for dense scenes, especially when only a small fraction is visible.

**Prototype boundary:** single mesh/material family, static bounding volumes, one camera, opt-in isolated experiment. Use public Godot RenderingDevice APIs and generic GPU computing techniques.

**Architecture draft (independently designed):**
1. Stable *render handles* (not simulation IDs) map to a compact GPU-side instance record; generations prevent stale reuse.
2. Dirty ranges or batch updates modify records; compact and measure fragmented updates.
3. CPU generates coarse region candidates from an independent spatial grouping; GPU optionally refines frustum/visibility.
4. GPU creates visible instance IDs and an indirect command buffer; use only supported hardware/API primitives.
5. Render passes consume compacted IDs. A normal Godot MultiMesh implementation remains the fallback/control.
6. Scene edits and camera teleports invalidate any temporal visibility assumptions conservatively.

**Metrics:** CPU cull/update/submit time, GPU cull and draw time, upload bytes/frame, occupancy, memory overhead, P95/P99 and visual misses. Track cost at 90% *visible* too, where GPU culling may not help.

**Reject or narrow if:** synchronization/readback dominates, CPU baseline already negligible, extra buffers increase VRAM disproportionately, or correctness deteriorates on rapid motion. Keep a small-scene threshold to bypass compute.

## Ticket P0-02 — original minimal virtualized/cluster geometry experiment

**Hypothesis:** a GPU cluster visibility pass with independent coarse LOD can outperform high-detail classic meshes in dense surface scenes at equivalent pixel detail.

**Proof boundaries:**
- Offline asset partition into small bounded clusters; don't mandate any particular Epic data format, clustering rule, page size, codec, queue shape or shader arrangement.
- Begin with *fixed resolution* clusters and a single opaque material. The first experiment tests GPU cull/indirect overhead, not full virtualized geometry.
- Then add independent cluster hierarchy + controlled geometric error; validate cracks/normals.
- Later test residency/prefetch; shadows/transparency/skinning deferred.
- Preserve ordinary mesh/material asset path and compare to a good mesh LOD + regional MultiMesh control.

**Control cases:** terrain-like continuous surface, large architecture, sparse medium-poly meshes, disjoint leaves/foliage. Include many fully visible objects to expose culling overhead.

**Gate:** total frame time, P95, GPU cull, preprocessed storage, VRAM, shader compile, correctness and real pixel-level error at equal render resolution. **Do not use source triangle count alone as a win metric.**

**Competitive goal:** seek demonstrable, reproducible improvement over the best conventional path in at least one meaningful, non-cherry-picked game workload. A negative result is useful and should be documented.

## Ticket P1-03 — bounded residency and fast-camera streaming

**Hypothesis:** an explicit bytes-per-frame budget, prioritized requests and fallback representations can flatten frame-time spikes and avoid missing geometry on fast travel.

**Proof:** generate a streamable sample resource from wholly original test data; cap GPU upload/IO budgets; add low-detail always-resident fallback; test steady camera, hard turns, teleports, constrained VRAM and back-and-forth thrashing. Report peak stalls, time-to-converge, cache hit and visible error. Do not start by copying Unreal data layouts or paging algorithms.

## Ticket P1-04 — changed-region shadow/GI refresh

**Hypothesis:** explicit versioned scene-change notifications can reduce repeated update work for static or slowly changing large-world content while preserving temporal correctness.

**Proof:** first choose one *existing Godot path* (shadow cache or SDFGI update) and construct a side-by-side invalidation experiment. Track change rectangle/volume, light visibility, camera motion and effect-specific dependencies. Recompute when needed; stale data must not be misrepresented as valid.

**Adversarial scenes:** moving large occluder, light rotation, emissive changes, teleport, foliage motion, fast-moving player, newly revealed regions. Report cache hits *and* artifacts/ghosting and P99 update spikes.

**Novel research avenue:** a general 'render relevance + change epoch' service could serve several effects, but only after a single effect has demonstrated correct savings. The world simulation may supply change information through optional metadata; the engine must also work with ordinary Godot nodes.

## Ticket P2-05 — dense foliage representation crossover

Compare ordinary MultiMesh, spatially chunked MultiMesh with LOD, procedural instancing/cards/impostors and future cluster geometry. Most prior Nanite-style claims center on continuous surfaces; aggregate partially covering foliage is a known pathological case in public docs. Measure foliage motion, overdraw, albedo/normal transitions, shadow quality, temporal shimmer, VRAM, CPU update cost. The winner may vary by distance and GPU.

## Ticket P2-06 — many lights and cached GI

Two separate lanes, neither first milestone:
- Direct lighting: clustered Forward+ control vs bounded light sampling with temporal reuse and denoising (hardware feature gated). Quality can degrade as overlapping light complexity rises.
- Indirect lighting: existing Godot SDFGI/VoxelGI/SSIL controls vs versioned probes/cache and adaptive update budgets. Must render moving geometry realistically.

Never describe these as 'implement Lumen/MegaLights' tasks; define independent quality/latency objectives.

## Ticket P3-07 — RT deformation and other frontier methods

Experimental only when target GPU supports tested RT features. Compare shared/low-cost deformation proxies and acceleration updates from independent papers against ordinary CPU/GPU animation. Report ray cost, BVH memory/update cost and mismatches. Cross-vendor or conventional fallback mandatory.

## Experiment harness: mandatory evidence record

For each trial record:

`engine_sha, prototype_sha, test_scene_sha, scenario_seed, OS, CPU, GPU, driver, backend, renderer_mode, shader_quality, resolution, VSync, warmup_frames, measured_frames, samples, median_frame_ms, p95_frame_ms, p99_frame_ms, cpu_render_ms, gpu_render_ms, RAM_peak, VRAM_peak, uploads_bytes, draw_calls, dispatch_calls, note_on_image_error`.

Some metrics require platform profiling tools and cannot come from standard GDScript alone; represent missing data as **unmeasured**, never fabricate a zero.

## Stop/go decision procedure

1. Confirm benchmark correctness and visual equivalence.
2. Establish uncertainty with repeated runs and stable conditions.
3. Compare against a *well-tuned baseline*, not a deliberately poor implementation.
4. Choose improved P95/P99 + acceptable memory/quality as the primary success condition.
5. Quantify regressions under unfriendly content; decide whether routing/fallback can avoid them.
6. Publish negative outcomes, driver exclusions, maintenance cost and portability.
7. Only then write a feature-flagged engine patch; separately review ordinary Godot compatibility.

**Provisional ambition:** seek a material advantage (e.g., >=15% lower total frame time or >=2x visible scene density under matched frame-time/quality/memory constraints); these are *research thresholds*, not measured claims or universal acceptance criteria.

## Exact next tasks

1. Smoke-test and correct current benchmark project on a graphics-capable Godot 4.8 build.
2. Add dynamic updates and visible-fraction controls.
3. Characterize Godot graph vs scene culling CPU costs separately.
4. Prepare architecture sketch and minimal API feasibility check for P0-01; ensure no avoidable GPU readback.
5. Prototype P0-02 only as an opt-in experimental scene, entirely independent implementation and public-source design.
6. Reevaluate rankings after data—do not confuse the priority of **research** with permission for a feature merge.

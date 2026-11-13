# 11 — Performance, benchmarking and evidence

## Policy

Never call a feature 'faster' without a recorded reproducible comparison. A benchmark must pin the fork SHA, upstream SHA, OS, GPU/CPU, driver/API, settings, resolution, assets, camera path, test duration, warm-up and build type.

## Primary measurements

- CPU: main-thread render work, simulation/physics work, scene traversal, frame pacing, worker utilization and waits.
- GPU: frame time, dispatch/draw counts, raster/fragment cost, geometry/visibility workload, memory bandwidth and uploads.
- Streaming: disk read/asset decode/upload, queue latency, residency thrash and memory peaks.
- Physics: tick time, broadphase/narrowphase/solver, body counts, sleep/wake churn and query latency.
- User experience: editor launch, scene load, import, tool responsiveness and export compatibility.
- Stability: exceptions, device loss, invalid updates, long-run leaks and resource lifetime.

Use P50, P95, P99 frametimes in milliseconds, not FPS alone; report startup/shader compilation and stutter separately. For qualitative visuals collect matched captures/video and artifact assessments.

## Baseline environment

Initial project development may occur on a Windows 11 laptop and a Fedora Linux desktop. Record their actual CPU/GPU specs rather than comparing numbers between machines as if they were interchangeable. Never compare upstream on one machine with the fork on another and attribute the difference to engine code.

## Scenario suite

| ID | Workload | What it isolates |
| --- | --- | --- |
| BENCH-01 | Empty scene/editor | fixed engine cost |
| BENCH-02 | Many unique MeshInstance3D nodes | scene traversal and submissions |
| BENCH-03 | MultiMesh instances divided spatially | batch cost and culling granularity |
| BENCH-04 | Dense forest and vegetation | overdraw, shading and shadow cost |
| BENCH-05 | City blocks and interiors | occlusion/culling efficiency |
| BENCH-06 | Moving animated crowd | skinning and transform update |
| BENCH-07 | Terrain fly-through | LOD, streaming and GPU residency |
| BENCH-08 | Dynamic lighting stress | GI, shadow and temporal stability |
| BENCH-09 | Rigid-body contact and debris | physics broadphase/solver |
| BENCH-10 | External ECS delta flood | bridge cost and representation changes |
| BENCH-11 | Project import and export | ordinary developer workflow regression |

Each test needs fixed scene seed, assets, camera path, capture method, repeated runs and clear pass/fail rules. Use upstream-equivalent graphics quality settings, and report relative visual quality changes separately.

## Metrics log template

- Experiment ID; date; responsible contributor
- Hypothesis and alternative no-change option
- Upstream commit and fork commit
- Hardware, OS, GPU driver/API, resolution and engine settings
- Scene and asset hashes; number of objects; animation/physics counts
- P50/P95/P99 CPU and GPU frame times; peak RAM/VRAM; uploads
- Correctness and visual comparison; editor/export regressions
- Variance/repetitions; data links and profiler capture
- Decision: adopt / revise / reject / needs research

## Experiment discipline

Run several trials after warm-up, vary scene density and stress extremes, and include worst-case burst behavior. Inspect GPU-limited versus CPU-limited cases separately. An optimization that improves average FPS but causes extreme P99 stalls may be a regression.

## Performance budgets

Targets are provisional until we select real hardware, resolution and content. Do not invent concrete FPS/VRAM numbers. First publish an upstream baseline; then agree on practical targets for each workload. The hard constraint is quality/scalability at predictable frame budgets, not a single marketing figure.
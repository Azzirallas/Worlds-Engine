# Rendering baseline benchmark — Phase 1

This is a minimal independent **Godot project** inside the Worlds Engine fork. It uses ordinary GDScript, `MeshInstance3D`, `MultiMeshInstance3D`, and built-in renderer counters to compare rendering representations **without modifying the engine**.

**Status (2026-11-13):** benchmark script now includes deterministic movement, view cuts and raw sample exports. **Not run or GDScript-parser validated in a Godot binary.** The Python results validator and its four synthetic tests have been exercised locally. Complete the graphics smoke run before accepting any GPU results. Stage 1's canonical plan is [Phase 1 execution plan](../../docs/worlds-engine/19-phase-1-rendering-execution-plan.md).

## Important renderer selection

The project deliberately does **not** pin a renderer in `project.godot`. On supported desktop hardware Godot generally defaults to Forward+, but **verify the active renderer in the editor** before gathering results. Select Forward+ explicitly for first-phase RenderingDevice tests; record when Mobile or Compatibility is used. Never compare runs with different active backends.

> The project is not intended for `--headless` graphics testing. A headless/dummy backend does not provide meaningful GPU results.

## Example run commands

With a built Godot executable on Windows or Linux, from repository root:

```sh
godot --path benchmarks/rendering -- --mode=nodes --count=1000 --frames=360 --warmup=120
godot --path benchmarks/rendering -- --mode=one_multimesh --count=10000 --frames=360 --warmup=120
godot --path benchmarks/rendering -- --mode=regional_multimesh --count=10000 --region=16 --frames=360 --warmup=120
godot --path benchmarks/rendering -- --mode=regional_multimesh --count=10000 --region=32 --bounds=custom --frames=360 --warmup=120
godot --path benchmarks/rendering -- --mode=regional_multimesh --count=10000 --move=25 --camera=cut --frames=360 --warmup=120
godot --path benchmarks/rendering -- --mode=nodes --count=0 --camera=fixed --frames=360 --warmup=120
```

If the executable has a different name or path, replace `godot`. Command-line flags after `--` belong to the benchmark.

## Arguments

| Option | Default | Purpose |
| --- | --- | --- |
| `--mode=nodes\|one_multimesh\|regional_multimesh` | regional_multimesh | Representation |
| `--count=10000` | 10000 | Object count (0 is permitted for an empty-scene control) |
| `--region=16` | 16 | World-space region edge length for region MultiMeshes |
| `--span=200` | 200 | Shared world footprint |
| `--bounds=computed\|custom` | computed | Use auto-generated or fixed conservative group bounds |
| `--warmup=120` | 120 | Frames skipped before sampling |
| `--frames=360` | 360 | Frames sampled |
| `--vsync=off` | opt-in | Disable VSync where supported |
| `--camera=orbit\|fixed\|cut` | orbit | Orbit, constant position, or alternating viewpoints (every 120 frames) |
| `--move=0\|1\|25\|100` | 0 | Percent of deterministic instances whose transforms change each frame (any 0–100 value accepted) |

## What it records

Built-in per-viewport CPU/GPU render-time counters, Performance draw-call count and rendered-object count, frame interval delta P50/P95/P99, object/group counts, moving-object count and scene build duration. Two CSVs are written to `user://`: a one-row summary (`WORLDS_BENCHMARK_COMPLETE`) and one row per sampled frame (`WORLDS_BENCHMARK_SAMPLES`). Nonpositive GPU timing is marked **-1 (unavailable)**, excluded from GPU percentiles and counted under `valid_gpu_samples`. It is never presented as zero-cost work.

**Cautions:** frame delta includes system scheduling / VSync effects; viewport GPU timing may be zero or unsupported on a particular backend, and built-in counters do not explain CPU-side culling, upload bytes or GPU stage occupancy. Dynamic updates run in GDScript, so the results are **whole-scene workloads**, not isolated renderer-only microbenchmarks. Use native profiling and GPU capture tools for attribution. Source-only evidence is not a benchmark.

## Validate and retain raw results

Run the standalone Python validator from repository root after each Godot run (paste the summary filename printed by the benchmark; the validator finds the matching `_samples.csv`):

```sh
python benchmarks/rendering/validate_results.py "/absolute/path/to/render_baseline_...csv"
python -m unittest discover -s benchmarks/rendering -p "test_validate_results.py" -v
```

The validator checks CSV integrity, frame counts, P50/P95/P99 summary consistency and missing GPU samples. It **does not** establish graphics correctness or hardware comparability; keep the original raw CSV and an environment manifest. The Python unit tests use synthetic data and do not require a Godot build.

## Run order and validity

1. Smoke-run `--count=100` in **each** mode; fix script/runtime errors before publishing comparisons.
2. Record Godot version/commit, build type, renderer/backend, GPU, driver, CPU, OS, resolution, VSync, display refresh, and whether editor or export binary was used.
3. Run a static empty baseline separately. Keep a consistent camera orbit, material, world span and light/shadow settings.
4. Compare 1k/10k/100k where hardware allows (avoid huge Node cases that exhaust RAM).
5. Compare region edge sizes and bounds settings at equal object count.
6. Repeat 3–5 times after shader warmup. Do not compare different machines.
7. Report GPU and CPU time as separate metrics, including stutters and variance.
8. Run `--move=0`, `--move=1`, `--move=25`, and `--move=100` with `--camera=fixed`, `--camera=orbit`, and `--camera=cut`. Use all three representation modes; verify no culling loss and conservative bounds.
9. Inspect GPU upload bytes, AABB update cost and bottlenecks with native CPU/GPU profiling; the present GDScript workload exposes movement but does not directly instrument bytes transferred.
10. Validate CSVs and archive per-frame files before comparing runs; the checker cannot prove equivalent rendered quality.

## Known limitations

- Deterministic grid placement is a synthetic workload; real forests, crowds, occlusion and animations require follow-on scenes.
- Object density increases at fixed span as count rises; compare modes at equal count, not absolute scaling between count tiers without that caveat.
- Orbit, fixed and camera-cut controls are available; actual *wall occlusion* and controlled visible-fraction scene fixtures remain future work.
- A single material is intentionally easy for automatic instancing; a mixed-material workload is needed.
- Renderer backend defaults and script syntax must be smoke-tested on the fork before trusting results.
- No performance claims are made by this README.

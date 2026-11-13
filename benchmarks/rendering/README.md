# Rendering baseline benchmark — Phase 1

This is a minimal independent **Godot project** inside the Worlds Engine fork. It uses ordinary GDScript, `MeshInstance3D`, `MultiMeshInstance3D`, and built-in renderer counters to compare rendering representations **without modifying the engine**.

**Status: committed but not executed or syntax-validated against a Godot binary.** It is a starting point and must pass a smoke run before its data is accepted. Stage 1's canonical plan is [Phase 1 execution plan](../../docs/worlds-engine/19-phase-1-rendering-execution-plan.md).

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
```

If the executable has a different name or path, replace `godot`. Command-line flags after `--` belong to the benchmark.

## Arguments

| Option | Default | Purpose |
| --- | --- | --- |
| `--mode=nodes\|one_multimesh\|regional_multimesh` | regional_multimesh | Representation |
| `--count=10000` | 10000 | Object count |
| `--region=16` | 16 | World-space region edge length for region MultiMeshes |
| `--span=200` | 200 | Shared world footprint |
| `--bounds=computed\|custom` | computed | Use auto-generated or fixed conservative group bounds |
| `--warmup=120` | 120 | Frames skipped before sampling |
| `--frames=360` | 360 | Frames sampled |
| `--vsync=off` | opt-in | Disable VSync where supported |

## What it records

Built-in per-viewport CPU/GPU render-time counters, Performance draw-call count and rendered-object count, frame interval delta P50/P95/P99, object/group counts and scene build duration. CSV summaries are written to `user://` and the absolute file path is printed as `WORLDS_BENCHMARK_COMPLETE ...`.

**Cautions:** frame delta includes system scheduling / VSync effects; viewport GPU timing may be zero or unsupported on a particular backend, and built-in counters do not explain CPU-side culling, upload bytes or GPU stage occupancy. Use native profiling and GPU capture tools for attribution. Source-only evidence is not a benchmark.

## Run order and validity

1. Smoke-run `--count=100` in **each** mode; fix script/runtime errors before publishing comparisons.
2. Record Godot version/commit, build type, renderer/backend, GPU, driver, CPU, OS, resolution, VSync, display refresh, and whether editor or export binary was used.
3. Run a static empty baseline separately. Keep a consistent camera orbit, material, world span and light/shadow settings.
4. Compare 1k/10k/100k where hardware allows (avoid huge Node cases that exhaust RAM).
5. Compare region edge sizes and bounds settings at equal object count.
6. Repeat 3–5 times after shader warmup. Do not compare different machines.
7. Report GPU and CPU time as separate metrics, including stutters and variance.
8. Follow with more precise **dynamic instance update / AABB / upload** benchmarks. The current project does **not** yet implement moving-instance percentage cases; they remain specified in RES-002.

## Known limitations

- Deterministic grid placement is a synthetic workload; real forests, crowds, occlusion and animations require follow-on scenes.
- Object density increases at fixed span as count rises; compare modes at equal count, not absolute scaling between count tiers without that caveat.
- The orbit changes camera view; test-specific isolated frustum and occlusion scenes remain future work.
- A single material is intentionally easy for automatic instancing; a mixed-material workload is needed.
- Renderer backend defaults and script syntax must be smoke-tested on the fork before trusting results.
- No performance claims are made by this README.

# GPU visibility — isolated RenderingDevice feasibility fixture

**Status (2026-11-14): source committed; NOT compiled, parsed by Godot, or GPU-executed.** The Python CPU reference was actually run in the research environment: **14/14 tests passed** on 2026-11-14. This project is an independent **proof-of-feasibility fixture**, not a replacement for Godot's rendering pipeline.

## What this implements

- `visibility.comp.glsl`: a 64-thread compute kernel receiving world-space sphere records, per-slot layer/generation metadata, candidate slot IDs, inward-facing frustum planes and a bounded compacted output.
- `runner.gd`: reproducible test scenes, CPU region AABB preselection and a full-instance CPU truth scan; creates a **local RenderingDevice**, uploads `std430` buffers, dispatches the kernel, **synchronously reads back only for validation** and compares exact visible slot/generation sets. Atomic output ordering is not assumed.
- **Fail-safe behavior:** output overflow sets bit 0 in an explicit diagnostic buffer; malformed candidate IDs set bit 1. The fixture **rejects truncated output as a successful draw list**. It does *not* implement real fallback draw submission or GPU frame integration yet.
- Scenarios: empty, boundary and disabled instances, 4,097 spatially distributed entries with region selection vs all-candidate mode, second view/layer, arbitrary non-unit plane, 257-overlap case with a deliberately tiny output capacity, a fully sized control and a bad-ID diagnostics case.

## Important configuration

`project.godot` sets **Compatibility** for the empty main viewport deliberately, because a *local* Vulkan RenderingDevice can be created separately from the viewport's renderer on supported hardware. **However, this behavior is not guaranteed across Godot backends/platforms.** If `create_local_rendering_device()` returns null, the fixture fails with `WORLDS_GPU_VISIBILITY_UNAVAILABLE` and exit code 2; this does not constitute a GPU PASS. To test with the production Forward+ backend, change the project renderer to Forward+ explicitly **as a separate recorded experiment**. The fixture never uses a headless/dummy device for performance claims.

## How to run on supported graphics hardware

With a built Godot 4.8-compatible executable:

```sh
godot --path benchmarks/gpu_visibility --editor --quit
godot --path benchmarks/gpu_visibility
```

First command imports/compiles `visibility.comp.glsl` in the editor; the second runs the fixture. On a supported device with a successful import, inspect stdout for `WORLDS_GPU_CASE_PASS` and the final `WORLDS_GPU_VISIBILITY_PASS`. A `FAIL` or `UNAVAILABLE` result is **not** a passing experiment. Graphics drivers/shader compilers, hardware, and this project have not been exercised together in this research environment; fix any Godot syntax/API issues before interpreting results.

## What this does NOT establish

- No actual GPU instance **drawing** or indirect draw command generation; only compute selection and CPU verification.
- No engine/RenderingServer integration, no camera projection extraction from the engine, no shadow/GI, occlusion/HZB, motion vectors, skinned bounds, editor picking or multiview compute scheduling.
- No GPU timing/throughput/VRAM or FPS claims. `rd.sync()` and `buffer_get_data()` deliberately stall for deterministic validation and **must not** appear in a production frame path.
- No use of proprietary Unreal reference code; the shader and GDScript are original, built against public Godot RenderingDevice APIs.
- No production renderer changes. Standard meshes remain the default and fallback.

## Next gates

1. Compile/import the shader using the exact Godot fork build; fix any shader, descriptor or GDScript error.
2. Compare all nine scenarios with CPU truth and confirm overflow is *reported*, not silently used.
3. Add graphics capture, GPU producer→indirect-consumer barrier tests, and a **separate opt-in draw fixture** using real meshes; preserve normal `MultiMeshInstance3D` controls.
4. Benchmark total scene frame costs and synchronization; avoid CPU readback in actual rendering.
5. Only consider adding an opt-in native path after measurable wins and correct shading and compatibility.

Reference: [GPU visibility source spec](../../docs/worlds-engine/30-gpu-instance-visibility-design.md), [CPU reference milestone](../../docs/worlds-engine/45-visibility-reference-milestone-and-gpu-gates.md).

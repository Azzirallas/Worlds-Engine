# GPU visibility — isolated RenderingDevice feasibility fixture

**Status (2026-11-14): guarded indirect command and optional offscreen raster probe source committed; still NOT compiled, parsed by Godot, or GPU-executed.** The Python CPU reference was actually run in the research environment: **14/14 tests passed** on 2026-11-14. This project is an independent **proof-of-feasibility fixture**, not a replacement for Godot's rendering pipeline.

## What this implements

- `visibility.comp.glsl`: a 64-thread compute kernel receiving world-space sphere records, per-slot layer/generation metadata, generation-tagged candidate handles (`uvec2 slot,generation`), inward-facing frustum planes and a bounded compacted output. The push-constant ABI is **32 bytes** (5 inputs plus 3 reserved words) to avoid tighter-alignment compatibility issues.
- `runner.gd`: reproducible test scenes, CPU region AABB preselection and a full-instance CPU truth scan; creates a **local RenderingDevice**, uploads `std430` buffers, dispatches visibility → a barrier → `indirect_guard.comp.glsl`, then **synchronously reads back only for validation** and compares visible slot/generation sets and the 16-byte GPU-generated draw packet. Atomic output ordering is not assumed.
- **Fail-safe behavior:** output overflow sets bit 0 in an explicit diagnostic buffer; malformed candidate IDs set bit 1; candidate handles referencing recycled generations set bit 2. The guard writes a **zero-instance draw** on any error, exceeded capacity or zero-vertex mesh. It does *not* implement automatic conventional fallback draw submission or production GPU frame integration.
- Scenarios (**12 total**): empty, boundary and disabled instances, 4,097 spatially distributed entries with region selection vs all-candidate mode, second view/layer, arbitrary non-unit plane, 257-overlap case with a deliberately tiny output capacity, a fully sized control, independent draw-limit suppression, zero-vertex guard, bad-ID diagnostics and stale-generation diagnostics. The **separate** `offscreen_draw.tscn` scene uses `indirect_probe.glsl` to consume the GPU-written indirect draw command in a small local framebuffer and validate the center pixel (green for valid draws, black for suppressed draws).

## Important configuration

`project.godot` **does not force Compatibility/OpenGL**. Use a graphics-capable Godot build with **Forward+ (RenderingDevice)** enabled for this test. The experiment uses a local RD for compute; if `create_local_rendering_device()` returns null, the fixture fails with `WORLDS_GPU_VISIBILITY_UNAVAILABLE` (exit code 2), **not** a GPU PASS. Do not run with a dummy/headless backend for performance claims.

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
2. Compare all ten scenarios with CPU truth and confirm overflow, stale-generation work and invalid IDs are *reported*, not silently used.
3. Add a **separate opt-in draw fixture** using real meshes and GPU producer→indirect-consumer barrier tests; preserve normal `MultiMeshInstance3D` controls. Godot's local RenderingDevices generally cannot be captured by RenderDoc, so migrate instrumentation/capture to a suitable main-device path *only once* the isolated compute parity experiment passes.
4. Benchmark total scene frame costs and synchronization on the target GPU(s); avoid CPU readback in actual rendering. Record actual shader compilation errors and GDScript/parser failures separately from mismatched GPU results.
5. Only consider adding an opt-in native path after measurable wins and correct shading and compatibility.

Reference: [GPU visibility source spec](../../docs/worlds-engine/30-gpu-instance-visibility-design.md), [CPU reference milestone](../../docs/worlds-engine/45-visibility-reference-milestone-and-gpu-gates.md).

# 47 — Guarded indirect draw and opt-in offscreen raster probe

**Status (2026-11-14): CPU reference code executed locally, 13/13 tests passed; GPU and Godot GDScript/GLSL unexecuted.** This is an isolated **RenderingDevice experiment**, not a renderer change, performance benchmark, fully integrated mesh renderer, or proven fallback. Normal Godot mesh rendering stays the default.

Read [30 — GPU visibility design](30-gpu-instance-visibility-design.md), [45 — generation-safe CPU visibility model](45-visibility-reference-milestone-and-gpu-gates.md), [46 — first compute visibility fixture](46-isolated-gpu-visibility-feasibility-fixture.md), and [DEC-012](15-decisions-and-open-questions.md). This extends [46] without replacing its tests.

**Hardware-free follow-on (2026-11-14):** [48](48-inflight-presentation-lifetimes-and-hardware-free-validation.md) adds a CPU-validated in-flight presentation-slot lifecycle and retirement model. It addresses slot reuse hazards that a shader-side generation test cannot resolve on its own. The GPU shader/draw fixtures in this document remain intentionally unexecuted until hardware is available.

## What was added

### A — Host-side, testable indirect draw ABI

- [`benchmarks/theory/indirect_draw_reference.py`](../../benchmarks/theory/indirect_draw_reference.py): `VisibilityCounters`, four-word `DrawCommand`, `DrawDecision`, `finalize_draw`, and exactly specified 16-byte little-endian output.
- [`benchmarks/theory/test_indirect_draw_reference.py`](../../benchmarks/theory/test_indirect_draw_reference.py): **13 passing standard-library unittest cases**, including 2,500 seeded random decisions and serialization roundtrips.
- Tests were run in the Python 3.13.5 research container on 2026-11-14. The existing 14-test visibility suite was **not rerun locally as part of this commit series**, although its prior result remains documented.

The **non-indexed indirect command ABI** is exactly four little-endian 32-bit unsigned integers:

| Offset | Field | Role |
| --- | --- | --- |
| 0 | `vertex_count` | number of vertices in mesh/procedural primitive |
| 4 | `instance_count` | number of valid GPU-selected instances, or **zero when unsafe** |
| 8 | `first_vertex` | zero in current experiment |
| 12 | `first_instance` | zero in current experiment |

This is the layout accepted by Godot `draw_list_draw_indirect(..., use_indices=false)` and the underlying Vulkan non-indexed indirect call. An indexed command needs a **different 20-byte format**, which this experiment does not create. `draw_count=1`; the command does not exercise multiple draws, mesh groups or independent LOD commands.

### B — GPU compute guard

- [`benchmarks/gpu_visibility/indirect_guard.comp.glsl`](../../benchmarks/gpu_visibility/indirect_guard.comp.glsl): one GPU workgroup writes the indirect command. It reads the visibility pass's atomic count and flags and **sets `instance_count=0`** if **any** flag is nonzero, visible count exceeds output capacity, visible count exceeds the separate draw limit, or mesh vertex count is zero.
- The original [`visibility.comp.glsl`](../../benchmarks/gpu_visibility/visibility.comp.glsl) produces the candidate result, count, and flags: output overflow bit 0; invalid candidate/data bit 1; reused/stale generation bit 2.
- [`benchmarks/gpu_visibility/runner.gd`](../../benchmarks/gpu_visibility/runner.gd) now records two compute dispatches in a local RenderingDevice: visibility → `compute_list_add_barrier` → guard. The packet is read back **only in the test fixture** and compared against a CPU-constructed expected command.
- All twelve source-defined scenarios are checked: the previous ten plus a count below capacity but **above the independent draw limit**, and a **zero-vertex geometry** case. These new cases must produce a no-op draw despite the visibility pass itself having no faults.

**Important safety distinction:** a zero-instance indirect draw is **not** an automatic conventional rendering fallback. It merely prevents the new experimental path from drawing incomplete data. A production integration would need an independent, validated mechanism to show all objects through ordinary Godot drawing on failure (and avoid double drawing on success). Do not merge an automatic replacement without that protocol.

### C — Separate offscreen raster probe

- [`benchmarks/gpu_visibility/indirect_probe.glsl`](../../benchmarks/gpu_visibility/indirect_probe.glsl): tiny vertex/fragment shaders draw a procedural green triangle for each valid selected handle. The vertex shader obtains its slot from the **GPU-visible-handle buffer** and samples its sphere record, testing the actual instance-index data path.
- [`benchmarks/gpu_visibility/offscreen_draw.gd`](../../benchmarks/gpu_visibility/offscreen_draw.gd) and [`offscreen_draw.tscn`](../../benchmarks/gpu_visibility/offscreen_draw.tscn): **optional standalone scene**, subclassing the visibility test runner but overriding its `_ready` to create a local RGBA8 framebuffer. The base fixture is unchanged when only `main.tscn` runs.
- The optional `_run_case(..., probe)` extension places a draw list **after** the compute lists and calls `draw_list_draw_indirect` with the exact GPU-written command buffer. For each scenario it reads a **single center pixel** from a 32×32 texture: green when at least one valid indirect instance should draw, otherwise clear black.
- The current draw test verifies **command consumption and suppression**, not per-instance pixel-perfect identity, mesh material/GI/shadow integration, or frame-time improvement. Because all procedural triangles overlap, one green pixel cannot prove that every selected instance was correctly rendered. Actual mesh and multi-view correctness requires further experiments.

## Verified fork-specific Godot source contracts

The source files inspected in `Azzirallas/Worlds-Engine` are the public Godot 4.8-beta fork, not private Unreal code:

- `servers/rendering/rendering_device.cpp`: `draw_list_draw_indirect` checks that the storage buffer has **INDIRECT** usage and that a non-indexed command has at least **16 bytes**; an indexed command requires **20 bytes**.
- `servers/rendering/rendering_device.cpp` and `rendering_device.h`: `STORAGE_BUFFER_USAGE_DISPATCH_INDIRECT` is the flag enabling that buffer usage **even for raster indirect calls**; the name is historical, so reuse the constant rather than introducing a fictional API.
- `servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp`: ordinary Godot MultiMesh already uses indirect command storage, so this experiment is to test visibility **and command generation**, not to add indirect drawing as though absent from Godot.
- `drivers/vulkan/rendering_device_driver_vulkan.cpp`: maps raster indirect calls to Vulkan.
- `servers/rendering/rendering_device.h` **in this fork** defines **`DRAW_CLEAR_COLOR_ALL`**, not the older stable-documentation spelling `CLEAR_COLOR_ALL`. The probe intentionally uses the fork's exact bound enum.
- `servers/rendering/rendering_device.cpp`: `render_pipeline_create` accepts `INVALID_ID = -1` as the vertex format for procedural shaders **with no vertex input attributes**, and demands a matching framebuffer fragment output mask.
- `servers/rendering/rendering_device_graph.h`: resource tracker has indirect-read usage. Cross-list GPU synchronization remains a **runtime correctness requirement**, even though the source has expected facilities.
- Godot RenderingDevice API documentation: [official class reference](https://docs.godotengine.org/en/stable/classes/class_renderingdevice.html). Stable docs may differ from this particular fork; source wins on version-specific call names.

## How to run after graphics-capable Godot is available

Requires a compatible Godot build, Forward+/RenderingDevice backend, shader importer, local-RD support and actual GPU drivers.

```sh
# Import both compute shaders and the separate vertex/fragment probe:
godot --path benchmarks/gpu_visibility --editor --quit

# First test compute visibility → guarded GPU command (no raster):
godot --path benchmarks/gpu_visibility

# Second test compute → guarded GPU indirect draw → RGBA8 pixel readback:
godot --path benchmarks/gpu_visibility res://offscreen_draw.tscn
```

The first scene should emit **12** `WORLDS_GPU_CASE_PASS` and one `WORLDS_GPU_VISIBILITY_PASS`; the second should additionally emit **12** `WORLDS_OFFSCREEN_CASE_PASS` and `WORLDS_OFFSCREEN_PASS`. Treat any parser/shader error, unsupported device or nonzero exit as **not validated**, even if only one scenario fails. If the driver/backend can't create a local device, record unavailable rather than claiming a pass.

The Python host-only test remains runnable without GPU:

```sh
python -m unittest discover -s benchmarks/theory -p 'test_indirect_draw_reference.py' -v
```

## Known limitations and next gates

1. **Cannot claim GPU success yet.** Neither `runner.gd` nor `offscreen_draw.gd` has been parsed by a Godot build; the shaders have not been compiled on the target driver; the new raster path has not executed.
2. **Screen pixels are deliberately simplistic.** All instances draw identical overlapping triangles. Next visual gate should encode distinct instance IDs and compare a full occupancy image, then actual world transforms/mesh geometry.
3. **Visibility reads are camera-dependent.** A future production renderer needs per-view buffer ownership/epochs; never share a visible buffer between cameras without a revalidation rule.
4. **CPU readbacks are diagnostic only.** All `sync`, `buffer_get_data` and `texture_get_data` calls are fixture work and must not appear on a performance-critical frame path.
5. **Resource lifetime:** slots can be reused while prior GPU frames are in flight; the generation check only handles candidates whose slot metadata is current. Native implementation requires delayed retirement, upload-order guarantees and proper fencing.
6. **Fallback requires design.** A suppressed draw alone leaves the object invisible. A safe opt-in mode should arrange an authoritative standard mesh draw unless the GPU result has been validated for that frame, and must avoid duplicate images when both paths are active.
7. **No renderer default replacement.** Material compatibility, clipping, real Godot camera matrices, animation displacement, shadows/GI, picking, editor interactions, backend portability and hardware performance are unverified.

**Recommended next development:** source-audit the synchronization and device ownership boundaries for a main-device opt-in draw, and develop a per-instance visual identity test; defer any production engine routing until a GPU machine provides evidence.

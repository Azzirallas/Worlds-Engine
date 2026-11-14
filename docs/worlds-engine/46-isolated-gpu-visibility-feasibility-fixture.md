# 46 — First isolated GPU visibility feasibility fixture

**Status (2026-11-14): committed source; not parsed by Godot, shader-compiled or executed on a GPU.** The normal Godot renderer remains unchanged. The prior CPU reference was executed in the research environment **14/14 PASS**. A connector-based source ABI consistency audit of the initial fixture returned **8/8 PASS**; this is **not** an executable shader test. The source was subsequently extended to add generation-tagged candidates and a tenth scenario; those changes require their own source check.

Read [45 CPU reference](45-visibility-reference-milestone-and-gpu-gates.md), [30 original visibility design](30-gpu-instance-visibility-design.md), [35 phase-1 gates](35-phase-1-validation-and-next-actions.md), and [DEC-012 mesh-first policy](15-decisions-and-open-questions.md).

## New source files

- [`benchmarks/gpu_visibility/project.godot`](../../benchmarks/gpu_visibility/project.godot): deliberately no explicit Compatibility renderer override; a device with Forward+ / RenderingDevice support is needed.
- [`benchmarks/gpu_visibility/main.tscn`](../../benchmarks/gpu_visibility/main.tscn): minimal empty `Node` running the fixture script.
- [`benchmarks/gpu_visibility/visibility.comp.glsl`](../../benchmarks/gpu_visibility/visibility.comp.glsl): original GLSL compute frustum/layer test; 64 local invocations; bounded atomic append with overflow/invalid-data/stale-generation flags.
- [`benchmarks/gpu_visibility/runner.gd`](../../benchmarks/gpu_visibility/runner.gd): builds seeded test cases and conservative CPU-region candidate lists, uploads arrays to a local RenderingDevice, verifies output slot IDs/generations against a full CPU scan; exits 0 on pass, 1 on error, 2 on unavailable RD.
- [`benchmarks/gpu_visibility/README.md`](../../benchmarks/gpu_visibility/README.md): execution, limitations and smoke-test commands.

**No engine renderer C++ source was changed. No splat work is involved.**

## Verified shader data contract (static source review only)

| Binding | Type | Contents |
| --- | --- | --- |
| 0 | `vec4[]` | world center xyz, bounding radius w, 16 bytes/slot |
| 1 | `uvec2[]` | layer/enable mask, generation, 8 bytes/slot |
| 2 | `uvec2[]` | candidate (slot,generation) from CPU region filtering, 8 bytes/candidate |
| 3 | `vec4[]` | frustum planes: inward normal xyz, offset w |
| 4 | `uvec2[]` | compacted (slot,generation) output, 8 bytes/hit |
| 5 | two `uint` values | atomic count and flags (overflow bit0, invalid slot/bounds bit1, stale generation bit2) |

Push constant block has **eight 32-bit words (32 bytes)**, five active params (candidate count, plane count, view layer mask, output capacity, total slot count) plus three reserved/padding words. This was deliberately padded after review of Godot push constant size/alignment discussions. The Godot runner submits the same 32-byte payload. All storage-buffer binding numbers were checked for completeness (0..5). No assumption that shader reflection or every driver has accepted the ABI yet.

## Test contract

Ten scenarios currently described in runner source: `empty`, `boundary_and_disabled`, `many_region_pruned`, `many_full_candidates`, `different_camera`, `nonunit_plane`, `overflow`, `all_visible`, `invalid_candidate_diagnostic`, `stale_generation_diagnostic`.

- A deterministic 4,097-record scene checks candidate filtering with multiple viewing/layer conditions.
- Each scenario computes **expected visibility using a complete slot scan independent of region pruning**, and verifies the region candidate set includes all expected IDs before dispatch.
- The compute kernel applies world-space sphere/frustum/layer predicates to the candidate slots and appends (slot,generation) results in **nondeterministic atomic order**. The runner sorts returned IDs before comparison, and verifies each generation.
- `overflow` deliberately limits output capacity to 13 while 257 records are visible. It checks the full atomic count and overflow flag, and validates that written IDs belong to the expected set; the algorithm must **never draw from this truncated list**.
- Invalid out-of-range candidate must raise diagnostic bit 1; successful other candidates must still be counted.
- The runner uses `submit()/sync()/buffer_get_data()` **only for one-off test parity**. These calls must **not** be ported unchanged into per-frame rendering.

## Limitations / potential first-run repairs

- The shader and GDScript **have not been compiled or executed by Godot**. This is the next real correctness gate, not a passed test.
- The float CPU predicate and GPU float32 operations have an explicit conservative epsilon; future correctness needs stress around rounding, giant coordinates, near/far plane, reversed Z and actual Godot camera frustum extraction.
- This first compute experiment writes an ID list, **not an indirect draw**. No mesh rendering, shadow pass, GI, normal scene visibility integration, occlusion/HZB or performance data.
- The region builder uses a CPU `Dictionary` for a small reproducible test; it is **not** a production data structure or an optimized scene-wide update path.
- Local RenderingDevice execution can be unavailable even when the main viewport renderer works on some platforms. A graphics-capable build with a supported RenderingDevice is required; failures must be reported as unavailable, not silently counted as passes.
- Godot documentation notes that **local** RenderingDevices cannot ordinarily be debugged in RenderDoc. A later GPU capture/indirect experiment needs an appropriate main-device path and a separate correctness review.
- Production fallback must use ordinary Godot mesh rendering. The source fixture merely reports `overflow_flags`, not a real draw fallback. An integration must reject or bypass the partial results.
- Godot draw/compute list API symbols already exist in this fork; **no** real resource barriers or indirect draw commands were exercised by this fixture.

## How to validate next time GPU hardware is available

```sh
# With the Worlds Engine Godot executable, graphics driver and Forward+ available:
godot --path benchmarks/gpu_visibility --editor --quit
godot --path benchmarks/gpu_visibility
```

Acceptance: all nine lines `WORLDS_GPU_CASE_PASS` and one final `WORLDS_GPU_VISIBILITY_PASS`. Record Godot SHA/build, backend, GPU, driver, operating system and shader compiler output. Nonzero exit or missing/unsupported GPU means **no pass**. Fix parser/shader/ABI problems first, then test pixel correctness with a follow-on opt-in draw fixture and a standard `MultiMeshInstance3D` control before claiming a performance benefit.

**Recommended continuation without GPU:** review the CPU→GPU scene-record ABI and possible Godot compiler edge cases, then strengthen adversarial CPU models for stale generation/pending upload packets, buffer overflow and highly scattered edits. Do not merge the experimental algorithm into the normal renderer before hardware validation.

## Public references

- [Godot — Using compute shaders](https://docs.godotengine.org/en/stable/tutorials/shaders/compute_shaders.html).
- [Godot — RenderingDevice API](https://docs.godotengine.org/en/stable/classes/class_renderingdevice.html).
- [Godot issue on push constant size alignment](https://github.com/godotengine/godot/issues/113583).
- Public Godot source files in Worlds-Engine `servers/rendering/rendering_device.h`, `rendering_device_graph.h`, and `renderer_rd/forward_clustered/render_forward_clustered.cpp`.

All experimental code is newly authored and uses public API contracts only, not private Unreal implementation details.

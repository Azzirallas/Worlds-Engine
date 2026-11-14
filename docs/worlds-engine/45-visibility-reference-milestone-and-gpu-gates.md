# 45 — GPU-driven visibility: CPU reference implementation and native integration gates

**State (2026-11-13):** code and tests committed in `benchmarks/theory/`. **14 CPU-only deterministic tests passed** in the research container using Python 3.13.5. Native GPU code: **not written**. Godot engine binary and graphics testing: **not performed**. No FPS/VRAM/driver results. Standard Godot renderer source is unchanged.

This follows [30 — optional GPU instance visibility specification](30-gpu-instance-visibility-design.md), [39 — MultiMesh sparse-update audit](39-sparse-instance-update-cost-and-gpu-selection.md), [35 — baseline/test program](35-phase-1-validation-and-next-actions.md), and [DEC-012 — mesh-first compatibility choice](15-decisions-and-open-questions.md).

## Implemented CPU reference

- [`benchmarks/theory/visibility_reference.py`](../../benchmarks/theory/visibility_reference.py): independent, standard-library-only **source model**. The code has concise function-level comments and no Godot/Unreal imports.
- [`benchmarks/theory/test_visibility_reference.py`](../../benchmarks/theory/test_visibility_reference.py): **14 unit tests**, including randomized adverse edit sequences, multi-view layer filtering, capacity overflow, immutable bound input, and retired-region cleanup.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_visibility_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

The model is intentionally built on world-space conservative **bounding spheres**, AABB regions (cells assigned by center), 32-bit layer masks, plane half-space frustum tests, and a full occupied-slot scan used as a correctness control. A transformed sphere uses an affine matrix-norm upper bound (including nonuniform scale and shear). A region AABB covers member **sphere extents**, including spheres straddling region boundaries. Empty region keys and their invalidation records are pruned.

**Identity and mutations:** slot+generation handles are presentation IDs, distinct from persistent Worlds-ECS identities. Delete advances generation; reuse cannot accept obsolete handle updates. The change queue is a slot-index dirty set: multiple writes in one frame produce the latest value; contiguous slots coalesce into runs, including deletion tombstones. Source CPU memory/input lists are normalized into immutable tuples, so external mutations cannot silently invalidate cached bounds.

**Visibility:** for each view, skip only regions with disjoint conservative AABBs. Test surviving member spheres and layer/enable flags. Output IDs sorted by stable slot identity. If an explicitly supplied visible-buffer capacity is exceeded, mark `fallback_required` and retain the **full visible list for safe CPU fallback**. The reference deliberately does **not** pretend to implement bounded GPU append, GPU fences, multi-draw groups, animation, occlusion or renderer-level submission.

## CPU test evidence and what it proves

Tests were executed in a container on 2026-11-13:

- 13 initial tests: PASS.
- Review uncovered two correctness/hygiene cases: mutable inputs and retired-region invalidation retention. Fixed both; expanded suite **14 tests: PASS**.
- The deterministic randomized test performs **180 create/move/delete steps** and compares regional selection against a complete scan for **4 distinct views per step** (720 parity checks). This checks the **coarse spatial reject path** against the same per-sphere frustum predicate; it is **not** an independent validation of Godot frustum extraction or real GPU pixels.

No real-world speed claims: this Python model sorts keys/slots and scans active regions; it is a correctness reference, **not an optimized Python runtime or guaranteed efficient renderer algorithm**.

## Direct Godot 4.8-beta API constraints verified

The public Worlds-Engine fork source exposes:

| API/source | Directly audited fact | Implication |
| --- | --- | --- |
| [`servers/rendering/rendering_device.h`](https://github.com/Azzirallas/Worlds-Engine/blob/master/servers/rendering/rendering_device.h) | `storage_buffer_create`, `buffer_update`, `buffer_copy`, `compute_pipeline_create`, `compute_list_dispatch`, `compute_list_dispatch_indirect`, `compute_list_add_barrier`, `draw_list_draw_indirect` exist | A compute→compacted-ID→indirect experiment can be investigated without a new generic render graph |
| same | `buffer_update` documentation warns not to call inside an active draw/compute list | Stage dirty uploads *before* recording relevant lists |
| same | `buffer_get_data` explicitly warns of a stall | Avoid CPU-readback visible count in every frame; use GPU-generated commands with validated barriers or fallback |
| [`servers/rendering/rendering_device_graph.h`](https://github.com/Azzirallas/Worlds-Engine/blob/master/servers/rendering/rendering_device_graph.h) | Graph has indirect draw/dispatch and buffer-update resource usage categories | Check actual producer→indirect consumer resource transitions in the selected backend; existence alone does not prove barriers correct |
| [`servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp`](https://github.com/Azzirallas/Worlds-Engine/blob/master/servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp) | Forward+ already submits indirect MultiMesh draws | An experimental path must demonstrate a benefit *beyond* existing indirect rendering |
| [`servers/rendering/renderer_scene_cull.cpp`](https://github.com/Azzirallas/Worlds-Engine/blob/master/servers/rendering/renderer_scene_cull.cpp) | Godot already has scene visibility and per-scenario culling | Never assume GPU culling is cheaper absent actual scene bottleneck evidence |

**Important:** these are *symbol/API existence* checks, not evidence that a particular indirect output packing, shader descriptor layout, draw-call ordering or format will work. Before GPU code, inspect the current buffer usage flags, alignment rules, resource lifetime and barriers in a graphics-equipped test build.

## Next implementation step: opt-in native RD feasibility fixture

No production edits until the ordinary baseline benchmark in `benchmarks/rendering/` can be smoke-tested. Then:

1. **Create a standalone test fixture** under `benchmarks/rendering/`, with a feature toggle and an unmodified fallback.
2. Use one **shared opaque mesh/material** and a fixed, reproducible world-space view, initially **1 camera** and no HZB or LOD. Build world-space spheres and region candidate IDs conservatively on CPU.
3. Upload a small instance table and candidates, dispatch a simple compute visibility predicate; allocate a **bounded ID output** and an overflow/diagnostic flag. Verify shader workgroup, std430 alignment, indirect-buffer usage and RD barriers against *this exact Godot revision*.
4. Render equivalent objects with normal nodes, a conventional regional MultiMesh control, and the experimental path. Compare captured results for missing instances and record **CPU + GPU total** work, not compute timing alone.
5. Exceed output capacity on purpose; fall back to standard rendering with a visibly reported error. No partial-frame invisible objects.
6. Only after pixel correctness, test static vs moving object deltas, camera cuts, resize, multi-view and device-loss handling. Introduce temporal/motion-vector support later.
7. Keep all changes additive and off by default; **do not** route regular Godot nodes through the experiment automatically.

## Main remaining risks

- **Scene semantics:** ordinary `MeshInstance3D` participation in shadow passes, GI, material overrides, transparency, editor picking, cull masks and 2D must remain unchanged. The first experiment supports only a narrow documented opaque mesh subset.
- **Buffer/graph synchronization:** a CPU reference cannot detect GPU races, barriers, in-flight slot reuse, indirect draw count encoding or backend-specific support.
- **Large-world precision:** Python floats and world-space spheres do not model 32-bit GPU precision, floating origin, interpolation, bone deformation or shader displacement.
- **Tessellation/occlusion:** no occlusion/HZB, animated bounds, alpha foliage, clustered LOD or skinning is modeled. These require new proofs and regressions.
- **Baseline competition:** one big MultiMesh and regional MultiMeshes may still beat a new GPU pipeline in low-count or coherent-motion workloads.
- **Hardware:** portability/quality gates need Windows/Linux AMD/NVIDIA test rigs; no test setup available at this moment.

**Decision:** keep standard mesh rendering the default. Continue source-level and CPU correctness work while graphics testing is unavailable. Treat optional splats [41–44] as a separate research lane.

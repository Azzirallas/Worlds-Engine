# 39 — Sparse moving instances: source-audited costs and GPU selection design

**Status:** direct Godot source audit, mathematically derived workload estimates, independently proposed architecture. **No hardware measurements, no engine implementation, no verified speedup.** Inspected 2026-11-13. Godot reference: `Azzirallas/Worlds-Engine` 4.8-beta fork; source blob hashes verified unchanged from `master@be1999a0f532124705359e4c3dde0a3b3034a0bd` for camera-cull, MultiMesh storage and meshoptimizer at audit time. Re-pin before implementing. Licensed Unreal source is **read-only reference**, never a source for the implementation. See [27](27-license-and-independent-implementation-protocol.md).

## Executive conclusion

The most attractive immediate experiment is **not** adding basic indirect draws: Godot already supports those. It is reducing unnecessary work in (a) instance visibility selection, (b) sparse transform uploads and (c) bounding volume maintenance while preserving all normal rendering semantics.

A distinctive source finding: MultiMesh tracks edits in fixed **512-instance** dirty regions and selects a **whole-visible-buffer upload** when the combined dirty region count exceeds **32** or half the visible regions. The choice is sensible for dense editing and minimizing per-update call overhead, but can over-transfer for scattered updates in very large groups. **This is an opportunity hypothesis, not a known performance regression:** many small uploads are not free, and motion-vector storage may add work.

## Exact Godot entrypoints

| Subject | Audited location | Direct source observation |
| --- | --- | --- |
| Camera candidate scanning | `servers/rendering/renderer_scene_cull.cpp` `_scene_cull`, `_scene_cull_threaded`, `_render_scene` | A camera pass partitions/scans `scenario->instance_data`, with layer/frustum/range/occlusion and type-specific work |
| Existing spatial structures | `servers/rendering/renderer_scene_cull.h` `Scenario` | `DynamicBVH` indexers already exist; an automatic replacement of the current camera path is not justified without measurement |
| MultiMesh dirty region setup | `servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp` | `MULTIMESH_DIRTY_REGION_SIZE = 512`; per-instance writes mark regions |
| Upload threshold | same file, `_update_dirty_multimeshes` | `total_dirty_regions > 32 || total_dirty_regions > visible_region_count / 2` chooses upload of the entire visible buffer; otherwise update dirty regions separately |
| Bounds maintenance | same file, `_multimesh_re_create_aabb`, `_update_dirty_multimeshes` | Unless a custom AABB is supplied, marked-dirty bounds can trigger a scan over visible instances to rebuild union bounds |
| CPU materialization | same file, `_multimesh_make_local` | If using GPU-owned buffer data and first requesting per-instance CPU access, an existing buffer can be read back to materialize a CPU cache |
| Indirect submission | `servers/rendering/rendering_device.cpp` `draw_list_draw_indirect` and Forward+ rendering code | RD already supports indirect drawing and checks indirect-buffer usage; Godot MultiMesh already uses an indirect path |
| Motion vectors | `mesh_storage.cpp`, Forward+ render list | Previous/current transform regions can be tracked separately when motion vectors are enabled; experiments must preserve temporal output |

The source fact `total_dirty_regions` includes both current and previous dirty sets in the audited code. Visible counts, material/data strides and interpolation can change actual update traffic.

Source links (all public Godot fork files, **not** Unreal):
- [Camera culling](https://github.com/Azzirallas/Worlds-Engine/blob/master/servers/rendering/renderer_scene_cull.cpp)
- [MultiMesh storage](https://github.com/Azzirallas/Worlds-Engine/blob/master/servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp)
- [RenderingDevice](https://github.com/Azzirallas/Worlds-Engine/blob/master/servers/rendering/rendering_device.cpp)
- [Forward+ submission](https://github.com/Azzirallas/Worlds-Engine/blob/master/servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp)

## Hardware-free model: scattered writes

Let:
- `N` = total instances in one fully visible MultiMesh;
- `R = 512` = dirty-region capacity observed in this revision;
- `p` = independent probability each instance changes during one frame;
- `B = ceil(N / R)` regions (last region may be partially filled);
- `S` = bytes per instance (illustrative transform-only 3D float layout uses 12 floats = 48 bytes; actual stride varies).

For bucket `b` with `n_b` instances, its probability of being dirty is `1 - (1-p)^{n_b}`. Thus:

`E[dirty regions] = sum_b (1 - (1-p)^{n_b})`.

This estimates **region activation**, not actual CPU/GPU times. It assumes independent random mutations; clustered movement yields very different occupancy. It ignores the additional previous-region set, making it a simplified model of the threshold.

For `N=100,000`, `R=512`, `S=48`, all visible, and independent random changes:

| Change rate | Expected changed instances | Expected dirty regions | Ideal changed-transform bytes | Source upload-policy implication |
| --- | ---: | ---: | ---: | --- |
| 0.01% | 10 | ~9.75 | 480 B | Dirty-region path likely; each region can still carry many unchanged transforms |
| 0.05% | 50 | ~44.13 | 2.4 KB | **Full visible-buffer path likely** because expected dirty regions exceeds 32 |
| 0.1% | 100 | ~78.32 | 4.8 KB | Full-buffer path likely |
| 1% | 1,000 | ~194.66 / 196 | 48 KB | Full-buffer path very likely |
| 10% | 10,000 | ~196 / 196 | 480 KB | Full-buffer path very likely |

A full **transform-only** upload for 100,000 instances would be approximately **4.8 MB** in this model, versus only **4.8 KB** of genuinely changed transform values for the 0.1% case. This is a **theoretical 1,000:1 byte-volume ratio**, *not* an observed transfer, performance loss or guarantee that 1,000 tiny GPU updates would be faster. Other attributes, motion vectors, buffer state and driver dispatch overhead must be counted.

### Consequences of the model

1. **Change locality is a first-class benchmark variable.** Compare uniformly scattered edits to clustered edits at the same changed count.
2. **Whole-scene visible count matters.** The source threshold and upload size use visible-region count; the simplified model assumes all N visible.
3. **Small regional MultiMeshes can reduce bounds/update impact** at the cost of more scene objects, calls and candidate management. Region size is an independent tuning dimension.
4. **One buffer per logical entity is not the answer.** Smaller transfers can become far more synchronization and driver work.
5. **Compaction has a cost.** Constructing packed dirty ranges, sorting and staging can lose to a bulk copy. We must compare full frame latency and memory, not only reduced bytes.
6. **Custom bounds are correctness obligations.** Reducing AABB recalculation via conservative region bounds must remain valid during transforms, animation, wind and streaming.

## Original proposed experiment: sparse-transform transport

A standalone, reversible experiment should compare *the strongest native Godot strategies* against a purpose-built optional scene table.

- **C0 — one MultiMesh:** per-instance setter updates, automatic AABB and existing dirty-region policy.
- **C1 — spatial MultiMesh groups:** selected region sizes; calculated and conservative custom AABB modes.
- **C2 — explicit bulk MultiMesh buffer updates:** same updates in a CPU-owned packed buffer with a full `set_buffer` call; separate initialization and steady-state costs.
- **E1 — batched dirty intervals:** original per-view/material-compatible instance data table, coalesce adjacent changes and update bounded contiguous ranges. Keep standard mesh shading and a fallback.
- **E2 — compact GPU-side scatter:** if supported and worthwhile, upload (index, new transform) patches into a temporary buffer; an independently authored compute step applies them to a persistent resident table. Compare GPU scatter, write hazards, synchronization and overhead with E1/C1.
- **E3 — visibility integration:** only after E1/E2 correctness, use per-region candidates and compute-visible IDs to avoid full CPU candidate preparation for applicable geometry; ordinary Godot scene semantics still drive lights, decals, GI, editor views, visibility layers and standard scene nodes.

E2 and E3 are **proposals**, not existing APIs, a requirement to use compute or proof of better performance.

### Transport risks to account for

- Scatter-gather can generate random device memory writes and extra barriers; relative cost varies by GPU.
- Region and instance mapping need generation-safe handles to avoid stale write jobs after free/reuse.
- Updates issued at arbitrary times may race GPU draws; retire/reuse GPU buffers with fences appropriate to Godot/RD.
- Material/mesh keys, skinning, previous transform and light/shadow versions must match ordinary rendering.
- If a render path is only faster for 0.1% scattered updates, route only that class through it; retain conventional MultiMesh otherwise.

## CPU-only correctness specification (no GPU required)

A later pure-CPU reference model can verify:
1. Run deterministic sequences of create/move/delete/reuse and confirm a stable-handle+generation mapping never applies old updates to a new object.
2. Rebuild expected world transforms from a simple authoritative array; compare after every coalesced patch batch, including duplicate writes to the same handle.
3. For each custom region, assert the union of all transformed conservative object bounds fits inside the region bounds after every motion, not just at startup.
4. Given a set of camera frusta, compare proposed coarse candidate results against an exhaustive plane/AABB reference with **zero false negatives**. False positives are acceptable.
5. Simulate dirty regions under random vs spatially correlated edits; compare actual dirty counts to the independent-probability model.
6. Test ordering: simultaneous create/delete, stale generation, region migration, camera cut, two viewports, shader reload, buffer-capacity exhaustion and fallback.
7. Keep CPU-model time separate from any claim about renderer GPU time. No fabricated throughput numbers.

## Decision rule

Before changing production renderer code, collect actual baseline CPU scene-cull time, AABB rebuild time, bytes uploaded, buffer update call count, render thread time, GPU cull/compaction time, p95/p99, motion-vector correctness and visual output. A technique can be adopted only if it is measurably better for a specified workload, does not create missing pixels, preserves ordinary Godot workflows, and has a nonregressing fallback.

**CPU-only model now committed:** [benchmarks/theory/multimesh_update_model.py](../../benchmarks/theory/multimesh_update_model.py) and [six deterministic tests](../../benchmarks/theory/test_multimesh_update_model.py) reproduce the report's expected dirty-region counts and compare clustered/scattered cases without graphics hardware. All six tests passed locally on 2026-11-13. The model simplifies the public Godot policy; it is neither an engine test nor an actual upload measurement. **Next source-only task:** add a generation-safe handle and conservative culling reference model, then design exact feature-detection/indirect-consumption fixtures. **Next hardware task (when available):** reproduce this table's scattered/clustered update cases on one GPU and determine which stage actually dominates.

Related: [30 — GPU instance design](30-gpu-instance-visibility-design.md), [18 — prior MultiMesh audit](18-res-002-multimesh-and-visibility.md), [35 — execution queue](35-phase-1-validation-and-next-actions.md), [38 — texture streaming source trace](38-texture-streaming-end-to-end-trace-and-validation.md).

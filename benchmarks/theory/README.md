# Hardware-independent rendering research models

This directory contains **CPU-only analytical models and invariants** for Worlds Engine research. These are not engine prototypes, actual GPU timing measurements, render quality tests or a substitute for the graphics benchmarks in [../rendering/](../rendering/).

## Global versus regional coarse root policy (11 new CPU tests)

[57](../../docs/worlds-engine/57-regional-geometry-roots-and-native-mesh-edge-audit.md) adds `root_topology_reference.py` and `test_root_topology_reference.py`: both topologies start with the same 32 model bytes of 4×4 coarse geometry, but the global parent requires sibling-region loads before refinement while independently resident regional roots do not. Synthetic traces report upload cost, temporary detail deficit, structural coarse submissions, protected frame references and safe evictions. **11/11 tests passed locally**, including 1,200 randomized camera requests. **No actual Godot draw timings or mesh compression claims.** A native opt-in edge audit is documented in [benchmarks/native_geometry/](../native_geometry/README.md); its C++ core compiled locally but the Godot wrapper has not been built.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_root_topology_reference.py' -v
```

## 2D edge ownership and integrated camera streaming (23 new passing CPU tests)

[56](../../docs/worlds-engine/56-2d-cluster-edges-and-synthetic-camera-traces.md) adds `cluster_2d_reference.py` (**13 passing tests**) and `geometry_camera_trace.py` (**10 passing tests**). The first verifies rectangular tiling, resident parent dependencies, ordered multi-edge profile overlap, missing split-vertex T-junctions and exact resident stitch certificates. The second combines page streaming, LOD pixel-error targets and 2D seam-safe selection in a reproducible 21-page camera lab. Synthetic trace telemetry reports deficit/excess detail cell-depth units separately, issued read/upload bytes, in-flight references, safe evictions and cancellation. **96/96 available local tests passed**, including earlier exploratory async tests not present in GitHub; 23 new committed tests passed. No Godot GPU execution or performance measurement.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_cluster_2d_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_geometry_camera_trace.py' -v
```

## Cluster coverage audit and seam-safe refinements (21 passing tests)

The previously unexecuted [54](../../docs/worlds-engine/54-cluster-coverage-cpu-contract.md) suite was run; 10/10 original tests passed. One actual missing-intermediate-parent bug was fixed and covered by a new regression, giving **11/11 current coverage tests**. [55](../../docs/worlds-engine/55-cluster-seam-correctness-and-dependency-audit.md) adds `cluster_seam_reference.py` and 10/10 passing tests for ordered integer border profiles, optional resident stitch validation, conservative coarsening and irreparable-root fallback. Both include seeded 2,000-case randomized coverage tests. **73/73 available local CPU tests pass**, but this includes older exploratory tests not committed to the repository and is not a complete checkout CI run. No GPU performance or real 3D crack-free geometry was tested.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_cluster_coverage_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_cluster_seam_reference.py' -v
```

## Async geometry lifecycle and projected-error LOD (27 committed tests passed)

[53](../../docs/worlds-engine/53-async-geometry-lifecycle-and-lod-error-cpu-milestone.md) adds `geometry_async_reference.py` (13 committed `test_geometry_async_release.py` cases passed) and `geometry_lod_reference.py` (14 committed `test_geometry_lod_reference.py` cases passed). The async model simulates versioned IO, decoded cache, upload, resident fallback, multi-camera demand, hot reload and scene-reset drain under separate byte budgets; pages too large for mandatory limits are blocked before wasteful IO. The LOD selector checks world-error projection under perspective/orthographic cameras, near-plane crossings, resident-parent chains and temporal hysteresis. **27/27 committed tests passed locally**, including 1,200 randomized streaming operations and 700 projected-error checks; a separate extended local 25-test async suite passed but was not committed. Exact committed file bytes were verified by length/FNV-1a. No Godot/GPU execution or speedup measurement.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_geometry_async_release.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_geometry_lod_reference.py' -v
```

## Bounded upload scheduling and geometry residency (33 new CPU tests passed)

[51](../../docs/worlds-engine/51-bounded-immutable-staging-upload-reference.md) documents `staging_upload_reference.py` (19 passing CPU tests), combining `FrameSlots` epoch/generation identity and `WSP1` packet descriptors into an immutable, byte-budgeted staging queue with simulated transfer acknowledgements, stale-update coalescing, draw-frame hazard checks, and conservative scene reset. [52](../../docs/worlds-engine/52-geometry-page-residency-cpu-contract.md) adds `geometry_residency_reference.py` (14 passing tests): pinned coarse roots, parent-first detail loading, per-camera epoch demands, resident/upload byte caps, transactional evictions and in-flight page holds. The local research directory ran **57/57 tests** with Python 3.13.5; it is a *partial local copy*, not a full repository CI run. The two new modules and tests are checksum-matched with GitHub.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_staging_upload_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_geometry_residency_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

None of these tests uses a GPU or proves a rendering speedup. The geometry model is **not** a replacement for Godot's pre-existing texture-streaming implementation.

## Scene epochs and full-frame CPU instance identity (24 new tests passed)

[50](../../docs/worlds-engine/50-scene-epoch-reset-and-cpu-instance-identity-oracle.md) records the two-phase CPU scene reset that drains submitted frame tickets before recycling old scene buffers. `Handle(slot, generation, scene_epoch)` prevents ABA after whole-scene replacement, including when identical slots and generations reappear. `test_scene_epoch_reset.py` passes **12 tests**, including 24 repeated resets and 1,300 randomized operations. `identity_raster_reference.py` produces a deterministic RGBA8 per-slot triangle ID image, and `test_identity_raster_reference.py` passes **12 tests**, detecting missing, swapped, duplicate and overflowing instances across *all* pixels. **24/24 new CPU tests passed** locally; no GPU implementation or performance has been validated.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_scene_epoch_reset.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_identity_raster_reference.py' -v
```

## Refcounted slot lifetimes and versioned update ABI (17 new tests passed)

The follow-on [49 specification](../../docs/worlds-engine/49-refcounted-slots-and-u32-upload-packet-contract.md) adds per-slot outstanding-frame counters (O(1) reference lookup), 32-bit generation/revision fail-closed exhaustion, and a versioned **32-byte little-endian** GPU upload descriptor with scene epoch and 16-byte payload-offset alignment. [test_frame_refcount_wrap.py](test_frame_refcount_wrap.py) validates 1,500 seeded interleavings and independent count parity (8 tests). [test_gpu_slot_packet_abi.py](test_gpu_slot_packet_abi.py) validates byte layout, malformed data, stale epoch and 1,000 binary roundtrips (9 tests). **17/17 tests passed locally on 2026-11-14**; exact committed files match the tested local copies by length and checksum. No GPU shader or Godot build was executed.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_frame_refcount_wrap.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_gpu_slot_packet_abi.py' -v
```

## Frame-safe GPU presentation lifetimes (14 prior tests passed)

[`inflight_slot_reference.py`](inflight_slot_reference.py) and [`test_inflight_slot_reference.py`](test_inflight_slot_reference.py) model CPU authoritative slots, generation-tagged publication packets, pending GPU-frame references, deferred updates, tombstone publication and safe recycling. Multiple frame/view tickets protect the same slot until *all* retire; stale or out-of-order updates never overwrite a newer generation. A full or not-yet-published table rejects experimental submission rather than dropping instances.

**Executed 2026-11-14:** **14/14 new tests passed**, and a combined local rerun of the visibility, indirect-command and lifetime reference suites passed **41/41**. The tested lifetime source and tests were checksum-matched to GitHub after the final test edit. A prior source review also found and fixed a generation-reset/tombstone bug. No Godot renderer, real GPU fences or performance measurements are involved.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_inflight_slot_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

See [48 — frame lifetime invariants and hardware-free development plan](../../docs/worlds-engine/48-inflight-presentation-lifetimes-and-hardware-free-validation.md). This is deliberately a simple correctness model; its per-frame reference scans are not a recommended production complexity target.

## New CPU visibility correctness reference (14 tests passed)

[visibility_reference.py](visibility_reference.py) and [test_visibility_reference.py](test_visibility_reference.py) implement an **independent reference model**, not Godot's live culler or a GPU renderer. Its region AABBs conservatively enclose all member world-space spheres, including bounds that cross cell lines. It implements generation-safe handles, layer-masked multi-view frustum selection, coalesced contiguous dirty records with deletion tombstones, and an explicit full-result CPU fallback when a future compacted buffer would overflow. Affine nonuniform scaling/shear uses a conservative radius multiplier. Invalid inputs and mutable external lists are handled explicitly.

Run:

```sh
python -m unittest discover -s benchmarks/theory -p 'test_visibility_reference.py' -v
```

**Result (2026-11-13, Python 3.13.5 in the research environment): 14/14 tests passed.** The randomized parity test compares region-pruned results against a full per-instance scan for 4 views across 180 mutation steps. This checks CPU algorithmic invariants only: **no Godot, GPU, driver, measured speedup or visual validation**. Read [45 — validated scope, RD APIs and next hardware gates](../../docs/worlds-engine/45-visibility-reference-milestone-and-gpu-gates.md).

## Guarded GPU indirect command ABI (13 tests passed)

[`indirect_draw_reference.py`](indirect_draw_reference.py) and [`test_indirect_draw_reference.py`](test_indirect_draw_reference.py) specify the **16-byte non-indexed indirect packet** (`vertex_count, instance_count, first_vertex, first_instance`) and a **fail-closed** guard. Nonzero visibility errors, exceeded append/draw capacity or an invalid mesh force **zero instances**; actual conventional draw fallback is a separate required responsibility. **13/13 tests passed** with Python 3.13.5 in the research container on 2026-11-14, including 2,500 reproducible random decisions, little-endian serialization, missing overflow flags, stale generations and unknown-future fault bits.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_indirect_draw_reference.py' -v
```

This is an ABI/correctness model, **not a GPU test**. Its separate compute/raster experiments are in [`../gpu_visibility/`](../gpu_visibility/), documented by [47](../../docs/worlds-engine/47-guarded-indirect-and-offscreen-raster-probe.md). The earlier 14-test regional visibility reference was not rerun as part of this new CPU test execution.

## Current model: MultiMesh scattered-instance updates

Run from the repository root with Python 3 (standard library only):

```sh
python benchmarks/theory/multimesh_update_model.py
python -m unittest discover -s benchmarks/theory -p "test_*.py" -v
```

Six deterministic tests passed in the research environment on 2026-11-13: occupancy boundaries, clustered vs scattered edits, previous dirty carry-over, partial visible bucket, duplicate coalescing and invalid input.

**Model scope:** the source-audited Godot 4.8-beta MultiMesh policy: dirty regions of 512 transforms, full visible-buffer path when combined current/previous dirty-region count exceeds 32 or half of visible regions, example 48-byte 3D transform. The model calculates **bytes selected by that simplified policy**, not actual bytes seen by a driver. It does not simulate pipeline scheduling, buffer allocator behavior, motion-vector buffer duplication, threading, CPU execution cost, GPU/PCIe bandwidth, shader stalls, upload overlap or additional material data.

### Reproducible theoretical case

For 100,000 **fully visible** transform-only instances and exactly 100 changed transforms:

| Spatial pattern | Estimated path | Estimated upload |
| --- | --- | ---: |
| First 100 instances (clustered) | One dirty region | 24,576 bytes |
| Every 1,000th instance (scattered) | Full visible buffer | 4,800,000 bytes |

These differences are **model outputs**, not measured engine transfers. A good GPU driver may prefer a full upload to many scattered updates. We must not claim the byte ratio is a frame-time speedup.

### Research trace

See [39 — sparse instance update cost and GPU selection](../../docs/worlds-engine/39-sparse-instance-update-cost-and-gpu-selection.md) for the math, source locations, hypothesis limitations, required graphics tests and comparison plan. Cross-check the policy constants whenever the underlying Godot revision changes. No Unreal source was copied or referenced in the implementation.

Potential next CPU-only model: generation-safe presentation handles, conservative region AABB coverage, coalesced transform updates and multi-view candidate selection. Those are correctness tests, not performance claims.

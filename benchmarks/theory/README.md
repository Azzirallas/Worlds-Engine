# Hardware-independent rendering research models

This directory contains **CPU-only analytical models and invariants** for Worlds Engine research. These are not engine prototypes, actual GPU timing measurements, render quality tests or a substitute for the graphics benchmarks in [../rendering/](../rendering/).

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

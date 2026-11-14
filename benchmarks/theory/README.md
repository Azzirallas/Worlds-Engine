# Hardware-independent rendering research models

This directory contains **CPU-only analytical models and invariants** for Worlds Engine research. These are not engine prototypes, actual GPU timing measurements, render quality tests or a substitute for the graphics benchmarks in [../rendering/](../rendering/).

## New CPU visibility correctness reference (14 tests passed)

[visibility_reference.py](visibility_reference.py) and [test_visibility_reference.py](test_visibility_reference.py) implement an **independent reference model**, not Godot's live culler or a GPU renderer. Its region AABBs conservatively enclose all member world-space spheres, including bounds that cross cell lines. It implements generation-safe handles, layer-masked multi-view frustum selection, coalesced contiguous dirty records with deletion tombstones, and an explicit full-result CPU fallback when a future compacted buffer would overflow. Affine nonuniform scaling/shear uses a conservative radius multiplier. Invalid inputs and mutable external lists are handled explicitly.

Run:

```sh
python -m unittest discover -s benchmarks/theory -p 'test_visibility_reference.py' -v
```

**Result (2026-11-13, Python 3.13.5 in the research environment): 14/14 tests passed.** The randomized parity test compares region-pruned results against a full per-instance scan for 4 views across 180 mutation steps. This checks CPU algorithmic invariants only: **no Godot, GPU, driver, measured speedup or visual validation**. Read [45 — validated scope, RD APIs and next hardware gates](../../docs/worlds-engine/45-visibility-reference-milestone-and-gpu-gates.md).

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

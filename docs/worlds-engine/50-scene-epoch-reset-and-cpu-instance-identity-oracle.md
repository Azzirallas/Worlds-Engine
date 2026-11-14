# 50 — Scene epoch reset and full-frame CPU instance-identity oracle

**Status: CPU-only implementation committed, 2026-11-14.** GPU hardware remains unavailable. **24 new tests passed locally**: 12 tests for the scene reset/ABA reference (including a 1,300-step seeded stress sequence and 24 consecutive resets), and 12 for CPU rasterized per-instance ID images (including 200 randomized selection comparisons). Tests are independent of a Godot build, GPU and paid CI. No production renderer or engine C++ files changed.

Prior context: [30 — GPU instance visibility](30-gpu-instance-visibility-design.md), [45 — CPU visibility parity](45-visibility-reference-milestone-and-gpu-gates.md), [47 — indirect raster probe](47-guarded-indirect-and-offscreen-raster-probe.md), [48 — safe presentation lifetimes](48-inflight-presentation-lifetimes-and-hardware-free-validation.md), [49 — refcounts and bounded GPU upload ABI](49-refcounted-slots-and-u32-upload-packet-contract.md).

## A. Scene-epoch protection implemented

The existing [`benchmarks/theory/inflight_slot_reference.py`](../../benchmarks/theory/inflight_slot_reference.py) now carries **scene epoch** inside `Handle(slot, generation, scene_epoch)` and therefore all `Packet` references. Its default epoch is 1, preserving the original two-argument handle construction in earlier tests. A handle from epoch 1 can never match epoch 2, even when the new scene recycles exactly the same **slot and generation**. All live handle checks and packet publication validate the epoch before accepting data.

A deliberate **two-phase reset** preserves old GPU-frame memory in the *CPU model* while the outstanding frames drain:

1. `begin_reset()`: reject new fast-path submissions with `reset_pending`, reject all live mutations, reject uploads, and discard deferred packets. If the scene epoch is exhausted, reject reset before changing anything.
2. `retire(frame)`: accept completion tickets out of order; decrement per-slot frame references. While resetting, do **not** publish pending stale writes or recycle old slots.
3. `complete_reset()`: reject until **every** prior frame ticket has finished and reference counts reach zero. Only then clear the old CPU/GPU mirror arrays, free/retirement tables and pending state, advance `scene_epoch` once, and permit new slots. Frame tickets remain strictly increasing across resets so a late old completion cannot retire a new frame.

The terminal generation of a saturated slot remains **unreusable within its epoch**. A whole-scene reset may begin a new identity namespace *only after* previous frames have completed; no generation or epoch wraps to zero. The CPU model does not implement actual GPU fences or allocator releases, only the required invariants.

**Faults exercised in [`test_scene_epoch_reset.py`](../../benchmarks/theory/test_scene_epoch_reset.py):** ABA slot/generation collision across reset, two-camera frame drainage and out-of-order retirements, discarded deferred transforms, unpublished tombstones, terminal generation recovery only via new epoch, exhausted epoch refusal, repeated/misordered reset calls, stale completion tickets, empty in-flight tickets, invalid epoch constructor inputs, 24 successive resets with retained stale packets, and 1,300 seeded interleaved operations with independently recomputed reference counts.

### GPU upload compatibility

The fixed 32-byte `WSP1` descriptor in [49](49-refcounted-slots-and-u32-upload-packet-contract.md) already carries `scene_epoch` independently of `generation` and `revision`. The scene epoch now exists **in the CPU slot model**, but these are still *separate experimental modules*: there is no validated native upload manager, atomic transaction from the CPU model to an immutable staging allocation, or integrated GPU shader check yet. The existing `visibility.comp.glsl` checks slot/generation only. A future production path must bind the exact upload packet namespace and GPU buffer lifetime to the same scene epoch, with driver fences and device-loss handling.

## B. Full image-identity CPU oracle

The new [`identity_raster_reference.py`](../../benchmarks/theory/identity_raster_reference.py) rasterizes small **procedural triangles into a complete RGBA8 image** using exact integer edge functions and a deterministic top-left edge rule. Each slot occupies its own nonoverlapping tile (8×8 pixels by default). No scene simulation or rendering engine is required.

- `slot_rgb(slot)` encodes **slot+1 in little-endian RGB24**; zero RGB is reserved for an opaque black clear pixel. This test visual format can encode slots `0..0xFFFFFE` only; higher slot IDs fail explicitly rather than alias an existing color.
- `triangle_for_slot` maps a slot to deterministic tile geometry. A slot beyond the configured tile grid, invalid tile size, duplicate slot or output count greater than declared capacity is rejected **before returning a partial image**.
- `render_ids` emits the full immutable image. Because each valid slot has a distinct tile and color, arbitrary atomic append order produces the **same** reference image.
- `ids_in_image` decodes every pixel, not a single sample. `compare_images` reports differing pixel count and exact sets of **missing and unexpected slot IDs**, rejecting truncated readbacks and invalid alpha.
- [`test_identity_raster_reference.py`](../../benchmarks/theory/test_identity_raster_reference.py) contains 12 cases, including 200 seeded random subsets and omitted-instance checks, duplicate/overflow failure, swapped slot detection, high-byte RGB encoding, and full-frame draw-order invariance.

### Why this is stronger than the earlier GPU fixture

The unexecuted [47 offscreen probe](47-guarded-indirect-and-offscreen-raster-probe.md) has each instance draw an identical green triangle in the same location and checks the center pixel. That test could still pass even if a large fraction of selected instances disappeared. A **per-slot encoded image** can flag *which* instance is missing or incorrect. The CPU oracle establishes what the expected full image **should** be; it does not claim Godot or any GPU has rendered such an image.

**GPU alignment is still a design task:** a future separate shader must use the same slot-to-tile transform, RGB ID encoding and clear color, and an optional full-frame readback test must account for Vulkan/Godot viewport orientation, pixel-center/edge precision, rasterization state, and any color-space conversions. Do not compare the existing overlapping-green shader to this identity oracle as though their outputs already match. Do not put readback in the production per-frame path.

## Reproduce without GPU hardware

From the repository root, with Python 3 standard library:

```sh
python -m unittest discover -s benchmarks/theory -p 'test_scene_epoch_reset.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_identity_raster_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

**Evidence:** 24/24 newly added tests passed in a CPU-only local container. The exact three newly added files (`test_scene_epoch_reset.py`, `identity_raster_reference.py`, and `test_identity_raster_reference.py`) were compared byte-for-byte via length and checksum with their committed GitHub counterparts. The modified `inflight_slot_reference.py` was implemented and tested locally with the same epoch/reset behavior and patched into the repository; its GitHub version retains some earlier comments/docstrings, so its bytes are **not identical** to the local rewrite. A full checkout-and-run of the precise GitHub HEAD across *all* existing test files has **not** been performed in this turn; avoid treating it as one.

## Scope and unresolved issues

- A CPU frame completion is **not** a GPU fence. Nothing here proves actual storage safety on Vulkan/D3D/Metal drivers. Native memory lifetime, multi-buffered copies and resource transitions remain separate work.
- `FrameSlots` is a **correctness oracle**, not a high-throughput native allocator. It uses Python deep copies and scans frame handles at admission and retirement, even though checking whether a particular slot is referenced is O(1).
- The identity image is a **test visualization format**, not a general mesh renderer. Fixed per-slot tiles are unsuitable for actual world rendering; use it only to verify the selected ID set and rendering command data path.
- Scene reset is deliberately conservative and freezes the optional path until prior in-flight work drains. A production engine may later support a second scene table in parallel, but must prove separate device allocations/epochs and bounded VRAM cost first.
- The default Godot renderer must remain authoritative. Rejecting an experimental submission or emitting a zero-instance indirect command **is not** an automatic fallback draw; production integration still needs an explicit standard-mesh draw route.

## Next hardware-free work

1. Integrate the `WSP1` packet validation contract with the epoch-aware frame table **in a CPU-only upload queue**, including immutable staging ranges, per-frame byte budgets and stale completion cancellation.
2. Begin **geometry cluster/LOD + residency budgeting** CPU reference models based on public Godot and meshoptimizer primitives. Favor deterministic visible-detail correctness, byte limits and low-cost fallbacks over speculative speed claims.
3. Once actual hardware access resumes, run the *existing isolated* Godot GPU fixtures before attempting a feature-flagged native renderer integration. GPU testing is **not** the immediate development blocker.

No private Unreal code was copied; all source here is original.

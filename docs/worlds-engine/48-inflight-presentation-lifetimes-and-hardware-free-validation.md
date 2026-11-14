# 48 — Frame-safe presentation lifetimes: CPU implementation and hardware-free validation

**Status: implemented CPU reference, 14/14 original lifetime tests passing; subsequently extended in [49](49-refcounted-slots-and-u32-upload-packet-contract.md) with O(1) per-slot reference counts and bounded unsigned GPU identities (17 additional CPU tests passed).** Date: 2026-11-14. On the available CPU-only research environment, the combined `visibility_reference`, `indirect_draw_reference`, and new `inflight_slot_reference` suites ran **41 tests: PASS**. The local copies of the two new files were verified to match committed GitHub content (length and FNV-1a checksum). No actual GPU work, Godot runtime parsing or hardware performance measurements have been performed.

**Decision:** because graphics hardware is unavailable, continue Phase 1 with source audits, deterministic correctness models, negative/fault-injection testing, memory and scheduling theory, and precise independent architecture contracts. Do **not** stop development to await a GPU. Keep native/render hardware verification a later acceptance gate. Standard Godot mesh rendering remains the stable default.

Related: [30 GPU instance visibility design](30-gpu-instance-visibility-design.md), [32 residency contract](32-residency-streaming-contract.md), [45 initial CPU reference](45-visibility-reference-milestone-and-gpu-gates.md), [46 compute fixture](46-isolated-gpu-visibility-feasibility-fixture.md), [47 guarded indirect and offscreen fixture](47-guarded-indirect-and-offscreen-raster-probe.md).

## Actual implementation

- [`benchmarks/theory/inflight_slot_reference.py`](../../benchmarks/theory/inflight_slot_reference.py): `FrameSlots` reference-model state machine with bounded slots and in-flight frames.
- [`benchmarks/theory/test_inflight_slot_reference.py`](../../benchmarks/theory/test_inflight_slot_reference.py): 14 tests, including 1,000 reproducible random interleavings of create, update, delete, publish, submit and retire.
- The existing `visibility_reference.py` and `indirect_draw_reference.py` remain independent. This module is **not** a replacement for Godot's actual buffer/fence management.

### Identity and publication states

- `Handle(slot,generation)` is a **temporary presentation handle**; it is not a persistent simulation identity.
- `create(value)` returns a `Packet(handle, revision, value)`, but no experimental draw is allowed until that packet is **published**.
- `update` increments a monotonically increasing revision in the same generation. Packets whose revision no longer matches the authoritative CPU value are rejected as **STALE**, preventing an old transform from overwriting a newer one.
- `submit(handles)` creates a simulated frame ticket **only** if all referenced live slots have an up-to-date published GPU mirror. Otherwise the optional fast path is rejected with an explicit reason; the hypothetical caller must preserve conventional rendering.
- `retire(frame)` simulates a *real completion acknowledgement*. Retiring one frame does not release a slot if another submitted frame still references it.
- A write to a referenced physical slot is **DEFERRED**, not applied to an in-use resource. Once every referencing frame retires, the latest matching pending packet may publish.
- `delete(handle)` invalidates the live generation immediately and creates a new-generation **tombstone**. A slot only becomes reusable after **all referenced frames finish AND the new-generation tombstone is published**.
- The table enforces optional `max_slots` and `max_inflight`. Exceeding either fails explicitly; it never overwrites an in-flight object or truncates the frame's intended instance list.

### Defect found during source review and fixed

The initial delete transition incremented `generation` and reset `revision` to 1, but retained the old generation's `published` revision. When the previous generation had also published revision 1, the tombstone could be wrongly treated as **DUPLICATE**, permanently preventing slot release. Corrected by resetting `published[slot]=0` on generation advance. The full 14-test suite passed after this fix.

### What the tests specifically establish

- Initial publication gate; source-value snapshot immutability.
- In-flight transform update deferral and reapplication after retirement.
- Deleted-slot quarantine while one/two view frames reference the old storage.
- Out-of-order frame completion and real bounded slot-pressure rejection.
- Explicit unpublished-tombstone gate.
- Superseded/stale update packets, including late arrivals after deletion.
- Independently submitted camera frames sharing the same instance table.
- Invalid handles, duplicate instances, in-flight budget exhaustion and zero-slot capacity.
- Seeded interleavings and eventual completion of all accepted tickets.

**Reproduce without Godot or GPU:**

```sh
python -m unittest discover -s benchmarks/theory -p 'test_inflight_slot_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

The second command also runs other existing tests; its total may exceed 41. **The recorded 41 PASS** is the explicitly rerun combined visibility + indirect command + in-flight lifetime suites, not a complete all-repository CI run.

## Why this matters before native implementation

A GPU shader's generation comparison alone is **insufficient** to guarantee old frame draws are safe. If a scene slot's storage is reused before the GPU consumes an earlier frame, shader-side generation data may have changed too. A physical slot must remain alive, its consumed data must remain stable, and its generation must not be recycled until the correct synchronization condition is met. Safe alternatives to waiting for all readers (copy-on-write buffers / multi-frame replicas) require **separate measured implementation and accounting**.

This reference deliberately chooses the simple conservative policy: **defer mutation of any slot referenced by a submitted frame**. [49](49-refcounted-slots-and-u32-upload-packet-contract.md) improves the referenced-slot check to an O(1) counter without changing that conservative policy. It is easy to reason about, but may cause unnecessary stalls/fallback under heavy motion. A production design should compare deferred writes to per-frame buffer versioning, multi-buffering and scoped fence-based retirement once hardware becomes available.

## Important limitations (do not overclaim)

1. **A Python frame ID is not a GPU fence.** We model completion as explicit `retire(frame)` supplied by a test. No Godot `RenderingDevice` fence semantics, command queue behavior, barrier placement, buffer mapping, indirect buffer hazard or thread safety has been verified.
2. **No actual fallback draw call.** A rejected `submit` means **the optional fast path is ineligible**; the host renderer must still implement a real conventional mesh draw. Safety cannot be established from a diagnostic flag alone.
3. **Not an optimized runtime.** This model scans outstanding frames to find references and copies Python values; it is a correctness oracle, not an O(1) production allocator, memory layout, or speed prediction.
4. **Integers are unbounded in Python.** Native slot generations and revisions will require explicit overflow/ABA policy when mapped to GPU `uint32`. Do not let generation wrap silently.
5. **GPU memory and texture/geometry residency are separate.** This tracks presentation-table slots only, not asset page sizes, staging uploads, allocation fragmentation, or residency pressure.
6. **Visibility and shading remain unverified.** Need Godot/GPU execution for the compute/shader and raster fixtures, camera precision, mesh material integration, shadows, editor semantics and actual quality/performance results.

## Next useful hardware-free engineering work

1. **Reduce model overhead theoretically:** add a per-slot in-flight reference count and compare its invariants to the current full scan of frame tickets; tests must prove exact parity even for out-of-order completion.
2. **Define GPU packet ABI and overflow policy:** 32-bit generation/revision wrap, alignment, max buffer limits, update/tombstone ordering, multi-frame mirror contracts. Create binary roundtrips and fuzz corrupted inputs.
3. **Develop software image-identity oracle:** a deterministic *CPU raster* for simple triangles that can later compare per-pixel IDs and coverage with the offscreen GPU probe, rather than checking only a green center pixel.
4. **Research/derive budgeted residency and geometry cluster contracts** while respecting existing Godot meshoptimizer, RenderingDeviceGraph and texture-streaming work; don't build speculative replacements from scratch.
5. **Once hardware is available**, first compile/smoke-test the exact isolated shader/scene fixtures, then test actual GPU synchronization and real mesh drawing. Do not merge into the default renderer before those pass.

**Version-specific source boundaries:** all implementation code was independently authored against the public Godot fork and standard algorithms. Licensed Unreal source remains a read-only high-level reference.

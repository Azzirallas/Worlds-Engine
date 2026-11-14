# 49 — Refcounted render slots and bounded GPU upload packet contract

**Status: CPU implementation and tests (2026-11-14).** Hardware unavailable; no native renderer modifications or Godot/GPU tests. This advances [48 — in-flight slot lifetime reference](48-inflight-presentation-lifetimes-and-hardware-free-validation.md) and [30 — GPU instance visibility](30-gpu-instance-visibility-design.md). Standard Godot rendering stays authoritative and unchanged.

## What changed in code

1. [`inflight_slot_reference.py`](../../benchmarks/theory/inflight_slot_reference.py) maintains one `slot_refs[slot]` count, incremented **only after** the entire frame's handle list is validated and admitted. On completion of a frame ticket, decrement exactly once for each referenced slot. Deferred updates/tombstones can publish only when the count drops to zero.
2. [`test_frame_refcount_wrap.py`](../../benchmarks/theory/test_frame_refcount_wrap.py) checks admission rollback (no reference leaks on rejected frames), three-camera overlap, retirement out of order, repeat-completion rejection, terminal generations, and a **1,500-operation seeded independent recount** of the whole frame-ticket table against every slot's cached count.
3. `FrameSlots` now has explicit, configurable `max_generation` and `max_revision` with **32-bit production defaults**. A revision update that would wrap is refused **before modifying the CPU record**; this requires conventional-renderer fallback or intentional object re-creation. A slot whose deletion advances to the terminal generation is **permanently nonreusable**, rather than wrapping and risking an ABA identity collision.
4. [`gpu_slot_packet_abi.py`](../../benchmarks/theory/gpu_slot_packet_abi.py) defines a versioned fixed-size descriptor for a **future** per-slot upload queue. [`test_gpu_slot_packet_abi.py`](../../benchmarks/theory/test_gpu_slot_packet_abi.py) checks little-endian byte layout, alignment, range limits, invalid flags, scene-epoch mismatch and **1,000 seeded binary roundtrips with corrupted format headers**.

**Executed in local CPU-only container:** 8/8 new refcount/wrap tests and 9/9 new descriptor tests passed, **17/17 total**. Local source files and committed GitHub contents were byte-equivalent under a length + FNV-1a check. Previous 41 tests from visibility, indirect draw and lifecycle references were not rerun as part of this run; the original 14 lifecycle tests remain in the repository and are expected to be included by the documented full-suite command below. Do not claim a 58-test current-turn pass without running those original tests.

## Precise refcount invariants

- **Admission is atomic:** validate duplicate handles, generation, published revision, GPU mirror and max-in-flight limit first; only then store the frame ticket and increment each slot count. Rejected submissions leave all counters unchanged.
- **One count per frame per slot:** duplicate handles in one frame are rejected, so `slot_refs` is a count of outstanding frames that can sample that physical slot, not the number of draw calls.
- **Retirement uses explicit completion:** finishing camera B before camera A must not free shared resources. An unknown or twice-completed frame fails rather than decrementing twice.
- **No mutation of referenced storage:** a pending update may be coalesced but is not applied while `slot_refs[slot] > 0`. When the count becomes zero, the latest still-current revision may publish.
- **Deletion is two-gated:** old GPU references must retire **and** the new-generation tombstone must publish before recycling. Any stale write packet from the earlier generation is rejected.
- **Lifetime is separate from scene visibility:** hiding or culling an object does not invalidate its slot identity or imply a simulation entity was deleted.

### Cost interpretation

The old reference `_referenced(slot)` searched every outstanding frame's handles: `O(sum of referenced handles in in-flight frames)` per query. The new `_referenced(slot)` is a direct `O(1)` array count read. **This is an algorithmic complexity improvement only**, not measured time saved in native Godot. A successful `submit` remains `O(H)` for `H` requested handles; a `retire` is `O(H)` for that frame's stored handles, and the model still copies Python values for safety. Frame ticket storage is still required to know which counts to decrement.

## Explicit 32-byte v1 descriptor ABI (CPU model)

The descriptor consists of eight little-endian unsigned 32-bit fields, `<8I`, exactly **32 bytes**. Both the header format and payload are **experimental design**, not an already accepted Godot shader ABI.

| Byte offset | Field | Contract |
| --- | --- | --- |
| 0 | magic/version | `0x31505357` (`WSP1` in little endian) |
| 4 | slot | uint32 index, 0 through `0xFFFFFFFF` |
| 8 | generation | nonzero; `0xFFFFFFFF` reserved as a **terminal tombstone generation**, never a live slot |
| 12 | revision | nonzero; must match the authoritative CPU revision exactly |
| 16 | scene epoch | nonzero; invalidates an old-world packet after scene/device reset |
| 20 | payload offset | 16-byte aligned for live packets; zero for tombstones |
| 24 | payload length | positive for live packets; zero for tombstones |
| 28 | flags | bit 0 = tombstone; every other bit currently rejected |

**Overflow policy:** All integers must fit uint32 without implicit Python/native truncation. `offset + length` must not exceed `0xFFFFFFFF` or the actual staging allocation; payload alignment is explicitly checked. A fresh scene epoch cannot roll over zero; reaching the maximum epoch requires replacement of the device-scene identity rather than recycling the number. Revisions refuse to wrap; a generation exhausted by deletions yields a terminal tombstone and a permanently retired slot. Terminal slots may increase capacity pressure, which is a deliberate **safe fallback** rather than a correctness risk.

**Ordering:** a receiver must compare the exact `(scene_epoch, slot, generation, revision)` tuple to its authoritative current record before accepting a packet. The header does not contain full instance data, a GPU fence, or a checksum for the payload itself; a future validated upload manager must bind it to an immutable staging buffer and implement secure upload and lifetime ownership.

**Important compatibility note:** the experimental `visibility.comp.glsl` currently consumes candidate `uvec2(slot,generation)`; this **new** 32-byte v1 upload descriptor is **not yet connected to that GPU experiment**. Its purpose is to define and test the host-side contract before updating any GPU-side ABI.

## Reproducible tests

From repository root, Python 3 (standard library only):

```sh
python -m unittest discover -s benchmarks/theory -p 'test_frame_refcount_wrap.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_gpu_slot_packet_abi.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

No GPU, shader compiler, Godot binary, network service, or paid GitHub Actions runner is required.

## Known limitations and future CPU-only tasks

- **No real GPU fence implementation:** frame completion is deliberately simulated. A packet header alone does not establish synchronization, memory barriers or GPU visibility correctness.
- **No native render-path fallback implementation:** capacity/refusal returns an ineligible fast-path result. The normal Godot renderer must remain a separate, real draw path; a zero-instance command is not itself a fallback.
- **No performance claim:** `O(1)` lookup reduces asymptotic reference checks, but throughput and memory benefits remain unmeasured; hardware-specific tests are later acceptance gates, not the next task.
- **Scene epoch update (2026-11-14):** [50](50-scene-epoch-reset-and-cpu-instance-identity-oracle.md) now adds `scene_epoch` to `FrameSlots` handles and implements two-phase whole-world reset with 12 passing CPU lifecycle tests. The `WSP1` upload descriptor and `FrameSlots` are **still separate reference modules**: an epoch-aware native/staging upload manager is not yet implemented.
- **Conservative integer exhaustion:** permanently retiring terminal slots uses memory capacity. A production design can reset a whole scene/device identity under guaranteed quiescence instead of wrapping per-slot handles.
- **Next hardware-free work:** model independent scene epochs and whole-world resets, a per-instance CPU raster/identity oracle for the offscreen shader fixture, and byte-budgeted geometry residency; preserve existing Godot meshoptimizer and texture-streaming infrastructure.

**Source policy:** all code is original and operates on public Godot concepts; licensed Unreal source is never copied.

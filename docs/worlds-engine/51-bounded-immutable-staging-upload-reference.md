# 51 — Immutable staging uploads, versioned GPU packets and byte-budget scheduling

**State (2026-11-14): committed and CPU-tested; no Godot/GPU runtime validation.** This is a synthetic resource-management reference for optional GPU-driven *instance-table uploads*. It is **not** a new production render path, real GPU transfer queue, graphics benchmark, or replacement for Godot's existing texture-streaming module.

Source: [`benchmarks/theory/staging_upload_reference.py`](../../benchmarks/theory/staging_upload_reference.py). Tests: [`benchmarks/theory/test_staging_upload_reference.py`](../../benchmarks/theory/test_staging_upload_reference.py).

**Evidence:** **19/19 newly added standard-library CPU unit tests passed**, including 800 seeded create/move/delete/transfer/submit/retire operations with an independent recomputation of both staged bytes and slot frame reference counts. The local test directory also ran **43/43 tests** across the currently materialized scene-reset, identity-image and staging tests. Both new source files' exact lengths and FNV-1a hashes were checked against the files returned from the GitHub connector after commit. **The entire repository's older tests were not cloned or rerun**, because the execution container cannot reach github.com. No graphical runtime, shader, driver or hardware metrics.

## Architecture and exact implemented contract

[48](48-inflight-presentation-lifetimes-and-hardware-free-validation.md) established deferred mutation while GPU frames reference a slot; [49](49-refcounted-slots-and-u32-upload-packet-contract.md) specified a 32-byte versioned `WSP1` packet descriptor; [50](50-scene-epoch-reset-and-cpu-instance-identity-oracle.md) added epoch-safe whole-scene reset. The new `StagingUploads` implementation connects those **existing CPU reference types** into one bounded upload-scheduling contract.

The model assumes the caller uses `FrameSlots` as its authoritative presentation table and provides **nonempty immutable `bytes`** for live records (or `None` for a deletion tombstone). In particular, mutable game objects, C# scene nodes and simulation entities are **not** serialized or altered by this model.

### Staging rules

1. `enqueue(Packet)`: validate the **scene epoch, slot, generation, revision, and payload equality** against the current `FrameSlots` table. Coalesce repeated updates for one slot into the newest immutable packet; stale or previously replaced revisions cannot overwrite an object. Invalid mutable/empty payloads raise, while a known stale packet returns `STALE`.
2. A queue slot consumes `32 + align_up(payload_length, 16)` **accounted bytes**, including its header (32 bytes even for a zero-payload tombstone). Maximum retained bytes, maximum total pending+in-flight packets, maximum outstanding transfer batches and maximum per-batch byte use are explicit constructor constraints.
3. `prepare()`: choose eligible packets within the byte limit. Skip slots still referenced by an in-flight **draw** or already held by another transfer. Pack non-overlapping payloads into a **new immutable `bytes` staging buffer**, each starting at a 16-byte boundary, with a validated `WSP1` descriptor. Producing a batch does **not** mean the source is published or drawable.
4. `acknowledge(batch, success)`: only the **exact outstanding transfer object** may complete, once. Release its reserved staging memory. On success publish the packet to the modeled GPU mirror only if **all identity/version fields remain current and no frame references its storage**. Failure or a newly unsafe reference becomes `RETRY`; replaced versions become `STALE`; a scene reset cancels old results. Retry queues never replace a newer slot revision.
5. `begin_reset()`: freeze experimental work using the `FrameSlots` two-phase protocol, drop queued packets but preserve the bytes owned by already prepared transfers.
6. `complete_reset()`: require **every old transfer acknowledgement** and **every old submitted draw frame completion** before releasing the old scene table and advancing its epoch. A still-active transfer cannot be silently forgotten just because no draw frame references its slot.

### What happens when resources are exhausted?

- A packet larger than the permitted one-batch limit, one exceeding the retained-byte ceiling, or one exceeding packet-count constraints raises `CapacityError` **before the queue mutates its accounting**.
- When a batch budget fills, other packets remain queued for a later batch; the model does not truncate a packet.
- A busy slot does not prevent an unrelated slot from being uploaded in the same step.
- An enqueue failure means the fast path is **not ready**; conventional mesh rendering must remain the external authoritative fallback. `StagingUploads` does **not** implement a fallback draw call.
- The model uses conservative accounting: retained bytes include the per-header cost and a 16-byte rounded-up payload reservation. Actual immutable staging buffers can use fewer bytes than their reservations.

## Specific tests

The 19 tests cover: initial upload readiness gate, immutable snapshots across newer CPU updates, two aligned payload offsets, multi-batch budget draining, atomic allocation failure, coalescing and duplicate rejection, in-flight draw hazard suppression, retry of failed transfer, newer revision beating a failed old transfer, forged/double acknowledgement rejection, deletion tombstone quarantine, scene reset with pending and outstanding transfers, reset waiting for a draw frame, retained-packet and byte limits, bounded transfer count, deletion during a transfer, independent upload progress while one slot is busy, rejection of mutable/empty/forged input, and 800 seeded mixed-operation accounting checks.

**Run CPU-only tests:**

```sh
python -m unittest discover -s benchmarks/theory -p 'test_staging_upload_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

The first command runs 19 tests. The second runs whatever tests are present in a complete working checkout; do not confuse this with the 43-test result from the partial local source directory.

## Deliberate scope limits

- **Transfer completion is simulated** by the caller's `acknowledge()`, not a GPU fence. It does not protect real Vulkan/Metal/D3D resources until a native integration provides correct submission and completion fencing.
- **Single-threaded reference only.** It does not implement concurrent producers, mapped staging rings, device-loss recovery, persistent buffer allocation, cache-coherent writes, actual graphics queue barriers, or shader readback.
- **Exclusive upload ownership is assumed.** Other code must not bypass this queue and directly mutate the same GPU-owned slot storage while transfers are in flight. The CPU reference cannot police a future renderer that ignores its contract.
- **Packet data is arbitrary bytes.** No transform, bounds, skinning, mesh/material layout or Godot scene serialization is implemented; the fixed `WSP1` descriptor is still an original research ABI, not a real Godot-visible GPU record.
- **No measured performance wins.** CPU algorithmic progress cannot establish native throughput or predict GPU transfer cost, memory pressure, shader correctness or multi-pass rendering quality.
- **Existing Godot texture streaming is not displaced**: this reference schedules prospective instance-table updates. [36](36-texture-streaming-baseline-audit.md) audits the already-present texture-streaming feature; geometry residency and quality fallbacks remain separate work.

## Next actionable hardware-independent work

1. Develop an independent **geometry page residency and fallback scheduler**: root/coarse coverage always available, demand coalescing, camera cuts, page dependencies, strict byte budgets, and in-flight eviction holds.
2. Link page residency to `FrameSlots` as a *simulation-only* request/permission contract; preserve a valid visual fallback until pages are actually ready.
3. Evaluate static geometry clusters and meshoptimizer-based preprocessing concepts using pure CPU quality invariants. Keep both as opt-in experiments, with no alteration of regular Node3D/MeshInstance3D behaviour.
4. **Later, when graphics hardware returns**, verify that the isolated compute/raster fixtures and new transfer ordering contract hold in an actual Godot build. Do not treat that as the immediate blocker.

**Independence:** all CPU code is original and grounded in public Godot RenderingDevice concepts; no proprietary Unreal implementation was copied.

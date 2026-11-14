# 52 — Hardware-free geometry page residency, safe eviction and quality fallback

**State (2026-11-14): synthetic CPU implementation committed, 14/14 new tests passed.** The two exact committed source files were compared by length and FNV-1a checksum to the copies executed in a local Python 3.13.5 container. The same local directory passed **57/57 tests** across scene reset, instance identity image, staged upload, and geometry residency suites. This is **not** a full GitHub checkout test run and is **not** GPU execution, hardware memory measurement or a replacement renderer.

Files:
- [`benchmarks/theory/geometry_residency_reference.py`](../../benchmarks/theory/geometry_residency_reference.py)
- [`benchmarks/theory/test_geometry_residency_reference.py`](../../benchmarks/theory/test_geometry_residency_reference.py)

Relevant decisions and research: [31 — optional geometry clusters/LOD](31-independent-virtual-geometry-design.md), [32 — residency and fallback architecture](32-residency-streaming-contract.md), [36 — existing Godot texture streaming](36-texture-streaming-baseline-audit.md), [51 — immutable instance-table staging](51-bounded-immutable-staging-upload-reference.md).

## What actually exists

The independent `GeometryResidency` model registers geometry **page records with parent fallback references**. The pages form parent-first trees (or forests), and a separate low-detail root must be registered for every hierarchy. A root is **pinned resident** from registration and its size is charged against a hard global capacity; a root registration is refused if the fallback cannot fit. This means `fallback(high_detail_page)` always returns a registered resident ancestor, even while fine pages are missing.

The model also implements:

- **Multiple independent view/camera epochs:** `request(page, view, epoch, importance)` records importance from 0–100 and refuses older camera epochs. Camera cuts discard that camera's old demand but not other cameras' demands or already-resident pages.
- **Deduplicated demand:** many cameras requesting the same page share one residency entry; the scheduler chooses the strongest effective page urgency, with simple bounded aging.
- **Parent-first loading:** a requested page is eligible only after its parent is actually resident. Only *whole* pages are made resident; per-step uploaded modelled bytes never exceed `max_upload_bytes`.
- **Conservative safe eviction:** roots never evict. A nonroot page is not evictable while referenced by an outstanding draw frame, required by a resident child, or needed as an ancestor of the page being loaded. Draw submissions protect the chosen detail page and its whole chain of resident ancestors until an explicit completion ticket retires.
- **Strict byte accounting:** the sum of every resident page's declared `size` cannot exceed the configured capacity; `verify()` independently recomputes size, hierarchy consistency, and reference counts.
- **Transactional eviction planning:** the scheduler computes whether enough eligible pages could actually be freed **before removing any**. If the next page still cannot fit, it retains the current visual quality instead of evicting several useful pages to no benefit.
- **Monotonic frame-ticket identity:** unknown and duplicate completion acknowledgements fail, preventing leaked or prematurely released page references.

This is **geometry-only**. It does not replace or modify the `modules/texture_streaming/` already present in the audited Godot fork.

## Review findings and corrections

The first implementation failed the seeded camera traversal stress test. A planned load could evict the **parent representation required for its own fine page**, producing a resident fine page with a missing dependency. The following corrections were made and tested:

1. Keep every ancestor of a candidate page off its eviction list.
2. Recheck a candidate's parent **at the moment of loading**, because an earlier page decision during the same scheduling step may have removed a previously valid dependency.
3. Make eviction selection transactional so an ultimately unsuccessful load does not discard the current higher-quality representation.

The final reference passed **14 tests**, including 500 deterministic camera-view and page-demand changes with modelled frame overlaps.

## Reproducible CPU-only tests

From a working Worlds-Engine checkout (Python 3, standard library only):

```sh
python -m unittest discover -s benchmarks/theory -p 'test_geometry_residency_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_staging_upload_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

The first command runs 14 tests; the second runs 19. The third includes other existing repository tests and may have a different total than the **57 tests from the partial local working directory**.

Adversarial scenarios in the 14-test suite: root fallback always drawable; parent-first medium/fine load; page too large for capacity; upload budget smaller than an indivisible page; rejected pinned root overflow; multi-camera deduplicated demand; stale camera epochs and cuts; eviction under pressure; in-flight draw pinning; parent/child dependency protection; doubled frame completion; invalid page registration; failed-fit no-eviction safety; and 500 seeded camera-teleport operations.

## Important boundaries and honesty about performance

- `step()` synchronously marks bytes as resident. It does **not** perform real disk IO, decompress mesh data, upload storage buffers, compile shaders or allocate native GPU memory. Actual memory may include staging copies, padding, fragmentation and driver overhead; no measured VRAM pressure or stalls.
- Pages are arbitrary records, **not meshlets**, cluster indices, optimized edge-preserving simplification results or GPU draw data. No LOD screen-space error, topology cracks, alpha geometry, per-material residency or shadow passes are simulated.
- A permanent coarse root incurs real budget cost. Registering many roots may exceed capacity; the model explicitly refuses registration rather than losing the fallback. A scalable production implementation needs coarser placeholder/impostor quality budgets and shared root assets.
- A page larger than the per-tick upload budget will remain queued with its coarse fallback. Future large-page scheduling requires **chunking or multi-tick progress accounting**; this experiment never pretends that an incomplete page is drawable.
- Request queues may retain demand for pages that stay resident and do not model async cancellation/retry, checksums, generation-safe page hot reload, multi-threaded IO, scene reset or device loss. Those are next required lifecycle gates.
- The implementation is deliberately a **Python correctness model** with whole-table scans; it does not establish throughput benefits or optimal eviction choices. Fairness and thrashing avoidance need comparative synthetic traces, then hardware measurement.
- Eviction refcounts are simulated draw tickets, not actual GPU fences. Conventional Godot meshes must stay available as the default and real fallback until a native implementation proves compatible.

**Follow-on completed (2026-11-14):** [53 — async page lifecycle and LOD selector](53-async-geometry-lifecycle-and-lod-error-cpu-milestone.md) extends the original synchronous page research with separately simulated IO, decoded and upload stages, versioned cancellation/hot reload and conservative screen-error/hysteresis LOD selection (27 committed new CPU tests passed). The synchronous `geometry_residency_reference.py` in this document remains a **separate correctness model**; its older `step()` is not retroactively asynchronous.

## Next hardware-free implementation priorities

1. **Async page lifecycle simulation:** queued → reading/decoded → upload pending → resident, explicit IO/upload budgets, failed/cancelled loads and stale generation/scene completion rejection. Derive a deterministic set of camera/IO traces to measure simulated churn and fallback quality.
2. **LOD quality constraints:** attach conservative error metadata to each geometry page, test a CPU-only screen-space error estimator with near-plane/orthographic handling, enforce monotonic quality/error where parent is substituted, and model transition hysteresis.
3. **Integrate two CPU models for budget accounting:** geometry page upload plans and [51](51-bounded-immutable-staging-upload-reference.md)'s immutable transfer packets share a conceptual staging budget but must not confuse instance-table updates with actual mesh payloads.
4. **Later** (hardware available): validate the isolated compute/raster fixtures and real Godot geometric fallback. Do not re-route production meshes or advertise measured speedups based on this CPU simulation.

No proprietary Unreal code is used; work stays in the public Worlds-Engine repository.

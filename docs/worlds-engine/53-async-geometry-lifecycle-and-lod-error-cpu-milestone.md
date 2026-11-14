# 53 — Asynchronous geometry lifecycle and conservative LOD selection (CPU-only)

**Date:** 2026-11-14. **Status:** implemented, committed and CPU-tested reference models. **GPU/Godot execution: not performed.** Normal Godot mesh rendering is unchanged. Hardware tests remain deferred while the user's graphics test environment is unavailable.

This continues [31 — independent adaptive geometry](31-independent-virtual-geometry-design.md), [32 — residency and fallback](32-residency-streaming-contract.md), [51 — versioned staging](51-bounded-immutable-staging-upload-reference.md), and [52 — synchronous geometry residency reference](52-geometry-page-residency-cpu-contract.md).

## Implementation files and verification

| File | Function | Tests |
| --- | --- | --- |
| [`geometry_async_reference.py`](../../benchmarks/theory/geometry_async_reference.py) | Original CPU model of async page reads, decoded cache, uploads, hot reload, residency and frame holds | [`test_geometry_async_release.py`](../../benchmarks/theory/test_geometry_async_release.py): **13 passing cases** |
| [`geometry_lod_reference.py`](../../benchmarks/theory/geometry_lod_reference.py) | Projected error, parent-first LOD chain, residency-aware selection, temporal hysteresis | [`test_geometry_lod_reference.py`](../../benchmarks/theory/test_geometry_lod_reference.py): **14 passing cases** |

**Exactly committed tests:** 27/27 passed locally (13 + 14). **Extended development-only test run:** the new async module also passed 25 locally authored exploratory tests, so a local combined run of those 25 plus the 14 LOD tests reported **39/39**. The extended exploratory test file is **not committed**; do not treat 39 as the repository's committed test count. The four committed files were verified against the local executed bytes using **length plus FNV-1a checksums** after the final GitHub commits. No full repository checkout / Godot parser run was performed in the research container. This is correctness evidence for the CPU models, not a measured renderer speedup.

## CPU page lifecycle

`AsyncGeometry` keeps a parent-first hierarchy of `Page(name, size, parent, generation)` and an always-resident coarse root for each registered asset chain. Four independent **synthetic byte limits** bound resident geometry, CPU decoded bytes, in-flight simulated reads and simulated upload staging. Page sizes are cost-model values, not actual mesh buffer allocations.

The service exposes two simulated work issuance/completion stages:

1. **Demand:** `request(name, view, epoch, priority)` coalesces camera demand and preserves a bounded waiting-age score. `set_view_epoch` cancels that view's old requests after a cut, but does not discard still-relevant demand from another view or resident data.
2. **Issue read:** `issue_reads(per_step_bytes)` chooses only currently demanded pages/ancestors, with a preference for prerequisites of equal urgency. It returns immutable, versioned `Ticket(serial, scene_epoch, page, generation, kind, size)` objects and reserves in-flight IO bytes.
3. **Complete read:** `complete_read(ticket, success)` releases the IO reservation exactly once. A mismatched generation/epoch, cancelled camera demand or failed IO cannot publish a decoded page. Successful, still-current data is charged against the decoded-cache cap.
4. **Issue upload:** `issue_uploads(per_step_bytes)` selects decoded pages only if their parent is resident, their version is still current, and staging/per-call byte limits allow a whole transfer.
5. **Complete upload:** `complete_upload(ticket, success)` releases its staging reservation. A current successful transfer may become resident **only after** an all-or-nothing eviction plan proves the full page can fit without removing a root, an in-flight draw dependency, an ancestor required by the incoming page, or a page with a resident child.
6. **Draw retirement:** `submit(page_keys)` pins every submitted resident page **and its complete ancestor chain** until the matching `retire(frame)` acknowledgement. Late or duplicate completions fail.
7. **Hot reload and scene reset:** `hot_reload(nonroot)` invalidates a page and derived descendants only if none is referenced by a submitted frame. Old IO/upload tickets retain their byte reservations until completion but cannot install stale data. `begin_reset` freezes new work; `complete_reset` waits for every old IO, upload and draw ticket, then advances the scene epoch and reinstates pinned coarse roots.

**Important distinction:** there are **no threads, real disk jobs, decompression, driver upload commands, GPU fences or device allocations** in this model. Asynchrony means the synthetic begin/ack lifecycle can be completed in different orders under deterministic tests.

### Preventing impossible work

A source audit and additional CPU tests found a wasteful cycle: when a page is larger than a mandatory downstream cap, naive retry continually schedules read jobs despite no possible path to residency. The final model provides `blocked_reason(name)` returning `READ_LIMIT`, `DECODED_LIMIT`, `STAGING_LIMIT`, `RESIDENT_LIMIT`, or `None`, checking prerequisite pages as well as the requested page. Hard-impossible pages do **not** issue reads; coarse root fallback remains visible. Temporary contention (e.g., a page referenced by an outstanding frame) is **not** misclassified as a permanent size limit and can recover on retirement.

**Versioning/ABA:** both IO and upload tickets carry page generation and scene epoch, with monotonically advancing ticket serials. Stale completions release reservations but may never overwrite a newer page revision. Root geometry hot reload is intentionally disallowed without a full scene reset; the root is the guaranteed fallback.

### Tests and observed model fixes

The committed 13-case async suite tests: root fallback and parent-first admission, camera-cut cancellation, shared multi-camera demand, stale read/upload hot-reload completions, cancelled uploads, impossible-budget fast refusal, IO/upload failure retries, in-flight parent/child holds, transactional eviction after frame retirement, no degradation from a failed-fit load, two-phase reset draining, duplicate completion rejection, and **1,200 seeded randomized operations with independent memory/refcount invariants**. The additional uncommitted exploratory suite tested more variants including concurrent old/new generations and parent-budget limits.

## CPU LOD screen-space error model

The original `LODSelector` models a single **whole-asset LOD chain** (root → medium → finest). Each `Level` specifies conservative source error and parent identity. The constructor refuses invalid parent chains, duplicates, nonfinite error values or any finer level with a larger advertised error. It is not yet an independent region/meshlet hierarchy.

For a validated perspective camera, approximate a conservative projected error as:

```text
error_pixels = error_world * max_scale * viewport_height
               / (2 * tan(fov_y / 2) * closest_depth)
closest_depth = center_forward_distance - world_space_bound_radius
```

The model returns **infinite** estimated error for nonzero source error if the bounding sphere intersects/crosses the camera near plane. This forces best *available* detail instead of spuriously choosing coarse geometry. A zero-error representation remains exact in the proxy model.

For an orthographic camera, projected error is `error_world * max_scale * viewport_height / ortho_height`, independent of camera distance. The caller supplies an already-conservative bound radius in world/camera-space units and an appropriate maximum transform scale; these are **caller assumptions**, not properties proven by this module.

`choose(camera, budget_px, resident, previous, hysteresis)`:

- Computes the ideal **coarsest** LOD satisfying the pixel budget; if no level satisfies it, chooses the finest available design level.
- Only uses the **contiguous resident prefix** of the required parent chain. Fine data without its medium parent is ineligible.
- Returns the selected drawable page, the preferred ideal page to request, the selected estimated error, whether it is a residency fallback, whether it meets the budget, and whether the chosen representation changed.
- Adds a relative threshold band to retain the previously selected resident level during small oscillations; genuine camera moves still permit promotion or demotion.
- Falls back immediately if a previous LOD became nonresident. A feature flag or native renderer integration would be required before Godot could use this choice.

The 14 committed LOD tests cover perspective near/far bounds, missing detail and missing-parent protection, near-plane intersection, orthographic distance invariance, nonuniform scale, hysteresis/no flicker, large quality changes, eviction of previous representation, zero-error pages, invalid inputs, **700 seeded projection monotonicity comparisons**, and an end-to-end *CPU-only* LOD decision → async page request → completed detail load.

## Boundaries / not-yet-implemented behavior

- **Not measured rendering quality:** a bound on geometric displacement is not proof of real pixel equivalence, crack-free boundary stitching, correct normals/UVs, masking, alpha foliage, shader compatibility or temporal reconstruction. Source errors must eventually be derived from an independently validated meshoptimizer/offline derivation and checked against actual geometry.
- **No real asynchronous IO or GPU transfers:** completion acknowledgements are test inputs. Device-loss, true Vulkan/D3D/Metal fences, GPU relocation, thread safety, allocator fragmentation and actual bandwidth still need separate implementation.
- **Not a streaming replacement:** Godot 4.8's existing `modules/texture_streaming/` was audited in [36](36-texture-streaming-baseline-audit.md). This page model is **geometry-only** and intentionally separate from material/mip residency.
- **Model overhead remains theoretical:** `_wanted()`, `_ancestor()` and resident child checks scan Python dictionaries. Optimize and benchmark only after native data structures and workloads are established.
- **Explicit coarse cost:** many pinned roots can exhaust the residency budget. A future general-purpose engine requires shared fallback assets, placeholder tiers and bounded root management.
- **No scene integration:** neither this LOD choice nor the async page hierarchy changes the production C++ renderer. Ordinary MeshInstance3D/MultiMesh geometry must stay the default and real fallback.

## Reproduction

From the repository root, with Python 3 standard library:

```sh
python -m unittest discover -s benchmarks/theory -p 'test_geometry_async_release.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_geometry_lod_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

The final full-discovery command includes existing repository tests; it was **not** executed against a complete checkout in this session.

## Next hardware-free priorities

1. Build a **synthetic geometry workload metrics harness** to compare eviction/streaming policies across camera teleport, oscillation, shared-view demand and memory pressure; report fallback quality, churn, and byte counts as *simulation outputs*, not GPU measurements.
2. Extend the whole-asset chain to **region/cluster LOD coverage** with explicit conservative bounds, shared edge/seam compatibility rules, parent-child coverage and crack-detection tests, leveraging Godot's already-vendored MIT meshoptimizer concepts.
3. Draft the optional Godot adapter's data/ownership contract, tied to [51](51-bounded-immutable-staging-upload-reference.md), without modifying production renderer paths until hardware validation can establish real correctness and benefits.

All new code is independently authored against public-domain algorithms and open Godot/meshoptimizer concepts, not private Unreal implementation code.

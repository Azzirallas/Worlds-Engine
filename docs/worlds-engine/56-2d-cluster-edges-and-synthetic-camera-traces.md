# 56 — 2D patch coverage, exact edge signatures, and synthetic camera streaming traces

**2026-11-14. Implementation status: committed CPU-only research.** Nothing changes Godot's native scene tree, mesh drawing, shaders, texture streaming or renderer backends. The current research cannot establish GPU throughput, final pixel quality or genuinely crack-free triangulated 3D clusters.

This milestone extends [53 — asynchronous geometry streaming and LOD](53-async-geometry-lifecycle-and-lod-error-cpu-milestone.md), [54 — interval coverage](54-cluster-coverage-cpu-contract.md) and [55 — 1D seam dependency audit](55-cluster-seam-correctness-and-dependency-audit.md).

## Source files and reproducibility

| Source | Tests | What is modeled |
| --- | --- | --- |
| [`cluster_2d_reference.py`](../../benchmarks/theory/cluster_2d_reference.py) | [`test_cluster_2d_reference.py`](../../benchmarks/theory/test_cluster_2d_reference.py) — **13 tests passed** | Rectangular patch partition, mixed-LOD adjacency, conservative shared-edge vertex checks, registered stitch certificates |
| [`geometry_camera_trace.py`](../../benchmarks/theory/geometry_camera_trace.py) | [`test_geometry_camera_trace.py`](../../benchmarks/theory/test_geometry_camera_trace.py) — **10 tests passed** | Combined synthetic camera positions, projected-error LOD, async geometry page demand, two-dimensional seam-safe selections, and frame-memory telemetry |

**23/23 new tests passed** in the local Python 3.13.5 reference directory. The full **available local suite passed 96/96**; that directory contains an **additional old exploratory async test file not committed**. Therefore 96 is *not* a repo-wide CI or complete-git-checkout claim. The four new committed files were verified by exact source length and FNV-1a before upload and rechecked from GitHub afterward. There is no graphics-hardware or Godot runtime result.

From a checked-out repository root, with Python 3 standard library:

```sh
python -m unittest discover -s benchmarks/theory -p 'test_cluster_2d_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_geometry_camera_trace.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

The first two tests are new. The third discovers all tests in the actual checkout.

## A. Exact 2D patch ownership

`Patch(key, parent, x0, y0, x1, y1)` represents an **integer half-open rectangle** in a synthetic region atlas. A parent can be replaced by its child patches only when those children **tile its entire rectangle**, with no gap or overlapping interior. Parent-first registration, unique names, positive widths/heights, child containment and disjoint root interiors are checked at construction.

`Patch2DCoverage._tiled()` independently enumerates cells induced by all rectangle boundaries (coordinate compression) and requires **exactly one owner** for every cell. `verify_cover()` checks the final selected patch set without invoking the refinement algorithm. Missing coarse roots are hard errors. A selected grandchild whose intermediate parent is not resident is never drawable, preserving the ancestry invariant identified in [55](55-cluster-seam-correctness-and-dependency-audit.md).

**Request semantics:** refinement must be requested at the parent, and **all** its direct children must support complete covered resident subtrees before the parent can be replaced. The same root can show a fine southwest quadrant while retaining coarse representation in the other quadrants, without partial ownership holes. This requirement is conservative: refining one quadrant first requires resident coverage at the sibling-quadrant level.

## B. Shared-border ownership and T-junction guards

Every patch has a `Borders(left, right, bottom, top)` record. Each side is an ordered, strictly increasing sequence of integer **(edge parameter, proxy height)** vertices, including exact endpoint parameters. `flat_borders()` produces a simple level test fixture.

For any two selected rectangles sharing **positive-length** horizontal or vertical boundary, the seam checker first computes the shared subspan, then compares the exact ordered **subspan vertex signatures**:

- Equal signatures pass.
- A differing proxy height, a missing boundary split vertex (even if the underlying line is collinear), or different intermediate tessellation vertices is treated as **unsafe**, to avoid authorizing T-junctions.
- A separately registered `Stitch2D` can authorize **only its specified ordered patch pair, axis, subspan, and exact current signatures**, and only when that stitch name is explicitly resident. This models an offline-certified connector, not an actually triangulated/uploaded stitch mesh.
- Without a certified resident connector, requested refinement is suppressed, preferring the deepest affected requested ancestor. Re-selection repeats until all seams are compatible. An incompatible seam between fixed coarse roots that cannot be coarsened causes an explicit error rather than a bad draw.

The complete grid oracle and seam oracle are distinct checks; passing one does **not** automatically pass the other.

**Boundary of the result:** integer rectangular footprints plus quantized height samples prove consistency *within the synthetic representation*. They **do not** prove 3D manifold topology, triangles, watertightness, edge-normal/UV/material continuity, double-sided foliage behavior, shadow consistency, temporal stabilization, vertex deformation, floating-point raster precision, or visual quality. These require real geometry, import-time seam generation and eventual backend tests.

## C. Integrated camera + streaming workload

`CameraTrace` constructs a fixed 21-page hierarchy: one 8×8 coarse root, four 4×4 quadrants, and 16 2×2 leaf patches. The synthetic page sizes are:

| Layer | Pages | Modeled bytes/page |
| --- | ---: | ---: |
| Coarse root | 1 | 16 |
| Quadrants | 4 | 12 |
| Leaves | 16 | 9 |

The combined complete finest representation totals **208 model bytes**, while the default resident budget is **100 bytes**. This makes resource prioritization, fallback and eviction observable without any GPU.

For each simulated frame:

1. Validate view names, camera positions, depths and pixel-error budgets **before mutating** any state.
2. For each view and quadrant, use the CPU `LODSelector` projected-error estimate and hysteresis to determine the desired coarse, medium or fine level. Combine multiple views by requesting their finest applicable level.
3. Advance camera demand epochs. Request all quadrants if the root needs to split (the complete-coverage prerequisite), and request the fine children for quadrants requiring fine detail.
4. Complete due simulated **read**, **upload**, and **draw** tickets with configurable latency. The asynchronous model manages root pinning, per-page generations, camera-cancellation, dependency checks, byte caps, transactional evictions and in-flight frame reference holds.
5. Schedule new reads/uploads inside explicit per-frame and in-flight byte budgets.
6. Select the resident 2D cover and **coarsen incompatible edge transitions**. Independently verify exact coverage and seams before simulating submission of the selected pages.
7. Emit a `FrameReport` and cumulative `TraceReport` with per-frame outstanding bytes, IO/upload bytes begun, number of pages made resident, evictions, cancelled completions, seam-refinement suppression and quality levels.

**Two separate quality metrics:** `missing_quality_area` is the sum of *cell area × requested-minus-selected LOD-depth deficit*. `excess_quality_area` measures the opposite, *cell area × selected-minus-requested depth surplus*. They are **cell-depth units**, not actual pixel error, geometry triangles or area of real missing polygons. Extra medium detail can be required on far sibling quadrants simply to refine one near quadrant; this is now explicitly measured instead of being mislabeled as a defect.

## Recorded deterministic CPU-only scenario results

These values are **synthetic trace outputs from locally executed Python**, not renderer/device timings or real GPU upload bytes. They use default 100-byte resident capacity and deterministic ticket scheduling.

| Scenario | Frames | End quality deficit (cell-depth) | Read bytes issued | Upload bytes issued | Pages loaded | Evictions | Cancelled tickets |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stable near focus (healthy shared edges) | 24 | **0** | 120 | 84 | 8 | 0 | 0 |
| Same focus, one deliberately incompatible fine border | 24 | **16** | 120 | 84 | 8 | 0 | 0 |
| Far camera (coarse sufficient) | 24 | **0** | **0** | **0** | 0 | 0 | 0 |
| Four-region camera cuts every 12 frames | 160 | **32** (last frame) | 1,776 | 1,524 | 28 | 20 | 24 |

- Healthy stable near focus reaches zero quality deficit by the last frame; **excess detail is 48 cell-depth units** because splitting the root keeps the other quadrants at medium detail despite their far-camera target of coarse.
- Deliberately incompatible fine geometry still finishes loading but the edge checker **suppresses unsafe refinement in 17 of 24 frames**, yielding a persistent 16-unit deficit instead of displaying an unverified seam.
- A far camera uses the always-resident coarse root with no synthetic transfers.
- Camera cuts provoke delayed-work cancellations and **20 modeled safe evictions**. Complete root-area coverage and the byte limits continue to hold for every simulated frame.

**Interpretation:** these traces reveal policy costs and correctness obligations for a future engine. The fixed page dimensions, arbitrary per-page bytes, synthetic view distance scaling, instant local operations and no real graphics means these results **must not** be turned into FPS, milliseconds, VRAM utilization, or quality-superiority claims.

## Verification and remaining risks

The 13 2D tests cover: complete quadrants; mixed-LOD T-shaped boundaries; partial children; missing intermediate parent; malformed gap/overlap/out-of-parent rectangles; independent double-draw/hole checks; incompatible heights; collinear missing-vertex T-junction rejection; valid/stale stitch signatures; irreparable coarse-root border failures; invalid metadata; **2,000 seeded randomized resident/requested masks**.

The 10 trace tests cover: eventual stable close-view quality; zero-work far camera; persistent seam defect fallback; identical shared multi-camera demand with no duplicate work; **250 seeded camera teleports**, **160 deterministic oscillation frames**, strict per-frame byte limits, invalid camera fail-closed behavior, 21-page fixture checks and reset completion draining.

**Known unfinished areas:**
- A region hierarchy currently models a simple forest of rectangular ownership, not arbitrary triangle/meshlet surface topology or a shared-resource DAG.
- CPU `AsyncGeometry` completes synthetic tickets but does not run threads, IO, decompression or GPU fences.
- Workload counters are model quantities, and decoded/issued transfer bytes are not device allocation/real PCIe throughput.
- Root splitting may force **excess sibling detail**. A better hierarchy/independent patch coverage layout could reduce this overhead; compare against ordinary meshoptimizer LOD and conventional regional MultiMesh later.
- The seam checker is strict: equivalent geometry with extra collinear vertices will coarsen unless a trustworthy stitch is built and validated. This trades some quality for correctness.
- The stitch certificate model does not verify actual stitch triangle winding, shape, material data or edge rasterization.
- Input fixtures are tiny; the Python full pairwise edge matching/coordinate compression complexity is inappropriate as a native per-frame hot path.

## Next hardware-free implementation work

1. **Instrument and compare different ownership topologies:** one global coarse root versus independent regional coarse roots with compatible edge metadata, quantifying overspecified sibling detail and persistent fallback quality.
2. Develop offline **shared-border source geometry validation**, including oriented edge ownership, 3D sampled positions, crack/overlap raster or watertightness checks using actual triangles and original CPU-only math.
3. Define the serialization/ABI and task ownership for derived Godot `ImporterMesh` + vendored meshoptimizer clusters. Use existing permissively licensed functionality, not new bespoke simplification algorithms.
4. Retain the conventional renderer as a proven fallback. Actual Godot/GPU acceptance and performance measurements remain later gates.

All new source is independently authored and uses no proprietary Unreal code.

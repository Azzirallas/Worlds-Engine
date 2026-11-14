# 55 — Cluster dependency audit and seam-aware refinement (CPU only)

**Reviewed and implemented:** 2026-11-14. **Scope:** the experimental Python models under `benchmarks/theory`. Production Godot renderer remains unchanged; no graphics device, actual mesh, 3D stitch triangulation, shader or editor was executed.

## Review outcome

The previous [54 — cluster coverage reference](54-cluster-coverage-cpu-contract.md) proved integer-interval coverage but had not been executed. Its **10 committed tests now passed locally**. Review then exposed a real consistency failure: a fully covered set of *grandchildren* could be selected even when their **intermediate parent** page was not resident. That would violate the required ancestor-chain dependency used by the asynchronous page model in [53](53-async-geometry-lifecycle-and-lod-error-cpu-milestone.md).

Fixed `ClusterCoverage.select()`: a nonresident node is not traversable, even when its descendants happen to be resident. With the new `test_missing_intermediate_parent_disallows_grandchildren` regression, the coverage test suite now passes **11/11**.

## Seam-aware CPU prototype

New implementation: [`cluster_seam_reference.py`](../../benchmarks/theory/cluster_seam_reference.py). New tests: [`test_cluster_seam_reference.py`](../../benchmarks/theory/test_cluster_seam_reference.py) (**10/10 passing locally**, including 2,000 seeded random residency/quality selection cases).

The new seam layer composes the exact interval coverage tree with an original **ordered quantized boundary-profile** convention. Every region supplies a left/right ordered sequence of at least two distinct integer coordinate samples (conceptual shared-edge polyline). For two adjacent selected regions, the right edge of the left region must exactly equal the left edge of the right region. There is intentionally **no float epsilon** or implicit tolerance.

Selection policy:

1. Ask `ClusterCoverage` for a complete resident-cover selection (with the fixed parent-residency invariant).
2. Sort selected clusters by interval and compare both sides of each adjoining boundary.
3. If profiles match, the synthetic seam is compatible.
4. Otherwise, a **registered stitch** may make this particular ordered cluster pair eligible only when it is explicitly marked resident and its recorded left/right profiles match **both current profiles** exactly. A stale stitch for an older edge cannot authorize the seam.
5. If no valid stitch is resident, **remove one requested refinement** from the mismatching edge, preferring the deepest requested ancestor; retry selection. Thus a small incompatible child pair normally coarsens its affected branch first, rather than discarding every high-detail region.
6. If all possible coarsening still leaves an incompatible boundary **between coarse roots**, fail closed instead of drawing a known incompatible seam.

The result reports the selected clusters, removed refinement requests and stitch IDs used. Different branches can retain different detail levels. No actual geometry is uploaded or drawn.

### What the tests verify

- Previous ten exact-cover tests, now executed, plus the missing-intermediate-parent regression.
- Refusal of an incompatible boundary despite mathematically complete region intervals.
- Correct mixed-LOD refinement when edge profiles match.
- Explicit, resident matching stitch allows precisely its certified boundary.
- Stale profile signatures, unknown stitch IDs or invalid edge metadata cannot authorize unsupported transitions.
- A deep sibling mismatch can coarsen one branch while preserving safe detail elsewhere.
- Two neighboring coarse roots with irreparable borders fail closed.
- **2,000 seeded randomized** resident/requested masks always produce a disjoint, complete covered selection with no reported unsafe seams and selected pages belonging to the supplied resident set.

## CPU execution and source provenance

All tests were executed in the research container with Python 3. The newly reconstructed [54] file and test match the GitHub versions reviewed before edits. New code was first created locally and tested, then committed with exact expected length and FNV-1a source hashes.

```sh
python -m unittest discover -s benchmarks/theory -p 'test_cluster_coverage_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_cluster_seam_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_*.py' -v
```

**Results:** 11/11 amended coverage tests; 10/10 new seam tests; **73/73 tests across the available local directory**, including previous async and LOD suites. The 73-test local result is **not a complete GitHub repository checkout/CI pass** and includes uncommitted exploratory async tests from prior development. Source commits for this milestone are the fixed original coverage model and tests, plus the new seam module and tests.

## Limits: the seam rule is intentionally not a crack-free mesh proof

- Integer interval coverage is a **logical region-ownership surrogate**, not actual triangle coverage or 3D culling correctness.
- Quantized ordered boundary samples are **reference metadata**, not mesh geometry. Matching those samples does not guarantee triangle topology, normals, UVs, material transitions, tessellation edge parity or pixel-exact crack-free rendering.
- A `Stitch` is a **conceptual certificate** supplied by a trusted offline builder. This model validates identity and residency, but does not build, geometrically validate, upload or draw any connecting mesh. Naming a stitch does not itself establish physical crack-free coverage.
- The seam graph only considers adjacency of half-open **one-dimensional** region intervals. Real surface partitions require multi-edge adjacency, UV chart seams, material boundaries, manifold/non-manifold edge cases, and shared-border ownership.
- Coarsening is deterministic and safety-first, **not globally quality-optimal**. A later candidate-cost or dynamic-programming selector may retain more fine detail under the same constraints.
- Nothing establishes actual GPU throughput, memory footprint or runtime image quality.

**Follow-on implementation completed (2026-11-14):** [56 — 2D patch coverage and camera traces](56-2d-cluster-edges-and-synthetic-camera-traces.md) replaces the 1D ownership proxy with rectangular region tiling and horizontal/vertical shared edge checks, plus deterministic integrated async page/LOD/seam workload tests (**23 new passing CPU tests**). The original 1D model remains a separate independent correctness oracle; real 3D triangulation and runtime graphics validation are still pending.

## Next hardware-free steps

1. Add a **2D patch/edge adjacency reference**, with explicit edge ownership and deterministic shared-vertex compatibility, before implementing a native cluster renderer.
2. Combine synthetic async residency with cluster choice in camera traversal traces; track fallback area, failed requests, seam-induced coarsening, modeled resident bytes and eviction churn. Use measured **model outputs**, not hardware speedup claims.
3. Research offline meshoptimizer cluster/LOD derivation interfaces already present in Godot; define independently computed conservative error and border constraints. Avoid making a second meshoptimizer implementation.
4. Only once hardware is available, test exact feature flags and proper Godot mesh/material/shadow/rendering compatibility, not just colored synthetic triangles.

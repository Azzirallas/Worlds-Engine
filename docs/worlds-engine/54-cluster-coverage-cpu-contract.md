# 54 — Exact cluster coverage and all-or-nothing refinement (CPU reference)

**2026-11-14. Status:** two new source files committed; **not executed in Godot or on GPU**. The Python test suite is supplied for reproduction but has **not been executed in this turn**. Native renderer remains unchanged.

## Why this is the next constraint

The previous [53](53-async-geometry-lifecycle-and-lod-error-cpu-milestone.md) model chooses whole-asset LOD and models asynchronous page residency. Virtual geometry needs finer independent regions. If a parent is replaced by only some of its children, missing children produce holes; if a parent and its children draw together, the image may double-shade or z-fight. The first acceptance criterion is **exact spatial coverage** independent of how quickly pages load.

## New files

- [`benchmarks/theory/cluster_coverage_reference.py`](../../benchmarks/theory/cluster_coverage_reference.py): `Cluster(key, parent, start, end)` and `ClusterCoverage`.
- [`benchmarks/theory/test_cluster_coverage_reference.py`](../../benchmarks/theory/test_cluster_coverage_reference.py): ten deterministic unit tests including **2,000 seeded random resident/requested sets**. These tests are **committed, not yet run**.

This is an original synthetic interval model, not a meshlet builder, mesh simplifier or Godot implementation. Integer half-open intervals are an exact **proxy for region ownership**, not geometric triangle edges. Actual 2D/3D geometry requires validated coverage IDs or an equivalent spatial ownership proof.

## Contract

1. Nodes are declared parent-first, have unique IDs and positive integer intervals.
2. Each internal node's children partition its exact interval with **no gap and no overlap**. Disjoint root intervals are allowed; overlapping roots are rejected.
3. A coarse root must be resident for every asset. Missing roots fail closed.
4. A parent is refined only if refinement is requested **and every child subtree can supply a complete resident cover**. Otherwise keep that resident parent; never publish a partial split.
5. Recursive selection can mix quality levels in different branches. The returned list contains no overlapping parent/descendant pairs.
6. An independent interval-union oracle, `verify_cover`, checks selected output against every root interval. The oracle intentionally does not reuse the recursive selection implementation.
7. Selection uses residency sets as inputs and does **not** allocate, upload or evict pages. Connect it to [53](53-async-geometry-lifecycle-and-lod-error-cpu-milestone.md) only after both models pass their own invariants.

## Important limitations and risks

- **Crack-free geometry is not proved.** Two spatially adjacent child clusters can each cover their conceptual domain and still produce cracks due to differing vertex placement, floating-point precision or unmatched LOD edges. Actual meshlet/cluster boundaries need shared-edge IDs, border locking, skirts, stitch meshes or another independently verified strategy.
- **Coverage does not establish visibility.** Occlusion/frustum decisions and camera layers are separate from the page residency contract. Culling may discard an entire covered region only with a conservative visibility proof.
- **Parent-first chain is not yet a DAG.** Shared dependencies, instancing, page deduplication, material segmentation, transparent ordering, deforming meshes and skinned geometry require more extensive ownership contracts.
- **No performance claim.** This CPU model uses Python sets and recursive traversal and is designed to catch correctness failures, not optimize draw submission.

## Reproduce

```sh
python -m unittest discover -s benchmarks/theory -p 'test_cluster_coverage_reference.py' -v
```

## Next work

1. Execute the committed tests in a complete repository checkout and resolve any failures.
2. Add a seam compatibility graph that treats a boundary as safe only if its adjacent regions agree on shared-edge positions or a validated stitch is resident.
3. Compose residency, screen-error selection and exact coverage into one deterministic camera workload; record fallback frequency, residency churn and simulated bytes.
4. Keep conventional Godot MeshInstance3D/MultiMesh rendering as the stable default until native/GPU validation is possible.

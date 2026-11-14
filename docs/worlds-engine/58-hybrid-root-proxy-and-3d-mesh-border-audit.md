# 58 — Hybrid coarse proxy and real-position mesh border validation

**Date:** 2026-11-14. **Milestone:** two new CPU reference files, a compiled native C++ border analyzer and regression suite, and an expanded opt-in Godot scripting wrapper. **No native Godot editor/SCons build and no GPU test were performed.** All measured bytes and draw submissions in the policy comparison are synthetic model units; do not infer real VRAM, FPS, triangles or driver cost.

This milestone follows [57 — regional vs global roots and first native topology audit](57-regional-geometry-roots-and-native-mesh-edge-audit.md), [56 — 2D patch and streaming traces](56-2d-cluster-edges-and-synthetic-camera-traces.md), and [31 — virtualized geometry plans](31-independent-virtual-geometry-design.md).

## A. Implemented hybrid policy

New reference source: [`benchmarks/theory/hybrid_topology_reference.py`](../../benchmarks/theory/hybrid_topology_reference.py). Regression suite: [`test_hybrid_topology_reference.py`](../../benchmarks/theory/test_hybrid_topology_reference.py).

The original [`root_topology_reference.py`](../../benchmarks/theory/root_topology_reference.py) compared an all-world coarse root requiring all regional coarse children to load before splitting, versus a forest of independently streamable region roots whose complete coarse representation is already resident. The **new independent `HybridTopology`** starts with those same regional pinned roots and optionally streams a separate **far-field aggregate proxy**:

- **Near:** regional pages and detailed pages remain independently streamable; unrelated regional pages do not need to be uploaded again before choosing nearby detail.
- **Far:** if an aggregate proxy is resident, it stands in for the complete 4×4 region group in the **synthetic draw-submission model**. If missing, the resident regional roots still cover everything (16 nominal regional submissions), so visibility never depends on successfully loading the proxy.
- **Admission:** the aggregate's real model-byte cost is charged against the resident budget. It may transactionally evict unneeded, unreferenced fine pages; it must not force an unsuccessful partial eviction. Fine pages can evict an unreferenced proxy if capacity requires it, never the pinned region roots.
- **Frame safety:** the aggregate is pinned by each outstanding far frame. When a nearby view needs memory, it waits for those submissions to retire before evicting aggregate memory. A pending proxy upload is cancelled after a camera cut to a near-detail request.
- **Byte limits:** the optional proxy shares the existing per-tick upload limit and can never be partly published. If the budget cannot hold even the regional coarse representation plus the proxy, only the regional fallback is used.
- **Verification:** `verify()` independently recomputes pinned roots + fine pages + optional proxy residency, checks fine-frame reference counts and aggregate frame reference tickets. `compare_three()` replays identical camera focus traces through global, regional and hybrid alternatives.

This is **policy research**, not a built proxy mesh, GPU command allocator, or rendering-quality algorithm. Proper hybrid implementation must add derived mesh provenance, stable grouping IDs, world transforms, material equivalence, and device fence ownership before the engine adopts it.

### Executed comparison and correctness

**23/23 tests passed locally** across 11 prior topology tests and **12 new hybrid tests**; the new cases include **1,200 seeded random camera changes**, proxy capacity refusal, delayed upload completion, near/far transition, cancelled transfer, and a previous far frame preventing unsafe aggregate eviction. Tests use Python 3 standard library only:

```sh
python -m unittest discover -s benchmarks/theory -p 'test_root_topology_reference.py' -v
python -m unittest discover -s benchmarks/theory -p 'test_hybrid_topology_reference.py' -v
```

From the locally executed CPU reference, using a 4×4 grid, identical 32-byte coarse baseline, 12-byte individual fine pages, 10-byte optional aggregate and an 88-byte resident cap:

| Synthetic scenario | Global | Regional | Hybrid |
| --- | ---: | ---: | ---: |
| 12 far frames: final coarse submissions/frame | **1** | 16 | **1** |
| 12 far frames: total bytes uploaded | **0** | **0** | 10 |
| 12 near-focus frames: total bytes uploaded | 44 | **12** | **12** |
| 12 near-focus frames: remaining resident bytes | 76 | **44** | **44** |
| Far12 → near12 → far12: final coarse submissions/frame | **1** | 16 | **1** |
| Far12 → near12 → far12: total uploads | 44 | **12** | 22 |
| Far12 → near12 → far12: model final resident bytes | 76 | **44** | 54 |
| Far12 → near12 → far12: cumulative requested fine-page deficit frames | 5 | **2** | **2** |

The hybrid keeps the nearby selective-streaming advantage while recovering a single far-field proxy submission after its load latency. The extra ten proxy bytes are **not free**; in the mixed trace the final hybrid memory is 54, above the regional layout's 44. Unbatched synthetic draw submissions are not real Godot draw calls. Regional roots can be instanced/batched/cull-filtered; global simplified assets could also compress differently. These numbers establish *only* behavior of the reference model.

## B. Native exact-position and 3D border diagnostics

Added native source to [`modules/worlds_geometry/`](../../modules/worlds_geometry/):

- [`mesh_border_audit.h`](../../modules/worlds_geometry/mesh_border_audit.h) and [`mesh_border_audit.cpp`](../../modules/worlds_geometry/mesh_border_audit.cpp): independent C++17 routines sharing the existing `Point` and topology `Report` types.
- [`test_mesh_border_audit.cpp`](../../benchmarks/native_geometry/test_mesh_border_audit.cpp): **13 explicit native test scenarios** for duplicated UV seam vertices, true open edges, oriented tetrahedron, invalid inputs, reversed boundaries, missing split vertices, opposite/same winding, and configurable 3D gap tolerances.
- Updated `worlds_mesh_topology.h/.cpp` and `doc_classes/WorldsMeshTopology.xml`: extend the opt-in Godot `RefCounted` diagnostic class with two new read-only methods. The existing `analyze_indexed_surface()` remains available.

### Position-welded connectivity

`analyze_position_topology(vertices, indices)` computes **two independent topology analyses**: raw index identity and a second index buffer remapped through **exact XYZ equality**. A duplicated vertex with an identical 3D position may represent a UV/material/normal seam rather than an open geometric edge. The result reports `indexed`, `welded`, `unique_positions`, `coincident_vertex_duplicates`, and `indexed_open_edges_resolved`.

One deterministic test duplicates **all four tetrahedron faces' indexed vertices**, emulating UV splits. Raw index topology reports **12 open edges**; exact-position-welded topology reports **0 open edges** and passes its closed-oriented two-manifold proxy. In contrast, a truly open single triangle still reports **3 open edges** after welding.

**Critical limits:** exact XYZ equality does not weld nearly coincident vertices. The routine **does not alter source geometry**, does not account for UV or material continuity and cannot prove that a self-intersecting or overlapping mesh renders watertight. The name `indexed_open_edges_resolved` is a diagnostic delta, not a license to automatically weld a production mesh. Nonfinite positions and malformed indices are rejected by the underlying auditor.

### Ordered 3D boundary comparisons

`compare_border_samples(a, b, tolerance)` compares real 3D `(x,y,z)` sample positions of **two caller-supplied, ordered edge polylines**. Adjacent triangles are expected to traverse their common edge in opposite directions. It requires at least two finite nondegenerate samples per side, exactly corresponding points in reverse order, and reports `geometry_match`, `opposite_direction`, `same_direction`, `max_opposing_gap`, `samples_a`, `samples_b` and `t_junction_risk`. A missing intermediate split vertex is considered unsafe even when the endpoints lie on the same line. An explicit nonnegative distance tolerance may be provided, but a tolerant match is **not** crack-free proof.

These routines are diagnostic geometry checks, not a triangle importer or actual connecting stitch builder. A future import pipeline must identify boundary polylines from real mesh triangles, handle segmentation and materials, and validate stitch triangles rather than trusting arbitrary caller-supplied samples.

### Compiled validation and Godot build status

The core and its regression fixture were compiled using local `g++` 14.2 with strict warnings and then compiled/executed again with the undefined-behavior sanitizer:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
    modules/worlds_geometry/mesh_edge_audit.cpp \
    modules/worlds_geometry/mesh_border_audit.cpp \
    benchmarks/native_geometry/test_mesh_border_audit.cpp \
    -o /tmp/worlds_mesh_border_test
/tmp/worlds_mesh_border_test
```

**Local result:** normal and UBSan binaries exited successfully; 13 native fixture scenarios passed. The script-facing `WorldsMeshTopology` interface has new `analyze_position_surface(vertices, indices)` and `compare_border_samples(border_a, border_b, tolerance = 0.0)` methods. The XML documentation parsed successfully using the Python standard-library XML parser. The Godot wrapper source and module class binding **have not been compiled inside Godot**, so script API and engine compatibility remain a mandatory separate acceptance gate. The module remains disabled by default; the normal Godot build remains unaffected.

Build flag for an eventual full engine test:

```sh
scons platform=linuxbsd target=editor module_worlds_geometry_enabled=yes
```

## Next engineering gates

1. **Native Godot build verification** for the opt-in module, including its `ClassDB` method signatures and a GDScript/editor smoke test when a build is available.
2. **Real imported mesh analysis:** inspect Godot's current `ImporterMesh` / `ArrayMesh` and `SurfaceTool` source, then build an indexed-surface extraction path with explicit geometry/material/source provenance.
3. **Hybrid grouping policy:** establish bounds, proxy validity, image-error criteria and group IDs. Avoid double-shading when replacing regional draw submissions with aggregate proxies, and don't assume all distant proxies are equal quality.
4. **True seam testing:** compare actual spatial triangles across region edges, detect near-coincident coordinates and self-intersections without accidentally merging distinct surfaces. Model stitching only with a validated geometrical artifact.
5. GPU device upload/fence and raster acceptance remain untested; **never claim native performance superiority based on the CPU model**.

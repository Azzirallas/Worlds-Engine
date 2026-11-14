# 57 — Global versus regional root policies and first native geometry audit

**Date:** 2026-11-14. **State:** CPU research and standalone C++ native-core test implemented; opt-in Godot module committed but **not built inside Godot**. The user has authorized direct modification of the Godot fork; no production rendering path was removed or replaced without an executable graphics baseline.

This milestone follows [56 — 2D patch ownership and camera streaming traces](56-2d-cluster-edges-and-synthetic-camera-traces.md), the [phase-1 plan](35-phase-1-validation-and-next-actions.md), and [31 — independent virtual geometry design](31-independent-virtual-geometry-design.md). It focuses on two concrete design questions: how many coarse roots to preserve, and how to move from abstract integer edge signatures toward **real triangle topology analysis**.

## A. Global-root versus regional-root comparison

New files:
- [`root_topology_reference.py`](../../benchmarks/theory/root_topology_reference.py)
- [`test_root_topology_reference.py`](../../benchmarks/theory/test_root_topology_reference.py)

The model replays **identical camera demands** through two original scheduling policies:

- **Global:** one always-resident combined coarse asset; before replacing it by finer regional coverage, *all* regional coarse descendants must load. Fine pages only become drawable after that complete coverage set is present. A far camera can keep using one global-root submission even when children remain cached.
- **Regional:** each region owns one pinned coarse representation from the beginning. Fine pages can replace an independent region without first loading every unrelated sibling. A far scene starts with one coarse draw per region in this deliberately unbatched model.

The four-by-four experiment assigns an identical **32 model bytes** of base-coarse geometry to either layout: one 32-byte global root or sixteen 2-byte regional roots. Each optional fine page costs 12 additional model bytes. The two layouts are **assumed** to have equal coarse visual quality and content; no real mesh equality or compression rate was checked. Both use a shared modeled per-frame upload limit of 24 bytes, two-tick synthetic transfer latency, simulated draw-frame holds and safe eviction. The numbers are intentionally synthetic and not a GPU bandwidth model.

**11/11 newly added Python tests passed locally**, including 1,200 seeded changes of up to three camera regions per frame, independent recomputation of resident bytes and frame-reference holds, simultaneous camera demands, budget exhaustion, safe eviction, invalid input, and the return-to-far view optimization.

### Deterministic model results

| 4×4 scene and equal 32-byte base | Global root | Regional roots |
| --- | ---: | ---: |
| Far-view coarse draw submissions per frame | **1** | 16 |
| One nearby desired region: total uploads at 88-byte cap | 44 | **12** |
| Resident bytes once that region reaches fine detail | 76 | **44** |
| Final fine detail possible at 70-byte cap | **No** | **Yes** |
| Cumulative requested-fine deficits across 24 stable focus frames at 88-byte cap | 5 | **2** |
| Cumulative requested-fine deficits across 160 moving-focus frames at 88-byte cap | 35 | **32** |
| Total uploads issued across 160 moving-focus frames at 88-byte cap | 224 | **192** |
| Safe fine evictions across that 160-frame trace at 88-byte cap | 14 | **12** |

All bytes, draws, deficits and frame steps in this table are **synthetic model outputs**, not Godot draws, PCIe transfers, VRAM measurements, time in milliseconds, or FPS. In actual engines, regional roots can be **batched, instanced, culled by visibility**, or merged into proxy meshes; actual far-view draw overhead may therefore be far less than sixteen native draw calls. Geometry preprocessing may also give a global coarse proxy significantly different compression and image quality than sixteen regional proxies. The model does **not** prove that the regional layout is universally faster.

**Architecture decision for investigation:** prioritize a **hybrid forest**: regional roots suitable for independent fine streaming, plus an optional distant aggregated proxy that can replace an entire visible group when sufficient quality. Importantly, do not make all regional roots dependent on loading an additional global parent before refinement. This combines the spatial independence of regional fine pages with the potential far-field submission savings of an aggregated asset, at the cost of additional proxy geometry and transition rules. The hybrid is a design direction, **not yet implemented or benchmarked**.

### Known model shortcuts

- Immutable synthetic page sizes and an equal-quality assumption; no mesh simplification/texture/geometry codec.
- Simplified whole-page upload acknowledgements and no real asynchronous threads, decoded geometry, staging RAM, GPU fences or backend memory pressure.
- Pinned roots may preserve stale coarse detail after a camera cut; no optimal eviction/search policy, no cluster-level quality error metric.
- Only selected fine pages hold simulated frame references; coarse roots stay permanently pinned. A later device allocation implementation needs physical fence-aware lifetime tracking for every submitted buffer.
- Draw submission count is a **structural primitive**, not real CPU/GPU driver work; the model does not attempt Godot's MultiMesh batching or GPU-driven culling.

## B. First native implementation: opt-in Worlds geometry module

New source under [`modules/worlds_geometry/`](../../modules/worlds_geometry/):

| File | Purpose |
| --- | --- |
| [`mesh_edge_audit.h`](../../modules/worlds_geometry/mesh_edge_audit.h), [`.cpp`](../../modules/worlds_geometry/mesh_edge_audit.cpp) | Original **C++17, GPU-free indexed-triangle topology auditor**, compilable independently of Godot |
| `worlds_mesh_topology.h/.cpp` | Godot `RefCounted` class `WorldsMeshTopology`, converting PackedVector3/Int32Array to native inputs, returning a diagnostic Dictionary |
| `register_types.h/.cpp` | Registers the diagnostic class at the Scene module level |
| `config.py`, `SCsub` | Native module discovery, source build; **`is_enabled() == False`** keeps it **disabled by default** |
| `doc_classes/WorldsMeshTopology.xml` | Optional script API class description |

**Source-confirmed Godot integration fact:** the checked fork's `SConstruct` reads each module's `config.is_enabled()` to determine its normal build default, and includes the module only after the corresponding `module_<name>_enabled` flag and `can_build` check. The existing `modules/meshoptimizer/` already links the MIT meshoptimizer library to `SurfaceTool`—we should reuse its mature functions for actual meshlet partitioning and simplification rather than invent new algorithms.

### Native algorithm

The standalone `worlds_geometry::analyze_indexed_triangles` routine takes double XYZ positions and signed 32-bit triangle index triplets. It:

1. Checks nonfinite vertex coordinates, incomplete index triples, negative/out-of-range indices, repeated-index/zero-area triangles and duplicate index-triangle faces.
2. For every valid indexed triangle, counts undirected edges using the sorted **index identity** and records the direction each face traverses that edge.
3. Reports **open edges** (one incident triangle), **non-manifold edges** (more than two), and **orientation conflicts** (two triangles traverse a shared edge in the same direction), plus triangle and vertex totals.
4. Flags the indexed surface as a closed, consistently oriented two-manifold **only within those checks**. Closed disconnected components, self-intersection and coincident-but-distinct vertices are not fully diagnosed.

There is no epsilon-based welding, edge sampling or imported mesh material processing yet. Real mesh index buffers often duplicate vertices at UV, normal or material boundaries; such seams may appear as open edges even when the rendered object looks closed. The analyzer cannot certify literal watertightness without a subsequent geometric equivalence and surface-intersection pass.

### Executed validation

[Standalone native tests](../../benchmarks/native_geometry/README.md) compile **the exact native core** with the available Linux `g++`:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
    -Imodules modules/worlds_geometry/mesh_edge_audit.cpp \
    benchmarks/native_geometry/test_mesh_edge_audit.cpp \
    -o /tmp/worlds_mesh_audit_test
/tmp/worlds_mesh_audit_test
```

**Result:** compiler exited normally with strict warnings enabled and the executable passed **ten explicit assert-based fixtures**: oriented tetrahedron (closed), one open triangle, a reversed tetrahedron face, three triangles sharing an edge, invalid negative/out-of-range indices, trailing incomplete triplet, collinear triangle, duplicate triangle in opposite winding, nonfinite vertex, and empty mesh input.

**Not tested:** actual Godot/SCons C++ integration, the registered `WorldsMeshTopology` GDScript method, the Godot XML document-generation step, Windows/Linux engine builds and all GPU render paths. The module's normal default is disabled to avoid affecting working engine builds. To opt into the experimental module in an appropriate environment:

```sh
scons platform=linuxbsd target=editor module_worlds_geometry_enabled=yes
```

This is **a native engine source addition**, but not a claim that the Godot engine is currently able to compile or execute it.

## C. Next actionable engineering tasks

1. **Native build gate:** compile the opt-in module in Godot when a suitable build environment is available; fix ClassDB signatures, module registration, XML validity and platform variants if needed. The regular disabled-by-default build should remain unaffected.
2. **Geometric edge matching:** extend the native auditor with separately reported exact/quantized *position-based* border equivalence and seams, without confusing UV duplication with actual gaps; add triangle intersection/watertightness checking before using a 'sealed' label in authoring tools.
3. **Hybrid coarse proxy model:** compare regional root groups plus aggregate distant impostor/proxy, accounting for **duplicate proxy residency bytes** and safe transition ownership, not just modeled draw submissions.
4. **Importer path audit:** inspect existing `ImporterMesh`, `ArrayMesh` and `SurfaceTool` contracts in the checked Godot fork. Keep meshoptimizer integration and authored mesh provenance intact; no borrowed Unreal source code.
5. Continue CPU correctness tests without requiring GPU hardware. Real runtime renderer/shadow/material and performance validation remains a later adoption gate.

**Maintenance:** a future AI session should read [28 — AI handoff](28-ai-research-handoff-and-implementation-map.md), this document, and [56](56-2d-cluster-edges-and-synthetic-camera-traces.md) before changing the adaptive geometry pipeline.

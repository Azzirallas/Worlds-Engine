# 61 — Automatic mesh boundary extraction and derived cluster cache contract

**Date: 2026-11-14.** **State:** portable C++17 extraction code and CPU tests are implemented. Persistent geometry cache is a design proposal only. Godot SCons build, real imported glTF, real-vendor meshoptimizer linkage, GPU rendering and benchmarks have NOT been executed.

This follows [58 — 3D border comparison](58-hybrid-root-proxy-and-3d-mesh-border-audit.md), [59 — imported surface diagnostics](59-imported-mesh-readonly-topology-adapter.md), and [60 — meshlet certification](60-offline-meshoptimizer-meshlet-validation.md). The new code extracts *ordered 3D boundary chains from indexed triangle faces*, without modifying the original mesh, materials or standard Godot renderer.

## Native sources and API

- `modules/worlds_geometry/mesh_boundary_extract.h/.cpp`: `extract_mesh_boundaries(positions, indices)` returns `BoundaryExtraction` containing status, canonical local-space positions, ordered `BoundaryChain` records, coincident vertex count, internal edge count and border edge count.
- `benchmarks/native_geometry/test_mesh_boundary_extract.cpp`: standalone C++17 tests exercising the exact extractor and existing edge/border auditor.

Closed chains carry `closed=true` and do not repeat the starting vertex at the end. Chain orientation follows source triangle winding. Canonical vertex IDs are assigned by first occurrence of exact XYZ positions; they are **not stable identifiers across reimports**.

## Conservative algorithm

1. Fail on nonfinite points, invalid index streams, zero-area faces, duplicate source triangles and unrepresentable vertex counts.
2. Build an **exact-coordinate diagnostic weld** (UV/normal split duplicates share a position) without rewriting the mesh. Recheck topology after welding; refuse degenerate faces, duplicates, nonmanifold edges and inconsistent winding.
3. Count oriented edge incidences. One face yields a boundary; two oppositely oriented faces yield an internal edge. Reject more than two incidences.
4. Require no more than one incoming and outgoing boundary edge at each canonical vertex. Reject branch points/pinched surfaces, rather than guessing which loop to follow.
5. Walk all unvisited directed edges, open paths first and closed loops second, and verify every border edge was visited exactly once.

`status == OK` means only **local indexed topology** was accepted. Exact welding can merge intentionally coincident independent layers, so it is diagnostic only. No implication of watertight real-world seams, self-intersection freedom, same material appearance, equivalent LODs or renderer approval. Converting to global space requires explicit transforms and handedness; naive epsilon welding is unsafe.

## Reproduce portable tests

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
  modules/worlds_geometry/mesh_edge_audit.cpp \
  modules/worlds_geometry/mesh_border_audit.cpp \
  modules/worlds_geometry/mesh_boundary_extract.cpp \
  benchmarks/native_geometry/test_mesh_boundary_extract.cpp \
  -o /tmp/worlds_boundary_extract_test
/tmp/worlds_boundary_extract_test
```

**Observed:** GCC C++17 strict-warning compile/run passed, as did Clang with AddressSanitizer and UndefinedBehaviorSanitizer. The three new files were SHA-matched to their tested local versions. Cases cover a triangle, square, UV-split quad, tetrahedron, two disconnected surfaces, a hole/annulus, reversed winding, duplicate/degenerate/nonfinite/out-of-range inputs, triple-incidence edges, point-touch branch rejection, 1×1 through 16×16 grids and 400 seeded triangle reorder/rotation cases. A shared region edge was reconstructed from the extractor's returned loops, then checked against the existing border comparator. These tests do not validate real Godot import, graphics APIs or FPS.

## Proposed persistent derived cluster cache — not yet implemented

Build a separately stored, versioned, immutable `WGC1` asset **per imported surface and LOD**. Required contracts:

| Part | Planned contents and safety checks |
| --- | --- |
| Container | Magic/version/endianness; bounded little-endian field widths; validated lengths, offsets, hashes/checksums; reject unknown required features |
| Provenance | Source asset identity/content hash, generator and import-settings version/hash, surface/material slot and LOD identifier |
| Cluster payload | Meshlet vertex/global references, packed local oriented triangles, finite bounds, source mesh references, optional proxy/parent dependencies |
| Seam payload | Oriented boundary vertices and coordinate space, parent-child coverage, explicit seam/LOD validity state |
| Integrity | Immutable temp write then atomic publish; safe overflow checks and size caps; never trust a serialized verification flag without decoding and checking |
| Fallback | If outdated, invalid, unavailable or over budget, retain normal Godot source surfaces/LOD and disable experimental fast path |

The on-disk byte layout, compression, checksum choice and version ABI are **not yet finalized or coded**. Preserve Godot's original source mesh/material pipeline; cached geometry is disposable derived data.

## Next acceptance gates

1. Full opt-in Godot build against *real* vendored meshoptimizer; run existing headless mesh-source and meshlet smoke scripts.
2. Add a read-only `WorldsMeshTopology` wrapper around extracted boundaries with import/runtime surface+LOD metadata, and verify real glTF/ArrayMesh fixtures.
3. Transform borders into common world coordinates, segment shared region borders, test T-junctions/material continuity and prove LOD seam correctness before authorizing any rendering.
4. Specify `WGC1` byte layout, build robust decoder/round-trip/cache invalidation tests, then combine with certified meshlet data.
5. Only after asset correctness, attempt opt-in GPU cluster rendering and genuine hardware comparisons.

No Unreal source was copied. This is independent CPU research, not a validated renderer.

**Follow-on:** [62 — portable WGC1 cache codec](62-portable-meshlet-cache-codec.md) now serializes/validates meshlet ranges, references, triangles and bounds with explicit source/settings provenance; it does **not yet serialize boundary chains** or supply a Godot import/disk cache manager.

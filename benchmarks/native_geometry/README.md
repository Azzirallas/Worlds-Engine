# Standalone native geometry topology audit

This is the **first compiled native-C++ research component** for Worlds Engine. It validates topology of indexed triangle surfaces without launching Godot, accessing graphics hardware, changing imported assets or touching the production renderer.

## Offline surface-to-WGC1 orchestration (2026-11-15)

[64 — offline geometry import pipeline](../../docs/worlds-engine/64-offline-geometry-import-pipeline.md) adds `geometry_import_pipeline.h/.cpp`, a **passing CPU-only mock-boundary test**, and a separate **syntax-compiled but not yet executed** real-vendor end-to-end test.

The orchestrator normalizes indexed and unindexed triangles, performs optional boundary diagnostics, supplies complete source/settings identity to the SHA-256/WGC1 cache store, and maps errors to explicit safe-fallback statuses. Ordinary Godot rendering remains untouched.

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
  modules/worlds_geometry/geometry_import_pipeline.cpp \
  benchmarks/native_geometry/test_geometry_import_pipeline.cpp \
  -o /tmp/worlds_geometry_pipeline_mock
/tmp/worlds_geometry_pipeline_mock
```

**Executed:** GCC strict C++17 and Clang ASan+UBSan passed against isolated function-level test doubles. **Unexecuted:** full real meshoptimizer + WGC1 + disk end-to-end fixture; see [64](../../docs/worlds-engine/64-offline-geometry-import-pipeline.md) for its proposed native compile command and exact pending acceptance gate.

## Canonical cache provenance and atomic file lifecycle (2026-11-14)

[63 — source hashing and cache store](../../docs/worlds-engine/63-geometry-source-hashing-and-cache-store.md) adds standalone `geometry_source_hash.h/.cpp`, `geometry_cache_store.h/.cpp` and two CPU test suites. GCC 14 strict C++17 and Clang 17 ASan/UBSan executions passed for SHA-256 known vectors, source/setting invalidation and cache-store lifecycle. The **disk test uses a stub codec to isolate IO behavior**; the real WGC1 codec and native meshoptimizer were **not linked into that test**.

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
  modules/worlds_geometry/geometry_source_hash.cpp \
  benchmarks/native_geometry/test_geometry_source_hash.cpp -o /tmp/worlds_source_hash_test
/tmp/worlds_source_hash_test

g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
  modules/worlds_geometry/geometry_source_hash.cpp modules/worlds_geometry/geometry_cache_store.cpp \
  benchmarks/native_geometry/test_geometry_cache_store.cpp -o /tmp/worlds_cache_store_test
/tmp/worlds_cache_store_test
```

This is not yet a Godot import callback or proven cross-platform file-cache workflow.

## Portable WGC1 meshlet cache (2026-11-14)

[62 — WGC1 binary codec](../../docs/worlds-engine/62-portable-meshlet-cache-codec.md) adds `geometry_cache.h/.cpp` plus standalone `test_geometry_cache.cpp`. Portable GCC C++17 strict and Clang ASan+UBSan tests passed, including round-trips, truncations, invalid source/LOD provenance and 700 seeded mutations. **No actual file manager, real SHA-256 calculation, Godot engine build, GPU run or FPS measurements.** See [62](../../docs/worlds-engine/62-portable-meshlet-cache-codec.md) for reproduction and format.

## Automatic oriented triangle boundary extraction (2026-11-14)

[61 — border extraction](../../docs/worlds-engine/61-automatic-mesh-boundary-extraction-and-cache-contract.md) adds `mesh_boundary_extract.h/.cpp` and `test_mesh_boundary_extract.cpp`. Portable GCC strict C++17 and Clang ASan/UBSan regression suites passed. These are CPU-only tests, not a Godot build or real asset import. See [61](../../docs/worlds-engine/61-automatic-mesh-boundary-extraction-and-cache-contract.md) for the exact build command, validity limits and proposed (unimplemented) persistent cache.

## Offline meshlet generation and independent verification (2026-11-14)

[60](../../docs/worlds-engine/60-offline-meshoptimizer-meshlet-validation.md) adds **`meshlet_contract.h/.cpp`** for an independent exact source triangle multiset/oriented-winding proof and **`meshlet_builder.h/.cpp`** for meshoptimizer-backed offline cluster generation. The independent verifier passed GCC/Clang C++17 strict-warning builds and Clang ASan+UBSan, with 26 `assert` sites including **800 randomized partitions**. The builder control-flow tests passed compiler/sanitizer checks **against a marked mock ABI only**, including deliberately corrupted triangle order and invalid bounds. Full vendor linking and Godot build are unverified.

Standalone independent contract:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
  -Imodules/worlds_geometry \
  modules/worlds_geometry/meshlet_contract.cpp \
  benchmarks/native_geometry/test_meshlet_contract.cpp \
  -o /tmp/worlds_meshlet_contract
/tmp/worlds_meshlet_contract
```

Mock-ABI control flow (not real meshoptimizer):

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
  -Ibenchmarks/native_geometry/mock_include -Imodules/worlds_geometry \
  modules/worlds_geometry/meshlet_contract.cpp \
  modules/worlds_geometry/mesh_surface_source.cpp \
  modules/worlds_geometry/meshlet_builder.cpp \
  benchmarks/native_geometry/mock_meshopt.cpp \
  benchmarks/native_geometry/test_meshlet_builder_mock.cpp \
  -o /tmp/worlds_meshlet_mock
/tmp/worlds_meshlet_mock
```

The [headless Godot vendor smoke script](godot_meshlet_smoke.gd) is **committed but not executed**, and requires an engine build with `module_worlds_geometry_enabled=yes`. Diagnostics are read-only, per-surface/per-LOD and do not replace the conventional renderer.

## Mesh and ImporterMesh source/LOD adapter (2026-11-14)

[Milestone 59](../../docs/worlds-engine/59-imported-mesh-readonly-topology-adapter.md) adds the portable `mesh_surface_source.h/.cpp` validator and `test_mesh_surface_source.cpp`. It prepares actual triangle index streams for existing topology checks, including read-only sequential indices for unindexed triangles. Rejected inputs receive explicit status codes; the source is never modified.

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
  -Imodules \
  modules/worlds_geometry/mesh_surface_source.cpp \
  benchmarks/native_geometry/test_mesh_surface_source.cpp \
  -o /tmp/worlds_surface_prepare_test
/tmp/worlds_surface_prepare_test
```

**Executed in the local container:** GCC and Clang C++17 strict-warning builds passed; GCC undefined-behavior sanitizer run passed. The fixture contains 17 explicit assertions. All three source/test files were confirmed byte-identical to their GitHub commits.

The opt-in `WorldsMeshTopology` GDScript class now declares `analyze_mesh_surface(mesh, surface, include_lods=true)` and `analyze_importer_mesh_surface(mesh, surface, include_lods=true)`. Both are read-only and inspect original LOD index streams. The [headless Godot smoke gate](godot_mesh_source_smoke.gd) is **committed but not run**: Godot needs a full experimental module build. These APIs have not been verified in an engine binary.

## Compile and execute, from the repository root

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
    -Imodules \
    modules/worlds_geometry/mesh_edge_audit.cpp \
    benchmarks/native_geometry/test_mesh_edge_audit.cpp \
    -o /tmp/worlds_mesh_audit_test
/tmp/worlds_mesh_audit_test
```

**Result on 2026-11-14:** the original indexed-topology standalone executable compiled and completed on the local Linux container, covering ten explicit fixtures. The new position-aware border auditor also compiled and passed **13 native fixtures**, including a separate undefined-behavior-sanitizer execution. These check **portable C++ source only**, not the Godot wrapper, Windows build, or GPU. `assert` is used in the fixtures; run without `-DNDEBUG`.

### Position-aware border audit

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
    -Imodules \
    modules/worlds_geometry/mesh_edge_audit.cpp \
    modules/worlds_geometry/mesh_border_audit.cpp \
    benchmarks/native_geometry/test_mesh_border_audit.cpp \
    -o /tmp/worlds_mesh_border_test
/tmp/worlds_mesh_border_test
```

For a separate Linux undefined-behavior-sanitizer run, replace `-O2` with `-O1 -g -fsanitize=undefined -fno-omit-frame-pointer`.

The new `analyze_position_topology` reports the difference between raw index connectivity and **exact XYZ-position-welded** connectivity, without changing the mesh. It distinguishes apparent open indexed edges from duplicate vertex indices at the same spatial position (common at UV seams). The new `compare_border_samples` checks oriented 3D boundary vertex sequences for matching positions, configurable distance tolerance, and missing split-vertex/T-junction risks. Neither method certifies truly watertight real 3D triangulation, floating-point raster correctness, or valid stitch meshes. Full details and synthetic policy results are in [58](../../docs/worlds-engine/58-hybrid-root-proxy-and-3d-mesh-border-audit.md).

## Inputs and reports

The original audit routine accepts a `std::vector<Point>` (double-coordinate XYZ positions) and a `std::vector<int32_t>` containing indexed triangles. It returns:

- index/triangle and invalid-data counts;
- degenerate, duplicated and zero-area triangle counts;
- unique, open (one incident face) and non-manifold (more than two incident faces) edge counts;
- winding conflicts for two triangles traversing their common edge in the same direction;
- conservative `valid_input` and `closed_oriented_2manifold` flags.

The **original indexed** auditor performs no vertex welding, epsilon merging, triangle ray tracing or GPU upload. UV/material vertex duplication can therefore produce apparent open indexed edges; the **additional position-aware diagnostic** reports how many edges change after *exact-position* equivalence. A closed/index-connected or position-welded topology result does not prove a physically watertight raster surface.

## Optional Godot wrapper

`modules/worlds_geometry/` contains the opt-in Godot `RefCounted` class `WorldsMeshTopology`. Its read-only methods are `analyze_indexed_surface(vertices, indices)`, `analyze_position_surface(vertices, indices)`, and `compare_border_samples(border_a, border_b, tolerance = 0.0)`. These copy packed Godot arrays into the portable C++ analyzers and return diagnostic `Dictionary` objects. The script-facing code has **not been compiled or executed inside Godot**, so it remains provisional.

The module defines `config.py:is_enabled() == False`: it is **disabled in default SCons builds**. To include this experimental wrapper when a full Godot build environment is available:

```sh
scons platform=linuxbsd target=editor module_worlds_geometry_enabled=yes
```

The Godot integration, reflection/class registration, full engine compilation, script API behavior and cross-platform builds are **not yet validated**. This module is a diagnostic stepping stone toward future imported mesh edge and cluster-border analysis, **not** a virtual geometry renderer.

Related: [57 — initial native topology audit](../../docs/worlds-engine/57-regional-geometry-roots-and-native-mesh-edge-audit.md) and [58 — native 3D border and hybrid policy](../../docs/worlds-engine/58-hybrid-root-proxy-and-3d-mesh-border-audit.md).

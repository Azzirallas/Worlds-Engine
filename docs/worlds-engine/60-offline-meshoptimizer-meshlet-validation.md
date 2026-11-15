# 60 — Offline meshoptimizer meshlet generation with independent triangle certification

**Date:** 2026-11-14. **Status:** committed experimental code, standalone CPU verifier compiled and tested; the vendor integration compiled and tested against a deliberately isolated **mock ABI**. **Godot SCons build, real vendored meshoptimizer runtime, real imported asset execution, GPU rendering and performance tests have NOT been performed.** Default Godot renderer remains unchanged.

This advances [59 — read-only imported and runtime mesh inspection](59-imported-mesh-readonly-topology-adapter.md), [58 — position-aware border checks](58-hybrid-root-proxy-and-3d-mesh-border-audit.md), and [31 — virtual geometry design](31-independent-virtual-geometry-design.md).

## A. Upstream code audit and architectural decision

The checked Worlds-Engine Godot fork already includes `thirdparty/meshoptimizer/meshoptimizer.h`, `clusterizer.cpp`, `meshletutils.cpp`, and an enabled-by-default `modules/meshoptimizer/` integration, with the meshoptimizer C++ build and `SurfaceTool` hooks. Exact functions checked in the fork's source:

- `meshopt_buildMeshletsBound(index_count, max_vertices, max_triangles)` — worst-case meshlet count.
- `meshopt_buildMeshlets(..., vertex_positions, vertex_count, stride, max_vertices, max_triangles, cone_weight)` — geometry-aware meshlet grouping.
- `meshopt_computeMeshletBounds(...)` — meshlet bounding sphere and backface normal cone.

`meshopt_Meshlet` stores vertex/triangle offsets and counts in separate global-vertex and local-index buffers. Builder contract restricts `3 <= max_vertices <= 256` and `1 <= max_triangles <= 512`; triangles are packed as three local 8-bit vertex IDs each. The new builder uses defaults **64 vertices / 124 triangles**, and calls the existing vendor algorithms **rather than implementing simplification or clustering ourselves**.

The module's `config.py` now explicitly declares an SCons dependency on `meshoptimizer` if 3D is enabled. The new module is still **opt-in** via `is_enabled() == False`. The dependency is registered through the exact `env.module_add_dependencies("worlds_geometry", ["meshoptimizer"])` mechanism used by other modules in the same source tree.

## B. New native implementation

### Portable independent verifier

- [`modules/worlds_geometry/meshlet_contract.h`](../../modules/worlds_geometry/meshlet_contract.h)
- [`modules/worlds_geometry/meshlet_contract.cpp`](../../modules/worlds_geometry/meshlet_contract.cpp)
- [`benchmarks/native_geometry/test_meshlet_contract.cpp`](../../benchmarks/native_geometry/test_meshlet_contract.cpp)

The `audit_meshlets` CPU function takes source indexed triangles plus meshlet ranges, global vertex mappings, packed local triangle bytes, and per-meshlet limits. It **reconstructs the original triangle multiset**, canonicalizing cyclic corner rotations while treating **reversed winding as distinct**. In particular it checks:

1. Every source triangle index is in range and is not index-degenerate.
2. Meshlets stay under their declared vertex/triangle limits; their vertex and triangle buffer spans are valid and **do not overlap** (alignment gaps are permitted).
3. Every packed local vertex ID refers to a valid global vertex; local-to-global IDs within a meshlet are unique.
4. No source triangle is lost; no extraneous, reversed, duplicated, or corrupted triangle is emitted, accounting for repeated identical triangles in the original source.
5. Output triangle count and source triangle count agree exactly.

**Validation performed locally:** 26 static `assert` sites, including 800 seeded randomized valid/invalid meshlet partitions. GCC 14 and Clang 17 built and ran with `-std=c++17 -Wall -Wextra -Werror -pedantic`; Clang AddressSanitizer + UndefinedBehaviorSanitizer runs also passed. These are *real compiled, independently implemented tests* that do **not** require meshoptimizer or Godot and can be run from a full checkout:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
  -Imodules/worlds_geometry \
  modules/worlds_geometry/meshlet_contract.cpp \
  benchmarks/native_geometry/test_meshlet_contract.cpp \
  -o /tmp/worlds_meshlet_contract
/tmp/worlds_meshlet_contract
```

### Read-only, meshoptimizer-backed offline builder

- [`meshlet_builder.h`](../../modules/worlds_geometry/meshlet_builder.h)
- [`meshlet_builder.cpp`](../../modules/worlds_geometry/meshlet_builder.cpp)

`build_offline_meshlets(positions, triangle_indices, max_vertices, max_triangles)` validates source geometry, rejects malformed or nonfinite coordinates, checks the representability of **float3** coordinates, rejects degenerate triangles (including those collapsed by float conversion), and enforces a **250,000 source-triangle per-call diagnostic cap**. It requests the vendor's conservative output capacities before building and passes the resulting meshlet buffers through the **independent verifier** before computing/outputting bounds. Nonfinite sphere radius/center, cone-axis or cone-cutoff data fail closed. The original mesh data is never overwritten, simplified, repartitioned in-place or rendered.

The builder's implementation was locally checked against a test-only API mock matching the **inspected meshoptimizer header signatures**. The mock does trivial one-triangle meshlets and can deliberately return reversed winding or NaN bounds. **The real meshoptimizer algorithm was not executed in these tests.** The mock is located only under `benchmarks/native_geometry/` and cannot be included by the module's normal `SCsub` wildcard.

Mock-boundary regression paths:

- [`test_meshlet_builder_mock.cpp`](../../benchmarks/native_geometry/test_meshlet_builder_mock.cpp)
- [`mock_meshopt.cpp`](../../benchmarks/native_geometry/mock_meshopt.cpp)
- [`mock_include/thirdparty/meshoptimizer/meshoptimizer.h`](../../benchmarks/native_geometry/mock_include/thirdparty/meshoptimizer/meshoptimizer.h)

Reproduce the **mock API test** (NOT a real vendor regression):

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

**Locally passed:** GCC and Clang strict-warning builds plus Clang ASan+UBSan; 17 assert sites including two injected bad vendor outputs. The mock fixture is **not** performance evidence or evidence the real meshoptimizer implementation has been linked.

## C. Engine-facing interface (committed; engine build pending)

- [`worlds_meshlet_diagnostics.cpp`](../../modules/worlds_geometry/worlds_meshlet_diagnostics.cpp): new Godot-facing implementation. Existing [`WorldsMeshTopology` header](../../modules/worlds_geometry/worlds_mesh_topology.h), class registration and [XML class docs](../../modules/worlds_geometry/doc_classes/WorldsMeshTopology.xml) now expose:

```gdscript
var diagnostics := WorldsMeshTopology.new()
var runtime := diagnostics.build_meshlets_mesh_surface(array_mesh, 0)
var imported_lod := diagnostics.build_meshlets_importer_surface(importer_mesh, 0, 0)
```

Both functions accept optional `lod_level = -1` (base mesh), `max_vertices = 64`, and `max_triangles = 124`. For runtime `Mesh`, LOD levels are selected from the sorted `surface_get_lods()` distance keys; for import-stage `ImporterMesh`, levels use the original `get_surface_lod_indices()` and `get_surface_lod_size()` methods. Each material/surface is handled **separately**. The original material, blend shapes, UVs and index arrays are not changed.

The returned Dictionary records `source`, `surface`, `lod_level`, optional `distance`, `status`, `verified`, source/output triangle counts, total meshlet count, total vertex references and per-meshlet `vertex_offset`, `triangle_offset`, counts, sphere center/radius and cone information. This does **not** expose persistent GPU meshlet buffers or allow meshlet rendering: it is an offline/diagnostic metadata path.

**Status meaning:** `status == "OK"` plus `verified == true` states that in the audited CPU representation, the builder returned an exact oriented triangle cover with finite geometric bounds. It does **not** certify compatibility with adjacent LODs, border T-junctions, skinned deformation, alpha/material/shadow behavior, meshshader support or real raster output.

### Real-vendor acceptance gate

[`godot_meshlet_smoke.gd`](../../benchmarks/native_geometry/godot_meshlet_smoke.gd) creates actual `ArrayMesh` and `ImporterMesh` inputs, requests base and LOD meshlets, checks counts, imported distance metadata, and invalid settings. It requires a full engine build and **has not run**.

```sh
scons platform=linuxbsd target=editor module_worlds_geometry_enabled=yes
# Run the produced editor binary with --headless --script
# benchmarks/native_geometry/godot_meshlet_smoke.gd, from a valid Godot project.
```

SCons, a complete local Godot checkout, and GPU hardware are unavailable in the current validation container, so build/class registration and actual meshoptimizer linking remain **open acceptance gates**. Do not use GitHub Actions merely to compensate: the project's paid CI minutes are budget-constrained.

## D. Next priority and alternatives

1. **Build/link validation:** compile opt-in module against the real fork, run both `godot_mesh_source_smoke.gd` and `godot_meshlet_smoke.gd`, fix any binding or module dependency errors.
2. **Real meshlet data validation:** compare pre-import, post-`ArrayMesh`, and per-LOD cluster outputs on representative glTF assets. Check cluster bounds independently against source triangles; test material/UV seam splitting, blended surfaces and skinned meshes.
3. **Real border extraction:** generate oriented border-chain records from actual triangle topology, then apply the conservative seam/T-junction rules of [58](58-hybrid-root-proxy-and-3d-mesh-border-audit.md) across adjacent LODs.
4. **Persistent derived cluster asset:** design a versioned binary format carrying source mesh import IDs, material/LOD provenance, content hashes, positions or compact vertex references, cluster bounds, plus validation metadata. Use safe cache invalidation and keep the original mesh for fallback.
5. **Native renderer prototype:** only after actual asset correctness and a hardware benchmark baseline, connect certified clusters to a feature-gated experimental rendering path. Never infer FPS/VRAM improvements from these CPU tests.

**Source ownership:** this code is newly authored against the vendored permissively licensed meshoptimizer API; no Unreal/Epic implementation was copied.

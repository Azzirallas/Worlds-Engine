# 59 — Read-only ImportedMesh/ArrayMesh surface and LOD diagnostic adapter

**2026-11-14. State:** implemented and committed source-level integration in the fork's optional `worlds_geometry` module. Portable C++ index-preparation tests compiled and executed locally with GCC, Clang and UBSan. **Full Godot SCons build, module class registration, GDScript execution, and renderer/GPU testing remain unperformed.** The module stays disabled by default.

This follows [57](57-regional-geometry-roots-and-native-mesh-edge-audit.md) and [58](58-hybrid-root-proxy-and-3d-mesh-border-audit.md). The purpose is to read actual Godot surface data before connecting our geometry validation and virtual-geometry research to the asset pipeline.

## Source-level audit: what the checked Godot fork actually exposes

The fork's native APIs were inspected directly:

- [`scene/resources/3d/importer_mesh.h`](../../scene/resources/3d/importer_mesh.h): `ImporterMesh::get_surface_arrays(surface)`, `get_surface_primitive_type(surface)`, `get_surface_name(surface)`, `get_surface_lod_count(surface)`, `get_surface_lod_indices(surface, level)` and `get_surface_lod_size(surface, level)`. These allow reading **pre-conversion imported** vertex/triangle data and each stored LOD's indices without calling `get_mesh()`.
- [`scene/resources/mesh.h`](../../scene/resources/mesh.h): `Mesh::surface_get_arrays(surface)`, `surface_get_primitive_type(surface)`, `surface_get_format(surface)`, and `surface_get_lods(surface)`. Runtime `ArrayMesh` is a `Mesh`, so one adapter can inspect both. Unlike importer flags, the runtime `ARRAY_FORMAT_INDEX` bit indicates an indexed vertex stream.
- [`scene/resources/3d/importer_mesh.cpp`](../../scene/resources/3d/importer_mesh.cpp): `ImporterMesh::get_mesh()` converts source arrays and LOD dictionary into `ArrayMesh::add_surface_from_arrays()`; its normal LOD generator operates over indexed triangle arrays and is backed by `SurfaceTool` simplification callbacks.
- [`modules/meshoptimizer/register_types.cpp`](../../modules/meshoptimizer/register_types.cpp) and `SCsub`: already use the vendored meshoptimizer for `SurfaceTool` simplification, vertex remapping and cache optimization. **Do not reimplement simplification or overwrite its LOD products in this diagnostic module.**

**Decision:** a **read-only adapter** is safer and easier to validate than modifying `ImporterMesh::add_surface`, `get_mesh()`, or `SurfaceTool` at this stage. It can be called manually during import inspection without changing geometry, materials, blend shapes, normals, tangents, UVs or surface LOD buffers.

## New portable native source and tests

- [`modules/worlds_geometry/mesh_surface_source.h`](../../modules/worlds_geometry/mesh_surface_source.h) and [`.cpp`](../../modules/worlds_geometry/mesh_surface_source.cpp): a small independent C++17 `prepare_triangle_surface(vertex_count, is_triangles, is_indexed, indices)` validation/normalization function.
- [`benchmarks/native_geometry/test_mesh_surface_source.cpp`](../../benchmarks/native_geometry/test_mesh_surface_source.cpp): standalone executable that checks valid indexed/unindexed triangle streams, natural sequential indices, source index preservation, unsupported primitives, missing vertices, empty/conflicting index streams, incomplete triangles, negative/out-of-range indices, 32-bit index capacity and stable diagnostic status strings.

`PreparedSurface` reports `status`, `generated_indices` and the **temporary audit index stream**. It does not modify mesh inputs. For explicitly unindexed triangle lists, it generates `0,1,2, ...` so the existing `analyze_position_topology` can inspect actual triangle connectivity. For invalid data it returns one explicit status and does not authorize further topology processing.

Status values: `OK`, `UNSUPPORTED_PRIMITIVE`, `MISSING_VERTICES`, `TOO_MANY_VERTICES`, `EMPTY_INDICES`, `UNEXPECTED_INDICES`, `INCOMPLETE_TRIANGLES`, `INVALID_INDEX`.

### Reproduction (from repository root)

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
  -Imodules \
  modules/worlds_geometry/mesh_surface_source.cpp \
  benchmarks/native_geometry/test_mesh_surface_source.cpp \
  -o /tmp/worlds_surface_prepare_test
/tmp/worlds_surface_prepare_test
```

**Observed:** GCC 17-assertion executable passed with strict `-Werror`; equivalent Clang C++17 build also passed. A separate GCC **`-fsanitize=undefined`** execution passed. These verify only the standalone portable layer, not the Godot-facing wrapper or actual imported assets.

## Expanded Godot diagnostic API (committed but engine compile pending)

The optional [`WorldsMeshTopology`](../../modules/worlds_geometry/worlds_mesh_topology.h) now exposes two additional methods, registered at scene initialization:

```gdscript
var audit = WorldsMeshTopology.new()
var runtime = audit.analyze_mesh_surface(my_mesh, 0, true)
var imported = audit.analyze_importer_mesh_surface(my_importer_mesh, 0, true)
```

`analyze_mesh_surface(Ref<Mesh>, surface, include_lods=true)` reads a runtime `Mesh` or `ArrayMesh`, using its actual index-format flag and `surface_get_lods()` dictionary. `analyze_importer_mesh_surface(Ref<ImporterMesh>, surface, include_lods=true)` reads import-stage arrays and `get_surface_lod_indices()` directly. Because `ImporterMesh` stores separate import flags, the adapter interprets **a nonempty importer index array** as indexed and a missing/empty importer index array as unindexed. This limitation is documented rather than incorrectly assuming importer flags match runtime index flags.

The return dictionaries use:
- Top level: `source`, `surface`, `status`, `primitive`, `base`, and `lods`; importer reports also include the original surface `name`.
- Base entry: `status`, `generated_indices`, `vertex_count`, `index_count`, and `analysis` **only when source stream preparation succeeds**.
- `analysis`: the prior `indexed` and exact-position `welded` reports plus `unique_positions`, `coincident_vertex_duplicates`, `indexed_open_edges_resolved`.
- LOD entries: same stream/analysis fields and the original LOD `distance`; importer also includes `lod_level`.

Null meshes, invalid surface indexes, invalid vertex/index Variant arrays, and invalid LOD array types are reported as errors, not silently treated as empty valid geometry. Unsupported primitive modes (lines, triangle strips, points) fail closed. Only `PRIMITIVE_TRIANGLES` is accepted; triangle strips are **not** implicitly triangulated. LODs reference the original base vertex positions and are audited as separate index streams.

**Important distinction:** `status == "OK"` means a triangle index stream could be prepared, **not** that geometry is topologically closed, consistently oriented or truly watertight. Downstream clients must inspect `analysis.indexed.valid_input`, `analysis.welded`, and the detailed edge counters. Do not use the result as an automatic rendering authorization.

## Native integration smoke gate (not yet executed)

[The headless GDScript smoke test](../../benchmarks/native_geometry/godot_mesh_source_smoke.gd) constructs real `ArrayMesh` and `ImporterMesh` triangle surfaces, including an importer LOD; checks unindexed triangle handling and invalid surface refusal; and exits nonzero for failed expectations. To run it, first build the opt-in module:

```sh
scons platform=linuxbsd target=editor module_worlds_geometry_enabled=yes
```

Then run the generated Godot editor binary with `--headless --script` and the script path in a valid minimal Godot project environment. The `WorldsMeshTopology` class is deliberately unavailable on standard builds because `modules/worlds_geometry/config.py` returns `is_enabled() == False`.

**This GDScript smoke test has been committed but not run.** No claim is made about the Godot binding API passing until the actual native engine build succeeds.

## Remaining obligations

1. Compile the full fork with the experimental module and run the smoke script. Validate `ClassDB`, `Ref<ImporterMesh>` registration, `BitField::has_flag`, PackedArray Variant conversion and DocTools XML integration on the actual Godot baseline.
2. Test real imported glTF meshes with UV splits, indexed triangles, non-indexed arrays, blend shapes, materials, skinned meshes and LODs; compare importer-stage and post-`ArrayMesh` geometry reports without assuming identical face order.
3. Collect actual mesh boundary chains from triangle topology and safely match 3D adjoining regions, including quantization and transform handling. Existing polyline border checks still require caller-supplied ordered vertices.
4. Design an optional offline meshoptimizer cluster-adapter using the **existing vendored implementation**, preserving the original surfaces and material compatibility. No renderer replacement should precede a demonstrated import-to-draw validation.
5. Retain deterministic CPU tests and a conventional Godot rendering fallback. GPU performance and visual-quality claims require later hardware acceptance.

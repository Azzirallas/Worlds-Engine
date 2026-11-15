# 65 — Opt-in Godot surface-to-WGC1 cache bridge

**Date: 2026-11-15.** **Implementation status:** optional Godot-facing C++ source and GDScript smoke fixture have been added, but **a complete Godot SCons build and the headless fixture have NOT run**. The portable cache-path validator **was compiled and executed** with GCC and Clang sanitizers. There are no GPU benchmarks or measured renderer improvements.

This extends [64 — offline import orchestration](64-offline-geometry-import-pipeline.md), which connects normalized triangle streams to [60](60-offline-meshoptimizer-meshlet-validation.md) meshoptimizer meshlets, [61](61-automatic-mesh-boundary-extraction-and-cache-contract.md) boundary diagnostics, [62](62-portable-meshlet-cache-codec.md) WGC1 serialization and [63](63-geometry-source-hashing-and-cache-store.md) content/settings fingerprints and disk publication.

## New optional engine-facing methods

Existing `WorldsMeshTopology` now declares and registers:

```gdscript
var diagnostic := WorldsMeshTopology.new()
var report: Dictionary = diagnostic.prepare_mesh_surface_cache(
    my_array_mesh, 0, asset_identity_bytes, import_settings_bytes,
    "user://worlds_geometry_cache/example.wgc1", -1, 64, 124)
var imported_report: Dictionary = diagnostic.prepare_importer_surface_cache(
    importer_mesh, 0, asset_identity_bytes, import_settings_bytes,
    "user://worlds_geometry_cache/example_imported.wgc1", 0)
```

**Files:** `modules/worlds_geometry/worlds_geometry_godot_cache.cpp`, updated `worlds_mesh_topology.h/.cpp`, updated `doc_classes/WorldsMeshTopology.xml`, new `benchmarks/native_geometry/godot_geometry_cache_smoke.gd`.

The adapter reads the original `Mesh` / `ArrayMesh` or `ImporterMesh` arrays without calling importer `get_mesh()` or mutating material, vertex or index data. For runtime `Mesh`, a nonnegative `lod_level` means the sorted distance-key index returned by `surface_get_lods`; for import-stage meshes, it refers to the original importer LOD index and preserves the original distance in the report. Base geometry is `lod_level=-1`. Indexless triangles use temporary sequential indices, as in the existing pipeline. Each imported surface/material slot is prepared independently. Non-triangle primitives, invalid surfaces, malformed arrays and unsupported LOD selections fail explicitly.

The adapter copies `asset_identity` and `import_settings` bytes verbatim to the existing CPU pipeline. It **does not discover or hash all external glTF dependencies automatically**. A correct caller must include the identity of relevant source files and every setting that changes derived geometry; simply passing a constant string is suitable for a synthetic smoke test but **not production cache invalidation**. It does not yet register a Godot editor importer callback or automatically process every imported model.

## Returned report and compatibility rules

The report includes `source`, `surface`, `lod_level`, optional `distance`/`name`, `status`, `surface_status`, `generated_indices`, `boundary_status`, `boundary_edges`, `boundary_chain_count`, `verified`, `meshlet_count`, `source_triangle_count` and `output_triangle_count`. Supported success statuses are `READY_STORED`, `READY_CACHED`, `READY_MEMORY_ONLY`. Other statuses require conventional rendering. **Every report sets `requires_standard_renderer=true`, including successful cache preparation.** That flag remains mandatory until a separate GPU/lighting/shadow/LOD quality gate has been satisfied.

**No render pipeline is replaced.** A valid WGC1 cache is only certified oriented source-triangle coverage and conservative bounding-sphere data, not a cluster draw, guaranteed seam-free transition or a usable GPU mesh. The source Mesh and its original surfaces remain the authoritative visible representation.

## Cache-path policy and portable tests

New portable source: `modules/worlds_geometry/geometry_cache_uri.h/.cpp` and `benchmarks/native_geometry/test_geometry_cache_uri.cpp`.

A cache destination must be in `user://worlds_geometry_cache/`, end in lowercase `.wgc1`, be at most 240 ASCII bytes in total and contain only alphanumerics, underscore, dash or single path separators in its relative name. Dots are forbidden except for `.wgc1`. This rejects `../`, percent escapes, backslashes, empty path components, drive/URI prefixes and accidental writes to `res://`/arbitrary absolute paths. The source uses `ProjectSettings::globalize_path()` only **after** the portable URI validator accepts the input. The existing disk cache uses exclusive temporary-file creation and replace-after-sync semantics; parent directory symlinks/attacks by processes already controlling the user's filesystem are **not covered** by this validation.

Run on a standard CPU machine from the repository root:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
  modules/worlds_geometry/geometry_cache_uri.cpp \
  benchmarks/native_geometry/test_geometry_cache_uri.cpp -o /tmp/worlds_cache_uri
/tmp/worlds_cache_uri

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer -Imodules \
  modules/worlds_geometry/geometry_cache_uri.cpp \
  benchmarks/native_geometry/test_geometry_cache_uri.cpp -o /tmp/worlds_cache_uri_san
/tmp/worlds_cache_uri_san
```

**Observed locally:** GCC C++17 strict warnings and Clang ASan+UBSan **both passed**. Tests exercise valid simple/nested names, traversal/encoding/character/extension errors, overlong names and **1,500 seeded valid/invalid path pairs**. This proves the portable policy only. The Godot `String`, globalized path, SCons registration, native mesh adapter and actual filesystem usage have not been compiled or executed in Godot.

## Headless Godot acceptance fixture (unexecuted)

`benchmarks/native_geometry/godot_geometry_cache_smoke.gd` is a new SceneTree script that will check:

1. An indexed runtime `ArrayMesh` builds and stores WGC1 (two covered triangles), then yields a verified cache hit on repeat.
2. Changing import settings with the same cache path invalidates and rebuilds the data.
3. An `ImporterMesh` stored LOD yields one triangle, preserves its distance, and reuses its cache.
4. `res://` output paths, missing asset identity and invalid LODs fail closed.
5. Every status reports `requires_standard_renderer=true`, even when the offline meshlet cache is valid.

To run *after* building the fork with the opt-in module:

```sh
scons platform=linuxbsd target=editor module_worlds_geometry_enabled=yes
# From a minimal valid Godot project, invoke the produced editor binary:
./bin/godot.linuxbsd.editor.x86_64 --headless --path /path/to/test-project \
  --script /absolute/path/to/benchmarks/native_geometry/godot_geometry_cache_smoke.gd
```

The engine binary path is illustrative; check the actual generated executable. Run existing `godot_mesh_source_smoke.gd` and `godot_meshlet_smoke.gd` first. **No pass is claimed** for these engine-side fixtures or the real-vendor end-to-end test. Paid CI remains unused.

## Next milestones

1. Execute [64's real-vendor end-to-end native regression](../../benchmarks/native_geometry/test_geometry_import_end_to_end.cpp) and correct any actual WGC1/meshoptimizer mismatches.
2. Full native Godot build and all three headless diagnostic smoke tests; fix real ClassDB, `ImporterMesh`, path or linker failures before calling engine integration verified.
3. Engine-managed automatic cache naming, complete imported-asset provenance (including external resources) and import-time callback integration without altering conventional Mesh resources.
4. Cross-LOD border compatibility, material/skin/deformation cases and runtime resource lifetime acceptance.
5. Only after the above, feature-gated GPU-driven cluster rendering and hardware quality/performance comparisons.

No proprietary Unreal code was copied. This remains an experimental Godot module, disabled by default.

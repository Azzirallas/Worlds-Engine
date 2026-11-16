# 66 — Godot importer index semantics audit and real-vendor acceptance runner

**Date:** 2026-11-15. **Status:** upstream Godot behavior reviewed, a compatibility regression added and compiled/run against exact existing portable code, and a one-command CPU real-meshoptimizer/WGC1 acceptance script added. **No Godot engine build, real-vendor linked test execution, new GPU renderer or performance measurements are claimed.**

This extends [64 — offline geometry import orchestration](64-offline-geometry-import-pipeline.md) and [65 — Godot cache interface](65-godot-wgc1-surface-cache-bridge.md).

## Important review finding: preserve Godot's existing convention

The three existing `ImporterMesh` adapters detect indexed geometry using `!indices.empty()`. During review this initially seemed suspicious: a typed-but-empty `PackedInt32Array` could be confused with a missing array. **We investigated the actual Godot fork implementation before modifying production code**, and found that Godot **intentionally treats both as nonindexed geometry**.

Specifically `scene/resources/3d/importer_mesh.cpp`:
- `ImporterMesh::add_surface` stores the supplied arrays as-is.
- `merge_importer_meshes` reads `PackedInt32Array` and branches on `this_indices.is_empty()`, treating it as **nonindexed**, then transforms the original triangle-list vertex data.

Therefore changing the adapters to test only the Variant's `PACKED_INT32_ARRAY` type would **break valid Godot input**. The suspected fix was discarded before touching the branch. The existing size-based policy is correct in this engine. Keep `!indices.empty()` in the importer topology, meshlet and cache entry points. This review prevented a compatibility regression.

The lower-level portable `prepare_triangle_surface` still has a stricter explicit-input contract: if its caller sets `is_indexed=true` and passes zero indices, it reports `EMPTY_INDICES`. The bridge must pass **false** for empty importer streams under Godot's source convention.

## Portable regression actually executed

New: `benchmarks/native_geometry/test_mesh_index_presence.cpp`.

It checks that 3-, 6- and 9-vertex importer-style empty index streams generate sequential triangles, while a caller that **explicitly** declares indexed input with zero indices gets `EMPTY_INDICES`. It also verifies normal indexed input, out-of-range/negative indices, wrong primitive type and incomplete triangle groups.

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
  modules/worlds_geometry/mesh_surface_source.cpp \
  benchmarks/native_geometry/test_mesh_index_presence.cpp \
  -o /tmp/worlds_mesh_index_presence
/tmp/worlds_mesh_index_presence

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer -Imodules \
  modules/worlds_geometry/mesh_surface_source.cpp \
  benchmarks/native_geometry/test_mesh_index_presence.cpp \
  -o /tmp/worlds_mesh_index_presence_san
/tmp/worlds_mesh_index_presence_san
```

**Observed:** GCC 14 strict C++17 compilation and execution passed; Clang 17 ASan+UBSan compilation/execution passed. The used `mesh_surface_source.cpp` and header were byte-identical to current Git blobs `325edfb797ba849f0c686837110b01f59362407e` and `2cb18348e657fa7409157ddc580348181cb64464`. The test code itself is exact to the committed Git blob. **It does not compile any Godot-specific Variant bridge.**

A separate new **unexecuted** Godot `SceneTree` fixture, `benchmarks/native_geometry/godot_importer_index_presence_smoke.gd`, checks a typed-empty index array through three interfaces: `analyze_importer_mesh_surface`, `build_meshlets_importer_surface`, and `prepare_importer_surface_cache`, including WGC1 re-use. It expects successful **nonindexed** operation, consistent with upstream.

## Real-vendor no-CI acceptance script

New: `benchmarks/native_geometry/run_real_vendor_gate.sh`. From the full fork checkout with a C++17 compiler:

```sh
bash benchmarks/native_geometry/run_real_vendor_gate.sh

# Optional sanitizer run (when Clang/ASan is available):
CXX=clang++ SANITIZE=1 bash benchmarks/native_geometry/run_real_vendor_gate.sh
```

It compiles and runs the new portable index-policy test, then compiles and runs [64's existing end-to-end fixture](../../benchmarks/native_geometry/test_geometry_import_end_to_end.cpp) **without test doubles**. The latter explicitly links Godot's vendored `thirdparty/meshoptimizer/allocator.cpp`, `clusterizer.cpp`, `meshletutils.cpp`, alongside the real geometry normalization, boundary extraction, meshlet verification, source SHA-256, WGC1 codec, cache store, and offline pipeline. It uses an isolated temporary build directory with automatic cleanup. Only after the vendor-backed binary exits successfully does it print an end-to-end PASS.

**Observed:** the runner passed `bash -n`. **Not observed:** a full real-vendor build/link or execution. All vendor source files remain in the GitHub repository but are unavailable as a complete checkout in the local isolated compiler environment. Do not treat a syntax check as proof of integration. This is a deliberately **local, opt-in** acceptance runner; it schedules no GitHub Actions and incurs no cloud test charges.

## Other review findings

- Verified from the checked-in meshoptimizer header and `clusterizer.cpp` that the worst-case `meshlet_vertices` and `meshlet_triangles` output capacities are both `index_count`; the current builder's allocation follows this contract. No unsubstantiated allocation fix was made.
- Existing WGC1 correctness gates include exact oriented triangle partitioning, checked ranges, source/settings digests and sphere bounds. They do not certify GPU visibility correctness, visual material parity, skinning or compatible LOD borders.
- The Godot bridge still requires caller-supplied complete asset identity and geometry-affecting import settings. Without real glTF dependency provenance, its cache must remain experimental and opt-in.

## Next acceptance sequence

1. Run `run_real_vendor_gate.sh` against the complete source checkout and resolve any real WGC1/vendor failures with regression tests.
2. Compile the opt-in Godot module via SCons, then execute all existing source/meshlet/cache GDScript smoke tests and the new importer-semantics fixture. These are **not yet passed**.
3. Add stable engine-managed cache naming and automatic asset/settings/dependency hashing without modifying original imported meshes.
4. Establish cross-LOD seam, skinning/deformation, lifetime and shader/material parity gates before attempting feature-gated GPU-driven cluster rendering.

**No proprietary Unreal source was copied and no GPU performance claims are made.**

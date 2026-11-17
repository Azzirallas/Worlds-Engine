# 69 — Remove deep copies from the verified geometry-cache return path

**Date:** 2026-11-17. **Scope:** offline CPU meshlet caching and acceptance tests; no standard Godot renderer modifications.

## Problem established during integration review

`prepare_offline_geometry` received `const GeometryStoreResult store` from `load_or_build_geometry_cache`, then assigned `out.build = std::move(store.build)`. A move from a **const** `MeshletBuild` cannot select its mutating move-assignment operator. It therefore **copies** the `meshlets`, `vertices` and `triangles` vectors. This affects verified WGC1 cache hits, successful fresh builds stored on disk, and successful builds retained in memory if disk writing fails. Larger geometry could produce substantial unnecessary allocation, memory bandwidth and latency.

## Change

In `modules/worlds_geometry/geometry_import_pipeline.cpp`, receive the returned `GeometryStoreResult` in a **non-const local** before moving `store.build` into `out.build`. The store status is read independently and is unchanged. No API, WGC1 format, source identity, verification gates, meshlet data or rendering behavior changed.

A new regression, `benchmarks/native_geometry/test_geometry_pipeline_move.cpp`, checks **vector storage identity** across the bridge. The isolated store returns a certified test payload containing 175,000 global vertex references, 350,000 packed triangle bytes and 128 meshlet entries. The test records all three vector `.data()` addresses *before* the result leaves the store and asserts that `prepare_offline_geometry` returns the **same allocations** after the move. It exercises `HIT`, `BUILT_STORED` and `BUILT_UNSTORED`, plus failure/status mapping and the previously implemented skip-boundary default.

The mock payload is **not a real valid source partition**; that is deliberate: this fixture isolates the **ownership contract** and depends only on `MeshletBuild::valid` and `coverage.valid` returned by the mock store. Independent real WGC1 and meshoptimizer validation remain separate acceptance gates.

## Tests actually executed

The exact updated `geometry_import_pipeline.cpp` and regression test were placed in a standalone CPU build directory and byte-for-byte verified with `git hash-object` against their GitHub blob SHAs. Local headers mirrored the current public interface; external meshlet/cache/boundary implementations were replaced with link-isolated test doubles. This is **not a native Godot engine build**.

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
  modules/worlds_geometry/geometry_import_pipeline.cpp \
  benchmarks/native_geometry/test_geometry_pipeline_move.cpp \
  -o /tmp/worlds_pipeline_move && /tmp/worlds_pipeline_move

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer -Imodules \
  modules/worlds_geometry/geometry_import_pipeline.cpp \
  benchmarks/native_geometry/test_geometry_pipeline_move.cpp \
  -o /tmp/worlds_pipeline_move_san && /tmp/worlds_pipeline_move_san
```

**Observed:** GCC strict compile/run **PASS**, Clang ASan/UBSan compile/run **PASS**. The local source blob SHA-1 for the implementation was `112c6593dd7963f781d03b31da5c7d6df406bb8f`; the regression SHA-1 was `0d1a922bf64f6f187fa325a02c23ee87f8471c5d`. For a **negative control**, restored the original `const GeometryStoreResult` line and rebuilt the same test: it aborted on the first cache-hit vector-address assertion. This demonstrates that the new regression genuinely detects the previous deep-copy behavior.

The `benchmarks/native_geometry/run_real_vendor_gate.sh` runner now also executes this mock-isolated ownership regression before attempting vendor-linked execution. The vendor-linked test, optional Godot SCons module build and GPU hardware tests **remain unexecuted in this environment**; no FPS or measured byte savings are claimed. GitHub Actions minutes were not used.

## Larger integration risk remains

The standalone toolchain has no complete checkout of the fork's actual `thirdparty/meshoptimizer` sources, and its container cannot clone GitHub directly. Source has been reviewed through the connected GitHub repository, but an isolated mock test cannot certify the full codec/vendor/Godot linking.

Once a complete checkout or an available compatible build host is accessible, run:

```sh
bash benchmarks/native_geometry/run_real_vendor_gate.sh
```

Then build with `module_worlds_geometry_enabled=yes` and run the full headless tests. Until those gates pass, the experimental geometry path remains disabled by default and the conventional Godot renderer stays authoritative.

## Next milestones

1. Execute the full true-vendor CPU runner and fix any real meshoptimizer/WGC1 integration failures.
2. Build the optional Godot module and run GDScript tests with indexed/unindexed meshes and LODs.
3. Add automated complete source/import-dependency provenance and stable content-addressed cache paths once the native interface is validated.
4. Instrument cold/warm import times, derived-cache bytes, allocated bytes, and P95/P99 stalls on real assets before deciding how much of WGC1 moves to runtime streaming.

No proprietary Unreal source or assets were copied.

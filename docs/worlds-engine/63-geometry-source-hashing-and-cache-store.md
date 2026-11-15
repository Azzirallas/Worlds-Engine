# 63 — Deterministic geometry provenance and atomic WGC1 cache lifecycle

**Date:** 2026-11-14. **Status:** original portable C++17 SHA-256 source/settings fingerprints and cache disk lifecycle are implemented and CPU-tested. This is an **opt-in native helper**, not a Godot import callback, production cache directory, implemented glTF importer, or GPU rendering path. Existing ordinary Godot rendering is unchanged.

This continues [60 — meshlet correctness](60-offline-meshoptimizer-meshlet-validation.md), [61 — automatic boundary extraction](61-automatic-mesh-boundary-extraction-and-cache-contract.md), and [62 — WGC1 codec](62-portable-meshlet-cache-codec.md).

## New source contracts

- `modules/worlds_geometry/geometry_source_hash.h/.cpp`: self-contained FIPS 180-4 SHA-256, `stamp_geometry_cache_source` and `verify_geometry_cache_source`.
- `modules/worlds_geometry/geometry_cache_store.h/.cpp`: `load_or_build_geometry_cache(path, source, asset_bytes, settings_bytes, builder)`, returning `HIT`, `BUILT_STORED`, `BUILT_UNSTORED`, `BUILD_FAILED` or `INVALID_SOURCE`.
- `benchmarks/native_geometry/test_geometry_source_hash.cpp`: SHA-256 known vectors (empty, 'abc', one million 'a') and canonical source/settings invalidation cases.
- `benchmarks/native_geometry/test_geometry_cache_store.cpp`: cache lifecycle tests against a deliberately isolated **test-double** codec. The double supplies only a minimal validate/decode interface; it does not substitute for the real WGC1 decoder or verify actual meshlet coverage.

### Hashing rules

The SHA-256 source digest is domain-separated (`Worlds.WGC1.Geometry.V1`) and hashes vertex positions in **IEEE-754 binary64 little-endian order**, oriented source indices in u32 little-endian order, explicit element lengths and caller-supplied `asset_bytes`. Positive and negative floating-point zero normalize to the same geometry value. Invalid/nonfinite geometry, out-of-range indices and oversized input are rejected.

The SHA-256 settings digest uses a separate domain (`Worlds.WGC1.Settings.V1`) and includes generator version, surface, signed LOD identifier, meshlet limits and caller-supplied `settings_bytes`. Both stamps are recomputed from source data during each `load_or_build` call, rather than accepting arbitrary caller-provided digests from an existing cache. This closes the prior synthetic placeholder-hash limitation, **provided the caller supplies complete relevant import identity/settings bytes**.

`asset_bytes` and `settings_bytes` remain explicit inputs. A future Godot import adapter must include relevant source-file identity, mesh import options and any geometry-affecting attributes; hashing only positions/indices cannot detect a change to external material or UV data. The source/data is **not silently imported** by this helper. Generated WGC1 caches are disposable derived data; original Godot resources always remain authoritative.

### Disk lifecycle

1. Recompute the source/settings fingerprints and attempt to read the user-selected cache path.
2. Refuse symlinks at the initial lookup, non-regular files, zero-length or >24 MiB files, truncated files and files that change size while reading.
3. Decode using the existing WGC1 validator. Only a fully valid expected-source hit returns `HIT`; a miss/corruption requests regeneration from the supplied callback.
4. Encode the regenerated `MeshletBuild` with WGC1; refuse invalid builder output rather than publishing it.
5. Write bytes to a random-named **exclusive-create** sibling temporary file. On Linux/POSIX, issue `fsync` for the file before atomic `rename`; on Windows, use `_commit` and `MoveFileExW(MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)`.
6. If publishing fails, return a valid in-memory `BUILT_UNSTORED` result without treating the disk cache as valid. A failed exclusive create must **never remove an existing temp file** belonging to another writer. POSIX attempts a parent-directory `fsync` after rename, but directory sync failure is currently best-effort and therefore crash persistence is not guaranteed on every filesystem.

The storage code intentionally does not implement garbage collection, external process locks, background work, a stable source-specific filename policy, multi-asset transactions, or a Godot editor import hook. Concurrent writers may replace the same path: the last complete file wins, and readers must verify expected source identity. Cache paths are assumed to come from a trusted engine-managed directory; this is **not an adversarial untrusted-path sandbox**. Windows builds and filesystem semantics remain unverified here.

### Local tests and exact reproducibility

Run from repository root, **no Godot build and no GPU required**:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
    modules/worlds_geometry/geometry_source_hash.cpp \
    benchmarks/native_geometry/test_geometry_source_hash.cpp \
    -o /tmp/worlds_source_hash_test
/tmp/worlds_source_hash_test

g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
    modules/worlds_geometry/geometry_source_hash.cpp \
    modules/worlds_geometry/geometry_cache_store.cpp \
    benchmarks/native_geometry/test_geometry_cache_store.cpp \
    -o /tmp/worlds_cache_store_test
/tmp/worlds_cache_store_test
```

**Observed in isolated local container:** GCC 14 strict C++17 compile/run passed for both suites. Clang 17 `-fsanitize=address,undefined -fno-omit-frame-pointer` builds and executions also passed. Tests cover three SHA-256 known vectors, position/index/settings changes and canonical negative zero; first build, cache hit without builder, changed input/settings/position rebuilds, corrupt file rebuild, oversized file refusal, failure-to-build and failure-to-publish fallback. The disk lifecycle test uses a **stub codec** to isolate filesystem behavior; the actual [62](62-portable-meshlet-cache-codec.md) encoder/decoder were not linked into this particular test.

All six new files were copied byte-for-byte to GitHub blobs and checked against local Git object hashes before commit.

### Outstanding acceptance gates

1. Add an end-to-end **real WGC1 codec + native meshoptimizer** integration test (rather than only the storage test double), including actual imported and runtime mesh LOD data.
2. Connect fingerprinting and `load_or_build` to an opt-in Godot importer-side tool, with source/import settings capture, stable cache naming and standard renderer fallback.
3. Build with the actual Godot SCons module; run existing `godot_mesh_source_smoke.gd` and `godot_meshlet_smoke.gd` before reporting engine integration.
4. Add cross-process race and power-loss testing on supported filesystems and Windows compiler/runtime smoke, then classify crash durability by platform.
5. Only after geometry/LOD/seam correctness and asset-cache validation, integrate the feature-gated experimental geometry renderer.

**Performance:** none measured. The codec is an offline preparation milestone, not a claim of better GPU throughput or image quality.

**2026-11-15 continuation:** [64 — offline import orchestration](64-offline-geometry-import-pipeline.md) now connects surface normalization, boundary diagnostics, and the cache-store contract. Its mock-backed standalone tests passed; the new **real-vendor WGC1 end-to-end fixture is committed but not linked/executed**, and native Godot import remains pending.

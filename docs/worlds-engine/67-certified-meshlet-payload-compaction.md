# 67 — Certified meshlet payload compaction before WGC1

**Date:** 2026-11-15. **Status:** a portable meshlet payload repacker and independent CPU tests were compiled and executed with GCC C++17 strict warnings and Clang AddressSanitizer/UndefinedBehaviorSanitizer. Integration into the vendor-backed builder is source-level only: **the real meshoptimizer/WGC1 end-to-end binary, full Godot SCons build and GPU renderer were not executed**.

Follow-on to [60 — offline meshoptimizer builder](60-offline-meshoptimizer-meshlet-validation.md), [62 — WGC1 cache codec](62-portable-meshlet-cache-codec.md), [64 — offline preparation pipeline](64-offline-geometry-import-pipeline.md), and [66 — native gate runner](66-godot-import-index-semantics-and-native-gate.md).

## Finding

Meshoptimizer's API requires callers to provision `index_count` elements for both its global-vertex-reference array and packed local-triangle array, even if a typical result uses fewer global vertex references. Our builder correctly allocated these **worst-case capacities** and performed an independent source-triangle coverage audit, but it preserved all unused slots in `MeshletBuild`, which the WGC1 codec then serialized.

That means WGC1 files could contain unnecessary trailing global vertex references and any unused internal gaps. The original result is still valid, but it consumes extra derived-cache storage, disk I/O and later CPU staging memory. Do not change meshoptimizer's **input buffer allocation contract**: full worst-case scratch storage is still required during generation.

## New implementation

`modules/worlds_geometry/meshlet_payload.h/.cpp` provides `compact_meshlet_payload(MeshletBuild &)`.

1. Refuse empty data or results whose `build.valid` and independent `build.coverage.valid` are not both true.
2. Validate every meshlet vertex and packed-triangle span with subtraction-based bounds checks. Reject zero-length/invalid spans, overlaps and totals that would exceed source buffer sizes.
3. Copy **only referenced spans** into new vertex/triangle arrays in meshlet order; recalculate meshlet offsets to those contiguous arrays. Preserve the per-meshlet local index bytes, global references, bounds, cone data, source triangle coverage metadata and winding.
4. Publish new offsets and swap arrays **only after all preparation succeeds**, so a detected invalid span leaves the original `MeshletBuild` unchanged.
5. Return a failure code rather than attempting to repair unverified meshlets.

`modules/worlds_geometry/meshlet_builder.cpp` now calls the helper **after** the vendor bounds generation and independent `audit_meshlets` proof, before it returns `OK`. A failed compaction becomes `INVALID_MESHLET_STORAGE` with `valid=false`.

This is a memory-layout transformation of **certified data**, not an alternative clustering algorithm, topology simplification, altered material pipeline or new visual LOD. WGC1 format version **stays 1.0**, since only its array contents and offsets become compact; the binary schema and decoder are unchanged. Old valid cached data remains readable.

## Tests actually run

New: `benchmarks/native_geometry/test_meshlet_payload.cpp`. Tests verify two meshlets with internal and trailing padding, exact oriented triangle reference reconstruction, new offsets, unchanged coverage metadata, repeated idempotent compaction, invalid flags, overflow offsets, out-of-range spans, overlap rejection, and empty/invalid meshlets. **900 additional seeded multi-meshlet fixtures** use varying padding and meshlet counts up to 40, compare every reconstructed oriented triangle before and after, then compact again.

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
    modules/worlds_geometry/meshlet_payload.cpp \
    benchmarks/native_geometry/test_meshlet_payload.cpp \
    -o /tmp/worlds_meshlet_payload && /tmp/worlds_meshlet_payload

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic \
    -fsanitize=address,undefined -fno-omit-frame-pointer -Imodules \
    modules/worlds_geometry/meshlet_payload.cpp \
    benchmarks/native_geometry/test_meshlet_payload.cpp \
    -o /tmp/worlds_meshlet_payload_asan && /tmp/worlds_meshlet_payload_asan
```

**Observed locally:** both commands compiled with `-Werror -pedantic` and executed without failure; Clang ASan/UBSan reported no violations. The local test used header interfaces reproducing the current repository's public meshlet structs; it did **not** compile the entire vendored builder. The three new source blobs were checked against their locally tested Git object SHA-1 hashes before commit.

The portable test is now also the first step in `benchmarks/native_geometry/run_real_vendor_gate.sh`. That script now explicitly links the new compaction `.cpp` into the later real meshoptimizer + WGC1 end-to-end binary, preventing a missing-symbol regression. The whole script passed `bash -n`; its real-vendor stage has **not** run here.

## Current constraints and next gates

1. Run `bash benchmarks/native_geometry/run_real_vendor_gate.sh` on a complete checkout that includes `thirdparty/meshoptimizer`; inspect actual clustered geometry, cache hit behavior and generation/linkage.
2. Build optional Godot `worlds_geometry` module and run headless Mesh/ImporterMesh smoke scripts. No such engine binary was available for this milestone.
3. Profile real import data and compressed WGC1 file sizes before claiming memory, disk or runtime performance gains. The savings depend on meshlet vertex reuse and vendor output layout.
4. Continue fully automatic asset/dependency provenance and import-callback research, followed by cross-LOD seam and GPU lifetime correctness gates.

No conventional Godot rendering code has been changed. No Unreal/Epic source was copied, and no numerical performance improvement is claimed.

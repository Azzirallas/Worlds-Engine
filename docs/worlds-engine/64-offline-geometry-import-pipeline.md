# 64 — Offline geometry import orchestration and end-to-end native gate

**Date:** 2026-11-15. **Status:** an original, native CPU-only orchestration layer has been added and its control flow has been **compiled and tested against deliberate test doubles** (GCC strict C++17 and Clang ASan+UBSan). A separate real-vendor + WGC1 + filesystem regression fixture has been committed and **syntax-compiled only**; its linked execution is still pending. This does not mean Godot editor imports, the full Godot SCons build, the meshoptimizer vendor path, GPU rendering or performance gains are validated.

## Existing components being connected

- [59](59-imported-mesh-readonly-topology-adapter.md): indexed/unindexed triangle stream normalization.
- [60](60-offline-meshoptimizer-meshlet-validation.md): vendor-backed offline meshlet builder with independent oriented triangle coverage.
- [61](61-automatic-mesh-boundary-extraction-and-cache-contract.md): oriented boundary extraction, diagnostic only.
- [62](62-portable-meshlet-cache-codec.md): bounded, validated WGC1 binary data.
- [63](63-geometry-source-hashing-and-cache-store.md): SHA-256 provenance and atomic disk publication.

## Implementation

New source: `modules/worlds_geometry/geometry_import_pipeline.h/.cpp`.

`prepare_offline_geometry(GeometryPipelineInput)` receives **one triangle surface or one LOD** with raw positions, raw or absent index stream, explicit indexed/triangle flags, surface/LOD IDs, a generator version and meshlet limits. The caller supplies an engine-managed cache path and complete asset identity/import settings as bytes. No path is fabricated and no Godot resource is modified.

1. Validate and normalize source indices with `prepare_triangle_surface`. Unindexed triangle lists gain temporary sequential indices. Refuse unsupported primitives, invalid indices, missing vertices, nonfinite/float32-overflow positions and the current conservative 750k vertex / 250k triangle diagnostic caps.
2. Require nonempty asset identity, import settings and cache path, a nonzero generator version and safe meshlet limits. This is a **caller contract**, not automatic inspection of Godot materials/UVs or external glTF dependencies.
3. Call `extract_mesh_boundaries` for a *separate diagnostic result*. Open/non-manifold or ambiguous geometry may still contain renderable triangles; this report alone does not authorize or block a meshlet fast path. Cross-LOD seam compatibility remains unverified.
4. Build a `GeometryCacheSource` from normalized oriented triangles, original positions, surface, LOD, generator version and meshlet limits. Append a domain/version suffix and indexed flag to the supplied import-settings identity before hashing, so indexed and unindexed input layouts cannot accidentally share the same cache key.
5. Call `load_or_build_geometry_cache`, passing `build_offline_meshlets` as a callback. A valid expected-source WGC1 hit avoids invoking the builder; corruption or content/settings mismatch requests regeneration. The existing cache store's independently validated build and atomic publication rules apply.
6. Translate cache outcomes into stable `READY_CACHED`, `READY_STORED`, `READY_MEMORY_ONLY`, `INVALID_SURFACE`, `INVALID_PROVENANCE` or `BUILD_FAILED` statuses. On ready outcomes require the returned meshlet data to carry both `valid` and `coverage.valid`; otherwise fail closed.

**Fallback contract:** the caller must use the original Godot mesh whenever preparation reports a non-ready status. `READY_*` means validated offline *meshlet data*, **not** permission for the renderer to draw clusters: shader compatibility, skinning, material parity, LOD seams, GPU fences and image quality still require their own acceptance gates. The pipeline keeps the existing standard renderer untouched.

## Tests executed in the isolated environment

`benchmarks/native_geometry/test_geometry_import_pipeline.cpp` injects *test doubles* for surface preparation, boundary diagnostics, cache store and meshlet builder. The compiled orchestrator itself is real. The suite exercises:

- Cache hit with zero builder calls; stored rebuild; valid in-memory fallback when writing fails.
- Failure and source-provenance error mapping; forged store-success state rejected if data validity flags are missing.
- Oriented index preservation, normalized unindexed triangle streams, separate original indexed setting.
- Non-manifold boundary diagnostics not mistaken for general render failure.
- Rejection of unsupported primitives, missing/invalid indices, nonfinite geometry, absent identity/settings/path and invalid meshlet limits.

From repository root:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
    modules/worlds_geometry/geometry_import_pipeline.cpp \
    benchmarks/native_geometry/test_geometry_import_pipeline.cpp \
    -o /tmp/worlds_geometry_pipeline_mock
/tmp/worlds_geometry_pipeline_mock

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic \
    -fsanitize=address,undefined -fno-omit-frame-pointer -Imodules \
    modules/worlds_geometry/geometry_import_pipeline.cpp \
    benchmarks/native_geometry/test_geometry_import_pipeline.cpp \
    -o /tmp/worlds_geometry_pipeline_san
/tmp/worlds_geometry_pipeline_san
```

**Observed:** the above standalone GCC and Clang sanitizer executions passed. The mock test does **not** prove real WGC1 payload compatibility, actual vendor meshlets or native Godot classes.

## Real-vendor end-to-end gate: test source added, execution pending

`benchmarks/native_geometry/test_geometry_import_end_to_end.cpp` is a **separate test with no mocks**. It verifies a real 2-triangle indexed and unindexed quad through actual meshoptimizer meshlet generation, WGC1 serialization, SHA-256 source provenance, disk write/read, cache hit, source/LOD/settings invalidation and corrupted cache replacement. It also checks fail-closed invalid geometry/provenance. The fixture's source was compiled with `-c` for syntax using local mirrored header interfaces, but **was not linked or executed against real meshoptimizer/WGC1**, and is not evidence that vendor integration works.

Reproduction from a complete fork checkout on a CPU-capable machine (no GPU needed):

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -I. -Imodules \
    modules/worlds_geometry/mesh_surface_source.cpp \
    modules/worlds_geometry/mesh_edge_audit.cpp \
    modules/worlds_geometry/mesh_boundary_extract.cpp \
    modules/worlds_geometry/meshlet_contract.cpp \
    modules/worlds_geometry/meshlet_builder.cpp \
    modules/worlds_geometry/geometry_cache.cpp \
    modules/worlds_geometry/geometry_source_hash.cpp \
    modules/worlds_geometry/geometry_cache_store.cpp \
    modules/worlds_geometry/geometry_import_pipeline.cpp \
    thirdparty/meshoptimizer/allocator.cpp \
    thirdparty/meshoptimizer/clusterizer.cpp \
    thirdparty/meshoptimizer/meshletutils.cpp \
    benchmarks/native_geometry/test_geometry_import_end_to_end.cpp \
    -o /tmp/worlds_geometry_import_end_to_end
/tmp/worlds_geometry_import_end_to_end
```

The exact vendored sources and symbols were source-inspected. If additional link requirements or Godot-specific build issues appear, record and fix them **without changing the standard engine renderer**. Do not substitute a mock result for this gate.

## Next concrete tasks

1. Run the true end-to-end fixture above with real meshoptimizer; address any discovered bounds, source hashing or serialization issues.
2. Add a read-only Godot `Mesh` and `ImporterMesh` adapter for per-surface/per-LOD offline preparation. Choose safe engine-managed cache paths and hash the *complete* input asset/import settings (including external dependencies that affect geometry).
3. Build the opt-in Godot module with SCons and execute the existing headless smoke tests. Test actual glTF assets with UV splits, multiple materials, skinned surfaces and stored LODs.
4. Add explicit per-LOD seam compatibility and cluster-hierarchy proofs before any experimental renderer treats a cached asset as drawable.

All new implementation is independent; no proprietary Unreal source code or assets were copied.

**Follow-on (2026-11-15):** [65 — opt-in Godot surface cache bridge](65-godot-wgc1-surface-cache-bridge.md) adds script-callable `Mesh`/`ImporterMesh` adapters and a restricted cache-URI policy; only the portable URI validator has been compiled/tested so far. Real Godot module linking and the previously unexecuted end-to-end real-vendor test remain separate acceptance gates.

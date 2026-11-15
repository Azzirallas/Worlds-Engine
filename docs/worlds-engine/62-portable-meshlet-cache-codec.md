# 62 — Portable WGC1 meshlet cache codec and replay validation

**Date:** 2026-11-14. **Implemented and compiled:** a standalone C++17 binary encoder/decoder for **derived meshlet metadata**, not a full disk cache manager, a Godot Resource type, virtual-geometry renderer, or production import integration. Source meshes remain authoritative; invalid or missing cache content must force a conventional mesh fallback in the eventual engine integration.

This follows [60 — verified offline meshlet generation](60-offline-meshoptimizer-meshlet-validation.md) and [61 — automatic mesh boundary extraction](61-automatic-mesh-boundary-extraction-and-cache-contract.md). The new portable code is `modules/worlds_geometry/geometry_cache.h/.cpp` and `benchmarks/native_geometry/test_geometry_cache.cpp`.

## Why this milestone

We had a meshlet generator and independent triangle-coverage verifier, but no deterministic persistent representation or safe decode path. WGC1 now serializes/deserializes the **existing `MeshletBuild` shape** (meshlet ranges and bounds, global vertex references and packed local triangles), with exact data-source identifiers and strict length checking. It never changes or stores Godot's original mesh surfaces, UVs, normals, materials or shaders.

## First byte-level format (version 1.0; experimental, no compatibility promises)

All numbers are **little-endian**. A header of exactly **132 bytes** is followed by `meshlet_count * 48` bytes of meshlet records, `vertex_ref_count * 4` bytes of global vertex IDs, then `packed_triangle_byte_count` raw local-index bytes. No extra trailing bytes are allowed.

| Header offset | Field | Bytes |
| --- | --- | ---: |
| 0 | ASCII magic `WGC1` | 4 |
| 4 | Major / minor version (u16 each, currently 1/0) | 4 |
| 8 | Header byte length (u32, exactly 132) | 4 |
| 12 | Flags (u32, currently zero; refuse any nonzero) | 4 |
| 16 | Whole-file byte length (u32) | 4 |
| 20 | CRC32 of payload bytes **from offset 132 onward** (u32) | 4 |
| 24 | SHA-256 of canonical source identity/content, **supplied by caller** | 32 |
| 56 | SHA-256 of import/generator settings, **supplied by caller** | 32 |
| 88 | Generator version (u32, nonzero) | 4 |
| 92 | Surface identifier (u32) | 4 |
| 96 | LOD identifier (signed i32, `-1` means base) | 4 |
| 100 | Source vertex count (u32) | 4 |
| 104 | Source triangle count (u32) | 4 |
| 108 | Meshlet count (u32) | 4 |
| 112 | Global vertex-reference count (u32) | 4 |
| 116 | Packed local triangle byte count (u32) | 4 |
| 120 | Maximum meshlet vertices (u32) | 4 |
| 124 | Maximum meshlet triangles (u32) | 4 |
| 128 | Reserved (u32, must be zero) | 4 |

Each 48-byte meshlet record contains four u32 fields (`vertex_offset`, `triangle_byte_offset`, `vertex_count`, `triangle_count`), then eight IEEE-754 float32 fields: `center.xyz`, `radius`, `cone_axis.xyz`, `cone_cutoff`. The triangle stream keeps meshoptimizer-compatible **local u8 vertex indices**, not raw triangle positions. Meshlet triangle-byte ranges may contain permitted gaps/padding between meshlets. This first version stores **no cluster hierarchy, boundary chains, actual vertex attribute streams, textures, material data or GPU addresses**.

## Validation gates (fail closed)

`encode_geometry_cache(source, build)` and `decode_geometry_cache(source, bytes)` share a `GeometryCacheSource` contract. This includes the original source positions and oriented index stream, separate 32-byte digests, generation, surface/LOD IDs and builder limits.

1. Cap source geometry at 750,000 vertices / 250,000 triangles, meshlets at 250,000, packed bytes at 750,000, and the cache byte buffer at **24 MiB**. Reject empty/ill-formed inputs, nonfinite positions or invalid builder limits before serializing.
2. Decode a fixed version and known header; reject unknown flags/reserved values, truncation, extension bytes and computed length mismatch **before** allocating decoded records. Avoid offset overflow by using bounded fixed record sizes and 64-bit length arithmetic.
3. Match both supplied source/settings digests, generator version, surface/LOD IDs, vertex and triangle counts, and meshlet limits against the caller's **expected** source identity. Both digest arrays must be nonzero.
4. Check the payload CRC32 for accidental corruption. CRC32 is **not** cryptographic authentication. Importantly, the codec does not calculate SHA-256 over the source: a future importer must correctly compute and supply those digests. Dummy/nonzero hashes are insufficient for real cache invalidation.
5. Independently re-run `audit_meshlets` against the original oriented source triangles. Detect lost, reversed, duplicated, out-of-range or overlapping meshlet data even when an attacker recomputes the CRC.
6. Check that all bound sphere/cone scalars are finite, radius is nonnegative, and each referenced source position (converted to float32 like the meshlet builder) fits within the stored sphere plus a small floating-point tolerance. This does **not** validate conservative cone-backface culling or dynamic-deformation bounds.

A successful decode is **offline data-contract acceptance only**. It is not a verified GPU upload, accurate occlusion result, material/shadow equivalence or crack-free cross-LOD display. Do not trust an embedded metadata flag or permit the codec to mark source assets as render-ready by itself.

## Tests actually run (2026-11-14)

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -Imodules \
  modules/worlds_geometry/geometry_cache.cpp \
  modules/worlds_geometry/meshlet_contract.cpp \
  benchmarks/native_geometry/test_geometry_cache.cpp \
  -o /tmp/worlds_geometry_cache_test
/tmp/worlds_geometry_cache_test

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer -Imodules \
  modules/worlds_geometry/geometry_cache.cpp \
  modules/worlds_geometry/meshlet_contract.cpp \
  benchmarks/native_geometry/test_geometry_cache.cpp \
  -o /tmp/worlds_geometry_cache_san
/tmp/worlds_geometry_cache_san
```

**Observed locally:** GCC strict-warning build and execution passed; Clang AddressSanitizer + UndefinedBehaviorSanitizer build and execution passed. Tests include deterministic byte round-trip, two meshlets and full exact oriented coverage, source/settings/generator/LOD mismatch, invalid source, bad bounds, reversed triangles, huge offsets and counts, wrong format/flags/version, payload checksum errors, every-byte-prefix truncation, forged-CRC corruption and **700 seeded payload mutations**. The committed new-source blobs are checked against the exact locally tested files' git-object hashes.

The tests supply **synthetic** 32-byte identity digests; this proves *comparison and invalidation rules*, **not** real SHA-256 generation or actual file-cache invalidation. No real vendor-produced meshlet payload or Godot import test has run in this milestone. The codec is included in the opt-in module via existing source glob, but a full SCons engine build has not been performed.

## Next steps

1. Implement caller-owned **canonical SHA-256 source/settings hashing** and an **atomic disk publication layer** (temp file, flush, atomic rename, and size bounds) without touching Godot import assets.
2. Execute real vendored meshoptimizer and compile the opt-in Godot module; test cached data from both `ImporterMesh` and `ArrayMesh`, including UV-split and LOD assets.
3. Expose [61's boundary extractor](61-automatic-mesh-boundary-extraction-and-cache-contract.md) through a read-only Godot diagnostic method; add transformed-border/LOD tests.
4. Extend the format in a future explicitly versioned revision to include seam/cluster ancestry provenance once proven, without mislabeling the current WGC1 contents.
5. Only then establish runtime resource ownership, fence-safe streaming, certified fallback and hardware render/quality benchmarks.

The conventional Godot renderer remains unchanged. No Unreal engine code was copied.

**Follow-on (2026-11-14):** [63 — deterministic SHA-256 and cache storage](63-geometry-source-hashing-and-cache-store.md) adds automatically calculated geometry/settings fingerprints, bounded file reads, atomic temp-file publication and regeneration on misses. The storage lifecycle was tested using a stub codec; real WGC1-plus-Godot integration remains pending.

# 44 — Splat asset foundation: first implementation milestone

**Status:** implementation-ready plan; no runtime renderer changes or GPU performance claims. Companion to [43](43-splat-source-audit-and-implementation-lessons.md). Keep ordinary Godot mesh rendering unchanged.

## Goal

Build a small **independent, optional** asset-processing and residency model before touching Godot's renderer. It must represent captured-radiance and material-aware Gaussians without losing their different semantics, validate inputs safely, and support a hard resident-byte cap.

## Milestone A: canonical records and importer validation (CPU-only)

Define a versioned canonical format with:
- Asset header: schema version, source/provenance, coordinate convention, unit scale, color space, Gaussian count, SH degree, optional attribute bitset, and immutable content identifier.
- Required Gaussian geometry: finite center (3), positive finite principal scales (3), normalized quaternion (4), bounded opacity (1), and color/SH attributes with explicit encoding.
- **Optional** material-aware payload: finite normal (3, normalized), metallic [0,1], roughness [0,1], material identity and clear interpretation of color as **albedo**, not baked captured radiance.
- Distinct shading modes: `CAPTURED_RADIANCE` (SH/radiance, no unsupported relighting promises) and `MATERIAL_AWARE` (albedo + normal + PBR properties). Explicitly reject impossible/ambiguous mode-attribute combinations.
- Optional future payloads for skeletal influences and previous-frame motion, not allocated by default.

Start with a synthetic PLY fixture and parser/validator that recognizes **both** normal 3DGS properties and Mesh2Splat's extra `nx,ny,nz,metallicFactor,roughnessFactor`. Preserve unknown fields in import metadata or emit an explicit ignored-field diagnostic. Do not blindly use one project's logit/linear opacity conventions for another. Validate header/count/stride and multiplication overflow *before allocation*.

**Tests:** standard PLY, extended PBR PLY, absent optional attributes, unknown fields, zero points, invalid quaternion, NaN/Inf, negative/zero scale, invalid opacity encoding, truncated payload, excessive counts, inconsistent SH count, coordinate-conversion roundtrip, deterministic serialization.

## Milestone B: regional representation (CPU-only)

Represent immutable `SplatAsset` and `SplatRegion`:
- stable asset ID + region ID + LOD ID + content version;
- conservative AABB and/or sphere enclosing **full Gaussian ellipsoids** at a declared support cutoff, not just centers;
- child IDs, immutable count/byte size, compressed chunk ID, dependency/fallback parent;
- explicit `CapturedRadiance` / `MaterialAware` class per asset or region;
- a resource hash so repeated scene instances share decoded/resident data while keeping independent world transforms.

Generate a tiny synthetic region hierarchy; avoid a complex offline simplifier in the first iteration. LOD errors should remain metadata until a quality metric is actually implemented and tested.

**Tests:** transformed ellipsoid bounds, parent contains children, empty/degenerate nodes, stable deterministic ordering, missing parent/cycle rejection, identical asset reused across instances, corrupt/duplicate region IDs.

## Milestone C: byte-budgeted residency state machine (CPU-only)

Use explicit states `UNLOADED -> QUEUED -> LOADING -> READY_CPU -> UPLOADING -> RESIDENT -> RETIRING -> UNLOADED`, plus `FAILED`. Every asynchronous request carries generation/version identity. Model separate CPU-decoded, GPU-resident, staging, per-view scratch and retiring allocations; **reserve before allocating**. Include a configurable hard peak budget accounting for overlap between new and old allocations.

Prioritize coarse visible fallback first, then desired detail. A request cannot remove a coarse fallback until its replacement is resident and visible. When the minimum representation cannot fit, select a conventional mesh/proxy/error fallback **without exceeding the cap**. Multiple cameras generate separate demands but share immutable asset residency. View-dependent sorting/history must never be reused across cameras.

**Tests:** strict byte cap after every transition, eviction under pressure, canceled/stale completion, retryable failure, camera teleport, two simultaneous cameras, duplicate request coalescing, reference-counted shared resources, and no resource leaks after unload.

## Milestone D: optional Godot adapter, after A–C pass

Keep a small adapter between canonical data and Godot's importer/resource APIs. No default renderer changes. Prove the adapter can import and inspect an asset, serialize/reload it, and handle missing/unsupported attributes. **Only then** prototype an opt-in rendering backend using the existing Godot RD/compositor contracts, with a fallback for unsupported GPUs/renderers.

## Non-goals in this milestone

No photographic training, mesh-to-splat GPU conversion, production PBR renderer, sparse texture streaming, skeletal animation, ray tracing, replacement of meshes, new simulation/ECS integration, or asserted FPS improvements.

## Acceptance gate

- All CPU-only tests pass on available hardware.
- The exact material fields that were lost in the Mesh2Splat → GDGS path are preserved through our canonical import roundtrip.
- Peak budget never exceeds its declared cap, including staging and retirement.
- Every region has a conservative validated bound and a defined failure/fallback.
- A handoff doc records schema versions, API boundaries, tests, known limitations and future GPU requirements.

**Recommended first code change:** implement the standalone canonical schema/PLY test fixture and its unit tests. This is the smallest meaningful proof that resolves the verified material-loss problem in [43](43-splat-source-audit-and-implementation-lessons.md).

# 36 — Texture streaming baseline audit: reuse before rebuilding

**Status:** source-confirmed baseline and original experiment design, **not** validated by a running renderer. Inspected 2026-11-13. Godot fork `master@be1999a0f532124705359e4c3dde0a3b3034a0bd` (4.8 beta); Unreal licensed fork `release@f45729c0b6f097038e72b52d366a62baeca3275b` (5.8.4). See [27 — source separation](27-license-and-independent-implementation-protocol.md).

## Important correction to the earlier plan

The Godot fork **already contains** `modules/texture_streaming/`. An independent texture-memory scheduler is **not** a blank-slate priority. Reuse and measure this module before building any new streaming manager or virtual-texture system. This also does not establish that the module is production-ready, enabled in the user's projects, or equivalent to Unreal SVT/RVT.

## Verified Godot source inventory

- `modules/texture_streaming/register_types.cpp`: module registration, engine singleton and project-setting initialization.
- `modules/texture_streaming/config.py`: module gated on RenderingDevice availability at build configuration.
- `modules/texture_streaming/texture_streaming.cpp/.h`: texture/material tracking, GPU-feedback readback, requested mip policy, memory estimates, reload scheduling and shutdown.
- `servers/rendering/renderer_rd/storage_rd/texture_storage.cpp`: conventional renderer texture resources and GPU lifetime; the precise interaction with the streaming module still needs a full call-chain audit.
- `servers/rendering/renderer_rd/storage_rd/material_storage.cpp`: audit pending to trace feedback emission and material-to-texture registration.

The inspected implementation:
1. Registers a **disabled-by-default** streaming setting. The separate memory-budget switch is also disabled by default; a configured capacity is not proof of enforced allocation limits.
2. Does not support the Compatibility renderer through its streaming start path.
3. Uses render-thread initialization and asynchronous readback of material feedback; this is distinct from blocking immediate readback.
4. Has separate processing and reload work, applies mip-quality decisions with time smoothing/decay and optional budget fitting, and invokes reload callbacks.
5. Limits reload *operations* through a configurable rate; that is not yet a proven hard bound on bytes uploaded per frame or GPU allocation spikes.
6. Represents feedback and choice at material/texture mip level. The inspected subsystem does **not itself demonstrate sparse virtual page-table texture residency** comparable to independently documented virtual texturing.
7. Exposes usage reporting and a flush pathway. These must be checked against actual GPU memory measurements before being used as truth.

No runtime execution, image-quality comparison, shader coverage confirmation, backend test, or measurement was performed.

## Unreal comparison — licensed-source waypoints, public concepts only

Authorized private-source waypoints: `Engine/Source/Runtime/RenderCore/Private/VirtualTexturing.cpp`, `Engine/Source/Runtime/Engine/Private/VT/` and virtual-texture source inventory. These are **reference locations, not implementation instructions**.

Epic's public documentation distinguishes:
- **Streaming Virtual Texturing (SVT):** prebuilt texture content loaded at demand/granularity finer than traditional full-mip decisions.
- **Runtime Virtual Texturing (RVT):** rendered/composited texels cached on demand, particularly useful for large landscapes and layered materials.

Public descriptions: [virtual texturing overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-texturing-in-unreal-engine), [streaming VT](https://dev.epicgames.com/documentation/unreal-engine/streaming-virtual-texturing-in-unreal-engine), [runtime VT](https://dev.epicgames.com/documentation/unreal-engine/runtime-virtual-texturing-in-unreal-engine).

**Inference, not proof:** virtual-texture approaches may help with large atlases, megatextures and terrain material composites that whole-mip loading handles inefficiently. Virtual page lookup, cache misses, border/seam filtering, feedback lag, fallback tiles, transcoding and authoring burden may negate gains in ordinary scenes.

## Proposed Worlds Engine experiments

| Ticket | Experiment | Baseline or failure condition | Required evidence |
| --- | --- | --- | --- |
| R-005a | Exercise existing streaming OFF/ON in a texture-heavy reproducible scene | Same camera, assets, quality threshold, backend; verify module truly activates | CPU/GPU p50/p95/p99; real VRAM; image error; texture quality delay; allocation spikes |
| R-005b | Trace feedback through renderer to reload callback and underlying texture allocation | No assumption that sampled feedback covers all material types | call-path map, missing shader paths, resource lifecycle, thread rules |
| R-005c | Stress optional budget and rate controls | Two regions larger than available VRAM, camera teleport, rapid oscillation, throttled storage | worst stalls, quality recovery time, IO bytes, upload bytes/frame, mip oscillation, eviction correctness |
| R-005d | Only if needed, prototype **independent** tiled/virtual texture lab for one static opaque surface | Existing streaming + atlas/texture-array control | page miss rate, fallback coverage, page-table cost, visible quality and latency |

Do **not** equate the module's estimated memory counter with driver-allocated bytes; compare against backend/GPU tooling. A constant ops/second cap is not a bandwidth cap. Check whether an inactive or hidden material still affects feedback expectations, and test shader/material hot reload.

## Integration and correctness invariants

- Keep normal Godot textures and materials rendering correctly if streaming is off, unsupported, backlogged or in error.
- Never unload an asset relied upon by an in-flight draw; never hide geometry merely because higher-resolution texels are late.
- Avoid starvation of a continuously visible small texture in favor of noisy large requests.
- Make camera-cut / fast traversal policy explicit; measure texture popping and anisotropic/detail loss against quality-matched controls.
- Multiple viewports share residency but do not conflate view feedback.
- Report modelled requested bytes separately from observed device allocation, staging and transient duplicates.
- Do not couple asset residency with persistent Worlds-ECS world/entity identity.

## Recommendation

**First validate and instrument the existing module**. Only implement a virtual-tile layer if a reproducible workload demonstrates material memory or streaming shortcomings that simpler Godot improvements cannot solve. Keep geometry and texture residency budgets conceptually coordinated, but do not build a central manager before the existing paths are understood.

**Source trace completed in follow-on audit:** [38 — streamed texture input-to-GPU call chain and failure tests](38-texture-streaming-end-to-end-trace-and-validation.md) verifies importer, resource loader, streaming state, material feedback, shader paths in both Forward+ **and Mobile**, asynchronous feedback, mip policy, reloading and compatible GPU texture replacement. Runtime operation, correctness under failure and performance remain unverified.

Related: [32 — proposed residency contract](32-residency-streaming-contract.md), [35 — validation](35-phase-1-validation-and-next-actions.md), [29 — architecture evidence](29-renderer-subsystem-evidence-ledger.md).

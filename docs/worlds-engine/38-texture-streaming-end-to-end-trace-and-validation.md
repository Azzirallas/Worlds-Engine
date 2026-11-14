# 38 — Godot texture streaming: end-to-end source trace and validation plan

**Status:** verified code path and prioritized test requirements, **not a running-build validation**. Audited 2026-11-13 against `Azzirallas/Worlds-Engine` `master@be1999a0f532124705359e4c3dde0a3b3034a0bd` (before benchmark-only commits). Private Unreal remains read-only (`Azzirallas/UnrealEngine`, `release@f45729c0b6f097038e72b52d366a62baeca3275b`). No source or pseudocode from Unreal is reproduced.

## Why this trace matters

Godot 4.8 already has an experimental, opt-in **mip-level** texture streaming system. The right next step is to determine its throughput, quality, memory and failure behavior before implementing a different memory architecture. The distinction between *mip streaming* and *virtual-tile residency* is essential to credible improvement claims. See [36](36-texture-streaming-baseline-audit.md) and upstream [4.8-dev5 release notes](https://godotengine.org/article/dev-snapshot-godot-4-8-dev-5/).

## Verified runtime call path (Godot source)

1. **Asset import.** `editor/import/resource_importer_streamed_texture.cpp` registers the `streamed_texture_2d` importer (display label `Texture2D Streamed`), with per-asset min/max mip overrides; import produces `.stex` variants. `scene/resources/streamed_texture.cpp` parses the `GSTF` header, validates dimensions and offsets, reads the requested mip plus lower-detail levels, and constructs an Image.
2. **Initial load + state.** `StreamedTexture2D::_load_internal` selects the initial requested mip when streaming is enabled, creates the texture through `RenderingServer`, and registers a texture state with `TextureStreaming::texture_configure_streaming`. `StreamedTexture2D` constructor consults the project setting and renderer mode. Nonstreaming path loads full detail.
3. **Renderer attachment.** `TextureStreaming::_texture_configure_streaming_impl` associates a streaming-state RID and reload callback with a normal texture RID via `texture_2d_attach_streaming_state`. `servers/rendering/renderer_rd/storage_rd/texture_storage.cpp` stores that RID with the renderer texture.
4. **Material association.** `MaterialStorage` in `servers/rendering/renderer_rd/storage_rd/material_storage.cpp` collects streaming-state RIDs from textures used by each material and registers a material-feedback RID. The association is updated when material textures change.
5. **View setup and shader feedback.** Both `forward_clustered/render_forward_clustered.cpp` **and** `forward_mobile/render_forward_mobile.cpp` associate material feedback indices with instance data and bind a feedback buffer to the render pass. Shader code in `shaders/forward_clustered/scene_forward_clustered.glsl`, `shaders/forward_mobile/scene_forward_mobile.glsl` and `shaders/scene_forward_streaming_inc.glsl` calculates UV footprint (or explicit streaming LOD) and writes per-material feedback. **Do not describe this path as Forward+-only.** Compatibility is deliberately excluded by the streaming module.
6. **Readback and policy.** `TextureStreaming` has a render-thread-managed rotating feedback-buffer pool; `_feedback_frame_done_callback_render_thread` schedules asynchronous GPU readback at a throttled interval. The processing worker converts material feedback to requested mip levels for constituent textures; `_feedback_buffer_process` applies smoothing/inactivity and optional whole-texture memory-budget fitting.
7. **Reload work.** A separate reload thread processes queued requests; `_do_texture_reload` steps mip levels (or jumps during flush) with an operations-per-second throttle, invokes the `StreamedTexture2D::texture_reload` callback, and schedules follow-up work when necessary.
8. **GPU update + stable handle.** `StreamedTexture2D::texture_reload` re-reads selected mip data, creates a new texture, calls `texture_replace_compatible`, and reattaches the streaming state. In `TextureStorage::texture_replace_compatible`, the render texture RID remains the user's stable logical handle while its underlying RenderingDevice texture resources are replaced; the code also handles proxies and dependent atlas dirtiness.

**End-to-end control loop (public-Godot-only summary):**

`StreamedTexture2D import → texture RID/state → material feedback RID → instance/shader UV demand → asynchronous GPU feedback → per-texture mip decision → asynchronous I/O callback → new GPU resource → compatible texture replacement → next frame`

The code confirms the existence of these stages. It does **not** establish the actual propagation latency, whether every material/shader mode contributes valid feedback, physical peak VRAM residency, or synchronization safety under stress.

## Confirmed features and boundaries

| Observation | Consequence for Worlds Engine |
| --- | --- |
| Experimental system is disabled by default | Runtime tests must explicitly enable it and restart editor/import as appropriate |
| Importer creates dedicated streamed textures | A benchmark using only `ImageTexture.create_from_image()` is **not** a texture-streaming benchmark |
| Feedback and replacement operate on mip levels | No evidence of fine sparse tile/page mapping in this specific path |
| Both Forward+ and Mobile shader paths exist | Run and validate both; do not assume equal behavior or hardware capability |
| Feedback is asynchronous and throttled | Measure view-change-to-quality latency and camera-cut recovery |
| Budget fitting estimates mip-size occupancy | Compare reported bytes against actual device allocation and staging/overlap |
| Reload I/O throttles by *operations*, not bytes/frame | A large mip swap may still cause spikes; instrument real upload cost |
| Shader feedback carries material-scoped information | One material sharing textures with divergent texel footprints is a stress case |

## Prioritized correctness questions (hypotheses, not confirmed bugs)

**F-01 — failed reload accounting.** The current `StreamedTexture2D::texture_reload` method updates its cached mip before attempting file/GPU creation, with an error fallback. `TextureStreaming::_do_texture_reload` invokes a void callback and records the selected mip after the call without an explicit success result. *Hypothesis:* if a read, upload or compatible replacement fails, recorded residency may disagree with actual GPU contents. **Test:** fault-inject invalid/missing stream data and renderer resource errors; compare actual visual resolution, state, retry, peak allocations and error logging. Do not patch before reproducing.

**F-02 — out-of-date feedback.** GPU readback and I/O are asynchronous; rapid camera cuts, a destroyed material/texture, or reimport can race stale demand. **Test:** churn and teleport under feedback backlog; verify no stale-RID writes, memory leaks, missing geometry, or persistent quality errors.

**F-03 — memory budget semantics.** Budget fitting is optional and uses per-mip estimates, not a reported complete driver VRAM inventory. **Test:** compare estimated residency with device allocations (including transient duplicate images, staging, shader/material buffers) and verify worst-case frame hitch.

**F-04 — feedback and material coverage.** MultiMesh, alpha cutout, ShaderMaterial/explicit `STREAMING_LOD`, triplanar, UV scaling, Mobile, editor scene switching, multiview and material hot reload may have divergent feedback. **Test:** one controlled fixture per path; report missing/unmeasured coverage instead of silently treating it as success.

**F-05 — quality under bandwidth limits.** Ops/sec throttling can delay large textures or leave newly visible assets under-detailed. **Test:** view-motion/teleport and two-region VRAM thrash, measuring visible quality vs time, age of requests and starvation.

## Reproducible texture test matrix to build next

Use two sets of original or permissively licensed high-frequency images, at least two sizes and three material classes. In the editor import each candidate via **Texture2D Streamed**, not the standard texture importer. Enable `rendering/textures/streaming/enabled` and restart the editor; test the same scene with streaming **off** and **on** at several budgets. Use Forward+ initially and then Mobile where supported. Keep the same camera, texture inputs, mesh UVs, material, lights, output resolution, driver, GPU and warming strategy.

- T0 — baseline: stream off, imported texture visible, near/far static camera, no missing pixels.
- T1 — near/far progression with regular orbit and sudden cut; record first high-quality frame and transitions.
- T2 — repeated teleport between disjoint texture sets with combined working set beyond target budget.
- T3 — shared material + different texture sizes/UV frequencies, surface alpha masks, explicit shader LOD and triplanar.
- T4 — resource lifecycle: remove texture/material, reimport file, hot-reload material while requests are pending.
- T5 — constrained budget and I/O throttling; record memory used, real GPU allocation, upload and stall costs.
- T6 — renderer variations and device fallback; unsupported features must be documented, not silently treated as successes.

A passing result requires: correct pixels and bindings after replacement; finite/credible CPU/GPU metrics; zero missed renderable surfaces; bounded memory according to an explicitly specified target; no unexplained loss of shader/material fidelity; a complete backend/environment manifest. If VRAM measurement is unavailable, memory performance is **unverified**.

## Measurement and implementation gates

Stage A: run the standalone [rendering baseline project](../../benchmarks/rendering/README.md) with nodes vs global/regional MultiMesh, fixed/orbit/cut cameras and movement mixes. This tests submission and CPU scene updates, **not streaming**, and produces raw samples validated with `validate_results.py`.

Stage B: create an actual streamed-import fixture and record estimated resident bytes, actual VRAM, streaming latency, download/upload duration, p50/p95/p99 render frame-time and texture-quality error. Do not confuse a GDScript-generated `ImageTexture` with `StreamedTexture2D`.

Stage C: decide whether improvements should target feedback fidelity, better upload budgeting, predictive prefetch, resource lifetime/fault recovery, or independent virtual-tile experiments. A virtual-texture prototype is justified only by measured deficiencies in real target scenes.

**This source audit changed one prior unknown:** streaming input-to-GPU resource replacement is now traced, and Mobile does have a feedback path. It did **not** run a device, compile shaders, or measure speedups.

Related: [36](36-texture-streaming-baseline-audit.md), [37](37-pipeline-stutter-and-pso-research.md), [35](35-phase-1-validation-and-next-actions.md), [27](27-license-and-independent-implementation-protocol.md).

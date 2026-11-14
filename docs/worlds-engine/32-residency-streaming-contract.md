# 32 — Independent resource residency, streaming and fallback contract

**Status:** original architecture proposal; **a limited CPU-only geometry-page residency reference has now been implemented in [52](52-geometry-page-residency-cpu-contract.md)**. No native GPU page residency, geometry codec, real IO or production integration has been implemented. Research context: public virtualized geometry, sparse virtual memory, texture/mesh streaming and Godot resource management. Not a translation of Unreal streaming manager.

## Existing baseline correction (2026-11-13)

The audited 4.8 beta fork already has `modules/texture_streaming/`: project settings, material feedback, asynchronous GPU readback, mip-quality requests and optional budgeting. It is disabled by default, and its runtime efficacy is unmeasured. **This document's proposed resource scheduler is not a replacement for that existing texture module.** First validate/instrument the module and only build complementary geometry/chunk management or new texture paging when measured gaps justify them. See [36](36-texture-streaming-baseline-audit.md).

## The problem

An efficient visibility system is insufficient if an object requires data not currently on the GPU. Scenes containing huge quantities of detail need predictable choices about *what stays resident*, *what is requested*, *how much can upload this frame*, and *what is drawn while data is missing*. High apparent throughput with frame spikes, blinking geometry or cache thrashing is a failure.

Primary metric: **quality within an explicit frame-time / VRAM / upload budget**, including rapid camera motion and peak stalls—not 'number of streamed pages'.

## Distinguish three states

1. **Authoritative asset:** a logical scene object or resource exists and may be in world save data. This is not equivalent to being on disk or rendered.
2. **Ready representation:** a conventional Godot mesh, coarse LOD, card, impostor or other visual substitute is available.
3. **High-detail residency:** optional chunks/assets are in RAM/GPU memory with valid dependencies and enough synchronization to be referenced.

A persistent simulation entity must not be destroyed merely because its mesh is nonresident or invisible. This rule also applies to normal Godot gameplay: streaming a renderer representation must not silently delete gameplay nodes.

## Proposed open interfaces (descriptions, not copy-paste code)

**Resource identity:** `AssetKey` is based on source asset hash + importer config + builder version + format version; `ChunkKey` adds a deterministic chunk identifier. Runtime GPU handle is separate and generation checked.

**Request:** `ResidencyIntent` records target `AssetKey`, required quality level, importance, view epoch, deadline class, and whether fallback is already visible. Requests coalesce per key and update priority rather than spawn unbounded duplicate IO.

**Resource state:** `Unavailable`, `Queued`, `Reading`, `Decoded`, `UploadPending`, `Resident`, `EvictionPending`, `Failed`. These names are an original state-machine sketch; actual concurrency details to be designed.

**Budget:** hard/soft CPU heap bytes, device heap bytes, staging bytes, max upload bytes per frame, maximum work milliseconds per frame (CPU), IO throughput cap and optional power profile. Expose watermarks and emergency policy.

**Dependency:** if a high-quality representation depends on a parent/index/texture/material resource, it cannot become drawable until dependencies exist; it must not be evicted while any submitted draw still references it.

**Feedback:** `DemandObservation` (camera/geometry request or GPU feedback) may arrive late and can be stale. Attach a view or scene epoch, and merge with independent predicted demand. GPU feedback is advisory, not infallible.

**Fallback:** conventional Godot mesh or an intentionally cheap coarse representation must be drawable before fine pages are ready. If no valid fallback exists, draw a diagnostic placeholder instead of silently dropping the object.

## State-machine rules

- Multiple cameras can request the same chunk; aggregate demand without duplicating uploads.
- A chunk may be loaded once and referenced by many visible instances.
- Eviction is legal only when no in-flight graphics work still references its GPU allocation and when a valid replacement stays available.
- A generation/epoch barrier prevents stale asynchronous completion from overwriting a newer resource rebuild.
- CPU decode and IO may run asynchronously; GPU uploads obey the device's thread/synchronization model.
- Budget exhaustion degrades fidelity in a controlled, observable way before exhausting memory or stalling the frame.
- Failed/corrupt asset: record checksum/log; return fallback; retry policy bounded. No infinite request loop.
- When camera cut makes previous demand irrelevant, requests may be reprioritized; do not invalidate reusable resident data unnecessarily.

## Request priority research

Candidate priority inputs (tunable; no proprietary formula):
- size of projected contribution and current representation error;
- certainty that an object will be visible soon;
- estimated camera travel direction/speed, teleport target;
- duration that an object has been awaiting higher detail;
- reuse benefit across cameras/instances;
- bytes and cost to load/decode/upload;
- gameplay/user-visible importance without needing Worlds-ECS.

**Aging/fairness:** low-priority resources should not starve indefinitely if steadily visible. Foreground traversal should not cause one asset to oscillate between queued and evicted states. A simple additive priority plus queue aging can be prototyped before a complex adaptive model.

## Prototype phases

**R0 — telemetry only:** run a normal Godot scene; estimate asset size, per-frame buffers and visible quality. No behavioral changes.

**R1 — synthetic residency manager:** deterministic fixed-size original data chunks loaded asynchronously into CPU RAM, with simulated GPU budget. Test queueing, cancellation, requests, eviction and generation correctness without graphics.

**R2 — upload one optional visual derivative:** low-detail always-loaded mesh and one high-detail chunk; intentionally throttle uploads and verify fallback.

**R3 — view feedback and predictive prefetch:** add request epochs, two camera paths and priority aging. Avoid blocking GPU readback.

**R4 — multi-asset, multi-material, spatial coverage and actual VRAM pressure:** publish worst-case stall/quality degradation.

**R5 — optional integration with adaptive geometry/lighting; no coupling to simulation identity.**

## Adversarial tests and acceptance

- Camera teleport to unrecently visited region, then back.
- Rapid alternation between two distant areas with total working set > memory budget.
- GPU memory at 90%+ pressure and transient allocation bursts.
- Streamed geometry and shader/material resources requested simultaneously.
- Asset hot reload while old data is still in use.
- Midstream cancellation, corrupt data, slow IO and read errors.
- Device lost or rendering context rebuild.
- Multiple viewports with different priorities.
- Moving object whose representation changes while visibility is being decided.

Track: bytes resident, bytes read, bytes uploaded, pending requests, staging occupancy, cache hit/miss, request latency p50/p95/p99, first-quality pixel delay, emergency fallback frames, eviction churn, upload CPU+GPU time, visible error and dropped-geometry count (must be zero).

## Integration candidates to inspect in open Godot

- `servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp`
- `servers/rendering/renderer_rd/storage_rd/texture_storage.cpp`
- `servers/rendering/rendering_device.cpp/.h`
- `servers/rendering/rendering_device_graph.cpp/.h`
- `scene/resources/mesh.cpp`; `ResourceLoader`/importer pipeline (precise paths and thread constraints to audit)
- Conventional scene resource lifecycle and Editor import/reimport.

## Decision

Implement **a generic measurement and budget interface** before a fully custom codec/paging system. Only make it a production Godot feature if actual resource loads or paging show reduced stutter without unacceptable memory/image regressions.

Public context: https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-technical-details ; https://github.com/zeux/meshoptimizer ; https://docs.godotengine.org/en/stable/classes/class_renderingdevice.html .

Related: [31 geometry](31-independent-virtual-geometry-design.md); [30 visibility](30-gpu-instance-visibility-design.md); [35 validation](35-phase-1-validation-and-next-actions.md).

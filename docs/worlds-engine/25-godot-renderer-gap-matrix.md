# 25 — Godot 4.8 vs Unreal 5.8.4: renderer opportunity and redundancy matrix

**Status:** source-level comparison, 2026-11-13. Not a runtime benchmark. [Unreal audit](24-unreal-5-8-rendering-architecture-audit.md); [baseline source maps](17-renderer-source-audit-res-001.md) and [MultiMesh audit](18-res-002-multimesh-and-visibility.md). Godot source reference: `Azzirallas/Worlds-Engine` at `6a8f3e91d98af788bcf7837e785b26b0500989c9`.

## Existing features to reuse—not reinvent

| Godot 4.8 source / capability | Current evidence | Decision implication |
| --- | --- | --- |
| `servers/rendering/rendering_device_graph.cpp/.h` | Dependency-aware command graph; resource tracking, command grouping and barriers | **Do not rebuild a generic render dependency graph** |
| `servers/rendering/rendering_device.cpp` | Graph command reordering enabled; indirect draw and indirect compute; BLAS/TLAS interfaces | Reuse APIs; check actual backend feature support and submission/driver limits |
| `servers/rendering/renderer_scene_cull.cpp` | A camera cull path scans `scenario->instance_data`; parallelizes above a threshold (200 in audited tree) | Measure full scene scan, cache behavior, jobs, visible fraction; GPU/hierarchy may help but not always |
| `servers/rendering/renderer_scene_cull.h` | `DynamicBVH` indexers already exist for other scene queries and related tasks | Investigate query modes and update overhead before adding another spatial tree |
| `servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp` | MultiMesh CPU cache + dirty region updates (512-instance region); per-instance mutation and full-buffer paths; aggregate AABB | Test bulk vs sparse updates, near- and long-range culling, memory and one-time readback |
| `servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp` | Forward+ render list, clustering and multi-draw indirect support for MultiMesh | A simple indirect draw is **already a baseline**, not a novel feature |
| `servers/rendering/renderer_rd/forward_mobile/render_forward_mobile.cpp` | Separate Mobile backend also emits indirect MultiMesh draws | Backend portability may be possible but must be tested |
| `servers/rendering/renderer_rd/environment/gi.cpp` | SDFGI cascades, probes, update paths | First ask whether targeted GI limits can be improved incrementally |
| Existing shadow atlas and cascades | Conventional forward shadows with atlas/light rendering paths | Benchmark before building sparse virtual shadows |
| `servers/rendering/renderer_scene_occlusion_cull.cpp` | CPU-side hierarchical depth buffer support is present | Do not claim Godot has no occlusion at all; compare scope/accuracy/cost against GPU methods |

**Source caveat:** Godot 4.8 beta is moving. The specific audit is pinned. Comments about current code are not guarantees about future Godot 4.8 final, other renderer modes or all drivers.

## Most consequential capability gaps to test

| Domain | Unreal reference concept (publicly documented) | Godot verified starting point | Likely experiment | Priority |
| --- | --- | --- | --- | --- |
| Massive visible instances | Persistent GPU scene + fine instance visibility | CPU scene cull and MultiMesh aggregation | GPU-resident instance table + compact visible list | **P0** |
| Massive fine geometry | Hierarchical virtualized clusters, streamed LOD | Mesh LOD and indirect instance drawing; no verified equivalent in audited path | Minimal independent cluster proof of concept | **P0 research** |
| Streaming stalls | GPU feedback + budgeted page residency | Resource/mesh streaming audit still needed | Residency telemetry and quality/fallback under cache pressure | **P0 research** |
| Frequent instance changes | Stable state, batched GPU update path | Dirty-region MultiMesh path with possible expensive transitions | Sparse vs bulk update matrix; stable IDs and region buffers | **P0** |
| Graph scheduling | Transient resources, pass scheduling | Existing RenderingDeviceGraph | Profile graph CPU, barriers and transient churn | P1 measurement |
| Lighting many sources | Stochastic bounded direct lighting | Clustered Forward+ lighting | Conditional many-light path vs cluster baseline | P2 |
| Dynamic GI | Multiple cached lighting representations | SDFGI, VoxelGI, SSIL | Dirty/change-driven cache invalidation and selective updates | P1/P2 |
| Dense dynamic shadows | Virtualized shadow pages and static/dynamic cache | Cascaded/atlas shadows | Single-light sparse shadow proof | P2 |
| Fast world travel | Streaming source and spatial cells | Godot scene lifecycle + user-managed streaming | Independent visual residency manager and emergency LOD | P1 |
| Dense foliage | Nanite aggregate geometry limitations | MultiMesh, normal LOD, shaders | Procedural/impostor/cluster switching based on coverage | **P1 frontier** |
| Adaptive RT geometry | Flexible ray representations | RD acceleration APIs subject to driver capabilities | Deformable proxy experiment | P3 hardware gated |

## Crucial clarification on render graphs

Earlier generic proposals to *add a render graph* were overbroad. **The audited Godot code already contains one.** `rendering_device.cpp` indicates default command reordering, while secondary command buffers were disabled in the audited tree because of unresolved vendor problems. First inspect graph behavior and profile recording/barriers, then consider narrowly scoped enhancements. A 'modernizing the render graph' initiative must identify a proven missing feature, not imply there is no graph.

## Scene representation design: a hypothesis, not a transplant

Worlds Engine could diverge from both engines by selecting geometry representations independently of standard Godot `MeshInstance3D`:
- Dense opaque surface -> cluster/virtualized representation only when better than classic LOD.
- Dense aggregate foliage -> instancing + appropriate procedural/card/LOD path.
- Tiny projected moving subject -> reduced update/representation frequency with conservative validity.
- Significant onscreen deforming subject -> conventional mesh/skinning.
- Invisible but simulated entity -> no render representation; authoritative simulation remains intact.

To keep Godot general purpose, the choice belongs to an *opt-in rendering resource/manager* or capability-driven backend; ordinary Godot nodes/scripts/resources continue working. User-facing workflows matter as much as performance.

## Platform strategy

- Initial P0 prototypes target **Vulkan compute + standard indirect operations**, with shader compilation and feature checks.
- Do not assume mesh shaders, work graphs, hardware RT or vendor-specific extensions.
- Make D3D12/Metal/Mobile/Compatibility plans explicit; fallback conventional Godot rendering until measured parity.
- An RT-dependent feature may be researched separately; do not let it gate standard rendering.
- Test both raster/compute-bound and CPU visibility-bound scenes.

## Acceptance: distinguish real wins from benchmark artifacts

- Same driver, scene, camera path, resolution, lighting, material features, quality/error bound, visibility fraction and import detail.
- Compare **CPU frame**, **GPU frame**, **P50/P95/P99**, **VRAM**, **RAM**, **GPU uploads**, **streaming worst-case stalls**, **draw/dispatch counts**, **cold-start and shader compilation**.
- A single giant MultiMesh may win draw-call count and lose culling; a GPU visibility method may win large invisible scenes and lose tiny scenes.
- A full-quality image is not equivalent to a noticeably lower-quality impostor. Report temporal popping, shadows, and pixel differences.
- Do not compare FPS across different test systems and call it an architectural speedup.

## Next read

[Experiment backlog and protocol](26-phase-1-prototype-priority-and-measurements.md). This is the recommended Phase 1 implementation order.

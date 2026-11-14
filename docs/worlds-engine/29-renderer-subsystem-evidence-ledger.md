# 29 — Render architecture evidence ledger and independent comparative audit

**Audited:** 2026-11-13. Unreal licensed fork `release@f45729c0b6f097038e72b52d366a62baeca3275b` (5.8.4); Godot fork `master@6a8f3e91d98af788bcf7837e785b26b0500989c9` (4.8 beta).

**Scope:** broad source inventory and representative entrypoint review; this is *not* a full function-by-function understanding of UE internals. The public research here captures **concepts independently explained by published docs**, plus precisely located Godot source behavior. Private UE file paths are breadcrumbs for authorized review, not a reconstruction recipe.

## Subsystem coverage table

| Concept | Restricted UE file locations reviewed (file names only) | Godot paths inspected | Finding for Worlds Engine |
| --- | --- | --- | --- |
| Frame view and scene submission | `Renderer/Private/RendererScene.cpp`, `SceneVisibility.cpp` | `servers/rendering/rendering_server_default.cpp`, `renderer_viewport.cpp`, `renderer_scene_cull.cpp` | Distinguish view management, scene candidate generation, graphics submission and effects |
| Spatial visibility | `SceneCulling/SceneCulling.cpp`, `SceneCullingRenderer.cpp`, `SceneOcclusion.cpp` | `renderer_scene_cull.cpp/.h`, `renderer_scene_occlusion_cull.cpp` | Godot has CPU occlusion and BVH infrastructure, but region/instance GPU work selection is an experiment |
| GPU instance data | `GPUScene.cpp`, `InstanceCulling/InstanceCullingContext.cpp`, `InstanceCullingManager.cpp` | `mesh_storage.cpp`, `forward_clustered/render_forward_clustered.cpp` | Persistent GPU scene / fine instance selection is the most general-purpose candidate |
| Geometry construction | `Developer/NaniteBuilder/Private/NaniteBuilder.cpp` and related builder directory | `thirdparty/meshoptimizer/`, `editor/import/3d/resource_importer_scene.cpp` | Reuse Godot's MIT meshoptimizer and import system, then independently explore advanced cluster variants |
| Geometry visibility/raster | `Renderer/Private/Nanite/NaniteCullRaster.cpp`, `NaniteShading.cpp` | `forward_clustered/render_forward_clustered.cpp`, `rendering_device.cpp` | Simple cluster GPU selection before touching shading/raster backend |
| Streaming geometry | `Engine/Private/Rendering/NaniteStreamingManager.cpp`, `NaniteResources.cpp`, `DistanceFieldStreaming.cpp` | `mesh_storage.cpp`, `texture_storage.cpp` | Add residency experiments with explicit memory, upload and fallback budgets |
| Material processing | `NaniteMaterialsSceneExtension.cpp`, `NaniteShading.cpp`, `NaniteMaterials.cpp` | `storage_rd/material_storage.cpp`, `scene_shader_forward_clustered.cpp` | Shader compatibility, permutation count and runtime editor material changes are primary adoption gates |
| Dependency graph | `RenderCore/Private/RenderGraphBuilder.cpp` | `rendering_device_graph.cpp/.h` | **Godot already has a resource-aware graph**; benchmark before extending |
| Shadows | `VirtualShadowMaps/VirtualShadowMapArray.cpp`, `VirtualShadowMapCacheManager.cpp` | `storage_rd/light_storage.cpp`, `forward_clustered/render_forward_clustered.cpp` | Compare sparse cached pages against Godot shadow atlas/cascades; defer broad replacement |
| Indirect lighting | `Lumen/LumenSceneRendering.cpp`, `LumenSurfaceCache.cpp`, `LumenRadianceCache.cpp`, `LumenScreenProbeGather.cpp` | `renderer_rd/environment/gi.cpp` | SDFGI is already present; target dynamic contribution and update scheduling |
| Many lights | `MegaLights/MegaLightsSampling.cpp`, `MegaLightsResolve.cpp` | `renderer_rd/cluster_builder_rd.cpp`, Forward+ light paths | Stochastic lighting may win only at high overlap; compare against clustering |
| Temporal image quality | `PostProcess/TemporalSuperResolution.cpp` | `forward_clustered/render_forward_clustered.cpp` (FSR2/temporal integration) | Reconstruction must be treated as first-class integration/quality requirement |
| World streaming | `Engine/Private/WorldPartition/WorldPartitionStreamingPolicy.cpp`, `WorldPartitionRuntimeSpatialHash.cpp` | scene and renderer lifecycles; detailed Godot streamer audit pending | Keep streamed visuals distinct from persistent simulation ownership |
| RT geometry | `Nanite/NaniteRayTracing.cpp` | `rendering_device.cpp/.h` BLAS/TLAS APIs | API existence does not imply supported backends or a production RT GI pipeline |

## High-confidence Godot-specific facts (audited source)

1. `servers/rendering/rendering_device_graph.cpp` tracks resource use and establishes command dependencies; the command graph is not absent. `RenderingDevice` defaults graph command reordering on in the audited tree. Godot's secondary command-buffer recording is disabled by default with a driver-compatibility comment. **Action:** separate pass compilation/record time, driver time and resource transition cost.
2. `servers/rendering/renderer_scene_cull.cpp` scans the scenario's instance-data array during camera culling and dispatches workers above `thread_cull_threshold`. `renderer_scene_cull.h` also has `DynamicBVH` indexers used for other operations. **Action:** don't claim a BVH is automatically better than linear array processing.
3. `servers/rendering/renderer_rd/storage_rd/mesh_storage.cpp` marks dirty MultiMesh regions and updates GPU buffers. In this revision the region size is 512 instances. A transition to individual per-instance manipulation can cause CPU cache materialization. **Action:** compare per-instance vs bulk mutation and cold transition.
4. `servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp` has an indirect draw path for MultiMesh and sorts render elements/LOD as part of render-list preparation. **Action:** benchmark more granular visibility, not the mere existence of indirect draw.
5. `scene/resources/mesh.cpp`, `editor/import/3d/resource_importer_scene.cpp`, and `thirdparty/meshoptimizer` establish existing mesh LOD support. Godot documentation confirms automatic import LOD and visibility ranges. **Action:** use these as strong controls.
6. `servers/rendering/renderer_rd/environment/gi.cpp` has SDFGI cascade/probe update paths. Public docs say dynamic lights are supported, but not dynamic occluders/emissive sources. **Action:** benchmark correctness as well as GPU cost before modifying GI.
7. `servers/rendering/renderer_rd/storage_rd/light_storage.cpp` implements conventional local-light shadow atlas resources. **Action:** compare a sparse-shadow prototype against realistic atlas configurations rather than assuming any virtual shadow design wins.
8. `servers/rendering/renderer_rd/cluster_builder_rd.cpp` is light clustering infrastructure, **not evidence of an existing virtualized geometry cluster renderer**.

## Additional baseline findings (2026-11-13)

9. `modules/texture_streaming/` is present in the Godot 4.8 beta fork. Source inspection confirms optional GPU/material feedback, mip-level decisions, readback/reload workers and a configurable (default-off) memory budget. **Do not mark texture streaming as wholly missing.** This is not proof of sparse virtual texture paging or a production-ready feature. See [36](36-texture-streaming-baseline-audit.md).
10. `renderer_rd/pipeline_cache_rd.cpp` and `shader_rd.cpp` implement existing pipeline/shader variant machinery. Public Godot docs describe ubershader and precompilation paths; **do not mark PSO precompilation as absent without measurement.** See [37](37-pipeline-stutter-and-pso-research.md).

## Important public cross-engine lessons

- Epic's public Nanite docs discuss fine detail, LOD, streaming, material limitations, foliage overdraw and stress from aggressive streaming/visibility.
- Epic's Virtual Shadow Maps docs discuss sparse shadow pages, temporal caching, invalidation, deforming foliage and cache visualization.
- Epic's Lumen docs explain proxy surfaces, radiance caches, screen/hardware/software ray fallbacks and quality tradeoffs.
- Epic's MegaLights docs explain fixed sample budgets and degradation under many overlapping lights.
- Khronos documents optional Vulkan mesh shaders; they do not eliminate the need for a portable compute+indirect path.
- Public Godot docs confirm MultiMesh aggregate visibility/LOD and editor import meshoptimizer behavior.

## Source pointers for public conceptual verification

- Godot internal renderer: https://docs.godotengine.org/en/4.7/engine_details/architecture/internal_rendering_architecture.html
- Godot mesh LOD: https://docs.godotengine.org/en/4.7/tutorials/3d/mesh_lod.html
- Godot occlusion: https://docs.godotengine.org/en/4.5/tutorials/3d/occlusion_culling.html
- Godot RenderingDevice: https://docs.godotengine.org/en/stable/classes/class_renderingdevice.html
- Epic Nanite overview: https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine
- Epic Nanite technical details: https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-technical-details
- Epic aggregate geometry limitations: https://dev.epicgames.com/documentation/unreal-engine/working-with-naniteenabled-content
- Epic VSM: https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine
- Epic Lumen: https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine
- Epic MegaLights: https://dev.epicgames.com/documentation/unreal-engine/megalights-in-unreal-engine
- Khronos mesh shader: https://www.khronos.org/blog/mesh-shading-for-vulkan
- meshoptimizer MIT reference: https://github.com/zeux/meshoptimizer

## Version drift

This ledger refers to **UE 5.8.4** and Godot **4.8 beta**. Public docs may change after 2026-11-13; some live Epic pages may describe 5.9. Never infer a new feature is already in the audited UE 5.8 code merely because an official newer documentation page describes it. Re-review source and changelog before claiming parity.

## Unknowns / audit work remaining

- CPU/GPU frame costs across each backend on actual test hardware; none measured.
- Actual feature capability of compute, RT and indirect for Vulkan, D3D12, Metal, Mobile.
- Full Godot shader compile/PSO and custom compositor constraints.
- Mesh compression preprocessing quality/size and ingestion with every import format.
- Terrain/vegetation deformation, animations, skinning, decals and dynamic material interactions.
- Temporal reconstruction and motion-vector correctness when rendering a new custom geometry path.
- VR/ster eo/multiview, reverse-Z/projection corner cases, lightmaps and baked GI.
- Cross-platform build/CI and editor integration.
- Legal review of any private-source-influenced production code.

The next audit should deepen those topics *from publicly supportable specifications*, with tests and clear unknowns, not publish a detailed replica of private Unreal implementation.

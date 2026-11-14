# 23 — Frontier research evidence and provenance

> Published external performance results are tied to their authors' hardware/scenes. They are not performance claims about Worlds Engine and are not proof of superior real-world game performance. Research status as of 2026-11-13.

## Research papers and primary technical sources

| Topic | Primary reference | Reported idea and relevance | Important limits to test |
| --- | --- | --- | --- |
| Deformable ray-traced geometry | AMD GPUOpen, Holger Gruen, *Ray tracing massive amounts of animated geometry using tetrahedral cages*, July 22 / updated Sept 2 2026: https://gpuopen.com/learn/ray-tracing-massive-amounts-animated-geometry/ | Animate small cages; retain shared static detailed geometry and mini-BLAS for ray traversal. Dense dynamic foliage/creatures/crowds. | Hardware RT, approximate deformation, preprocessing, quality under fast/skinned motion. |
| Large foliage RT demo | AMD GPUOpen, *How tetrahedral cages significantly reduce BVH memory usage*, Sept 17 2026: https://gpuopen.com/learn/how-tetrahedral-cages-significantly-reduce-bvh-memory-usage/ | Reports ~25k individually animated plants, ~500m selected triangles, 60+ FPS at 1080p on RX 9070 XT with ~1.7 GB BVH and ~3.3 ms update. | Highly specialized scene; not transferable to ordinary frame cost or hardware; compare under identical constraints. |
| Software rasterization of dense opaque geometry | Schütz et al., *CuRast: Cuda-Based Software Rasterization for Billions of Triangles*, Computer Graphics Forum 2026: https://onlinelibrary.wiley.com/doi/10.1111/cgf.70538 | CUDA path with real-time billions-triangle research demos; useful as a distinct primitive selection approach. | Authors explicitly note it currently scales poorly with many low-density meshes and lacks blending; CUDA is not vendor neutral. |
| Adaptively generated geometry | TU Wien research, *Real-Time Rendering Methods with Adaptive Levels of Detail for Fast Rendering of Parametric Objects on Modern GPUs*, 2026: https://www.cg.tuwien.ac.at/research/publications/2026/UNTERGUGGENBERGER-2026-ALOD/ | Parametric surfaces generate screen-appropriate detail with adaptive sample allocation and no precomputed LOD structure. | Material, asset variety, deformability, feature set, collision, integration and narrow content scope. |
| Lighting reuse across geometry LOD | NVIDIA research, Wang et al., *Real-Time Level-of-Detail Rendering with ReSTIR*, SIGGRAPH 2026: https://research.nvidia.com/labs/rtr/publication/wang2026levelofdetail/ | Surface mapping preserves spatiotemporal sample reuse across topology-changing LOD switches; relevant to representation transitions. | Assumptions about materials, geometry, temporal stability and runtime costs; paper technique not turnkey GI. |
| Learned light transport | NVIDIA research, Xu et al., *A Generalizable Light Transport 3D Embedding for Global Illumination*, SIGGRAPH 2026: https://research.nvidia.com/labs/rtr/publication/xu2026generalizable/ | Research on encoding global geometric/material relationships for learned radiance/irradiance prediction. | Model training/inference costs, generalization, dynamic scenes, temporal stability and portability. |
| Neural radiance caches | *Neural Two-Level Monte Carlo Real-Time Rendering*, Computer Graphics Forum 2025: https://onlinelibrary.wiley.com/doi/10.1111/cgf.70050 | Learned on-the-fly cache combined with a residual estimator; potentially quality/cost trade-offs for GI. | Online training, quality variance, GPU work and scene change; avoid blanket real-time assumptions. |
| GPU Work Graph scheduling | AMD GPUOpen, *GPU Work Graphs mesh nodes in Microsoft DirectX 12*, original 2024 / updated Nov 24 2025: https://gpuopen.com/learn/work_graphs_mesh_nodes/work_graphs_mesh_nodes-intro/ | GPU-driven scheduling and mesh shader nodes without repeated CPU launch. | D3D12 feature/device availability and equivalents/fallbacks on Vulkan/Metal; not a universal backend feature. |
| Recent games industry research | SIGGRAPH 2026 Advances in Real-Time Rendering in Games course: https://www.advances.realtimerendering.com/s2026/ | Primary talks/slide material about production techniques and practical constraints. | Talks may not provide open-source code, complete numbers or matching hardware. |

## External prototypes to inspect conceptually (license before use)

- Light System / former Meridian: https://github.com/usestemframework/light-system — describes Vulkan virtualized geometry with Godot importer. **Independent project self-description; functionality and benchmarks not independently verified here.**
- SealLOD: https://github.com/panthuncia/SealLOD — experimental DX12 virtualized geometry/work graph renderer. **Demonstration/research reference; not a cross-platform product or automatically suitable for adoption.**
- CuRast reference repository (linked by authors): https://github.com/m-schuetz/CuRast — CUDA research implementation; license must be checked before any code adoption.

## Additional Gaussian-splatting project and research references (reviewed 2026-11-13)

- [GDGS Godot plugin, MIT](https://github.com/ReconWorldLab/godot-gaussian-splatting): compute and raster paths, depth/mesh interop, proxy relighting, import/scene tests. Runtime 4.8 fork untested.
- [NVIDIA Vulkan Gaussian Splatting, Apache-2.0](https://github.com/nvpro-samples/vk_gaussian_splatting): raster/ray/hybrid, stochastic transparency, PBR/lighting and tool-side benchmarks. Hardware feature restrictions.
- [PlayCanvas Engine MIT](https://github.com/playcanvas/engine), [SplatTransform MIT](https://github.com/playcanvas/splat-transform), [SuperSplat MIT](https://github.com/playcanvas/supersplat): GPU sorting, spatial Streamed SOG LOD, asset conversion and editing. JS/WebGPU architecture not directly portable.
- [Spark MIT](https://github.com/sparkjsdev/spark): procedural/dynamic splats, skeletal and shader-graph animation in Three.js. Cost/quality unmeasured on target hardware.
- [Niantic SPZ MIT](https://github.com/nianticlabs/spz): versioned compressed splat interchange; format compression not equivalent to GPU residency.
- [Brush Apache-2.0](https://github.com/ArthurBrussee/brush), [gsplat Apache-2.0](https://github.com/nerfstudio-project/gsplat): portable and CUDA-focused reconstruction research respectively; offline capture separate from runtime.
- [Independent MIT Vulkan/WebGPU renderer](https://github.com/netolcc06/gaussian-splat-renderer): selectable sort/tile paths, CPU reference and validation; self-reported benchmarks require independent replication.
- [StochasticSplats ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/html/Kheradmand_StochasticSplats_Stochastic_Rasterization_for_Sorting-Free_3D_Gaussian_Splatting_ICCV_2025_paper.html) and [Mip-Splatting CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Yu_Mip-Splatting_Alias-free_3D_Gaussian_Splatting_CVPR_2024_paper.html): public research on sorting-free rendering and aliasing; neither grants blanket permission to copy arbitrary associated software or assets.
- **Restriction:** [official INRIA implementation](https://github.com/graphdeco-inria/gaussian-splatting/blob/main/LICENSE.md) is research/noncommercial under its own terms; [OpenSplat](https://github.com/WebODM/OpenSplat) is AGPL-3.0. Avoid direct incorporation into the MIT fork without appropriate permission/legal review.

Full source/license matrix and priority rationale: [41](41-gaussian-splatting-project-survey-2026.md); independent architecture and tests: [42](42-independent-hybrid-splat-rendering-architecture.md).

## Findings we should *not* overstate

1. Billion-triangle claims often concern scenes chosen to favor a technique and powerful GPUs; count alone is not a usable metric.
2. GPU-generated work is not necessarily more efficient after scheduling, compaction, extra buffers and temporal synchronization.
3. Neural models can raise quality at high cost, or introduce ghosting/instability; they are not by default faster or more correct.
4. Ray-tracing acceleration-structure APIs in Godot's source do not imply hardware RT availability across target platforms or a full real-time GI system.
5. A collection of known techniques is not a demonstrated new scientific result. **Originality and superiority must be demonstrated**, not presumed.
6. Epic/Unreal source is source-available under a restricted license; independent technique study should use publicly documented principles, not proprietary implementation copying.

## Research review template

For each new reference log: date checked, paper authors, URL, venue and year, original claim, test hardware/workload, limitations, license/source provenance, our proposed experiment and whether existing Godot source already supplies part of it.

## Candidate questions

- Could a representation selector exploit *world persistence and known change frequency* to reduce redundant work more efficiently than per-renderer heuristics?
- Could one asset representation support raster + ray + streaming with shared compressed geometry and consistent LOD?
- Could GPU-driven cluster visibility combined with temporal visibility confidence reduce work while avoiding missed newly visible objects?
- Could procedural surfaces beat both regular mesh LODs and virtualized mesh streaming for extremely repetitive game assets?
- Can light reuse remain correct through mesh-to-impostor transitions at minimal memory cost?

All are unproven research questions.

## Additional independently usable primary references (2026-11-13 audit)

- meshoptimizer source and meshlet/cluster LOD experimental APIs: https://github.com/zeux/meshoptimizer (MIT; verify bundled Godot version/attribution and stability of experimental APIs).
- Khronos Vulkan mesh shader design and portability: https://www.khronos.org/blog/mesh-shading-for-vulkan and https://github.com/KhronosGroup/Vulkan-Docs/blob/main/appendices/VK_EXT_mesh_shader.adoc.
- Godot 4.7 internal rendering architecture: https://docs.godotengine.org/en/4.7/engine_details/architecture/internal_rendering_architecture.html . Note versions differ from 4.8 beta code audited.
- Godot mesh LOD and MultiMesh LOD caveats: https://docs.godotengine.org/en/4.7/tutorials/3d/mesh_lod.html .
- Godot CPU occlusion culling: https://docs.godotengine.org/en/4.5/tutorials/3d/occlusion_culling.html .
- Godot SDFGI dynamic participation limitations: https://docs.godotengine.org/en/latest/tutorials/3d/global_illumination/using_sdfgi.html (unstable docs; confirm in code).
- Epic Nanite aggregate geometry/overdraw limitation: https://dev.epicgames.com/documentation/unreal-engine/working-with-naniteenabled-content .
- Epic detailed streaming-pool and candidate-buffer caveats: https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-technical-details .
- Epic virtual shadow-map cache invalidation and separate static caching: https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine .
- Epic MegaLights sampling budget and temporal drawbacks: https://dev.epicgames.com/documentation/unreal-engine/megalights-in-unreal-engine .
- Epic source learning and restrictions (read both): https://www.unrealengine.com/ue-on-github/ and https://www.unrealengine.com/eula/unreal .

A public source may cover newer Unreal versions than the restricted source fork. Record date/version differences and do not infer matching implementation. See [AI handoff](28-ai-research-handoff-and-implementation-map.md).

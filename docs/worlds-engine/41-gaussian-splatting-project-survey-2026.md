# 41 — Gaussian splatting: open-source project survey and integration ranking (November 2026)

**Status:** research/source-licensing review, **not a GPU benchmark**, renderer implementation, or proven product decision. Sources checked 2026-11-13. The project goal is superior visual quality and scalability in a general-purpose Godot fork, with Worlds-ECS/WorldSim optional and independent. Hardware tests currently unavailable. [42](42-independent-hybrid-splat-rendering-architecture.md) specifies the recommended independent design.

## One-paragraph conclusion

**Best starting point for Godot integration:** [ReconWorldLab GDGS](https://github.com/ReconWorldLab/godot-gaussian-splatting), MIT. **Best advanced GPU/reference testbed:** [NVIDIA Vulkan Gaussian Splatting](https://github.com/nvpro-samples/vk_gaussian_splatting), Apache-2.0. **Best large-world streaming/formats references:** [PlayCanvas Engine](https://github.com/playcanvas/engine), [splat-transform](https://github.com/playcanvas/splat-transform), [SuperSplat](https://github.com/playcanvas/supersplat), all MIT. **Best programmable animation reference:** [Spark](https://github.com/sparkjsdev/spark), MIT. **Best small isolated algorithm/quality reference:** [gaussian-splat-renderer](https://github.com/netolcc06/gaussian-splat-renderer), MIT, with CPU reference, Vulkan sort/compute/tile paths and tests. These are **rankings by relevance to our work**, not comparative rendering-speed rankings.

A hybrid *opt-in* splat representation is promising for captured landscapes, interior scans and distant scenery, but it should **not** displace dynamic physically simulated objects, traditional meshes, ordinary Godot materials or deterministic simulation ownership.

## Project matrix

| Priority/use | Project / pinned main HEAD at review | License verified | What is concretely interesting | Important boundary |
| --- | --- | --- | --- | --- |
| **A1 Godot baseline** | [GDGS](https://github.com/ReconWorldLab/godot-gaussian-splatting), `c22024b3` | MIT | Godot 4.3+ add-on, import pipeline, `GaussianSplatNode`, depth/mesh integration, two backends, limited relighting, collision-proxy generation, headless plugin tests | Godot 4.8 fork compatibility **untested**; compute and raster have different sorting/VRAM and shader properties; not a fully relightable PBR surface |
| **A1 advanced** | [NVIDIA vk_gaussian_splatting](https://github.com/nvpro-samples/vk_gaussian_splatting), `d2f60325` | Apache-2.0 | Vulkan raster, ray tracing, hybrid, unscented-transform projection, stochastic transparency, GGX materials, shadow/light research, profiling and benchmarks | NVIDIA GPU or full Vulkan 1.4 requirement; RTX/DLSS capabilities must be feature-gated; not an off-the-shelf Godot renderer |
| **A1 massive scenes** | [PlayCanvas Engine](https://github.com/playcanvas/engine), `9b219191` | MIT | Active Gaussian rendering, GPU sorting, progressively streamed spatial LOD hierarchy, splat budgets, WebGPU/WebGL fallbacks | JavaScript/WebGPU architecture needs independent adaptation to RenderingDevice and graphics backends |
| **A1 asset pipeline** | [PlayCanvas splat-transform](https://github.com/playcanvas/splat-transform), `6f642939` | MIT | Multi-format conversion, Streamed SOG LOD creation, spatial chunking, splat reordering, collision voxel output, chunk-wise processing | External authoring tool first; runtime format decoder compatibility is **not** implied |
| **A2 editor** | [SuperSplat Editor](https://github.com/playcanvas/supersplat), `b4f3b255` | MIT | Editing, inspection, optimizer, export; v3 WebGPU GPU compute editor and chunked data model | Not a runtime Godot renderer; hosted publication APIs/services are separate |
| **A2 deformables** | [Spark / World Labs](https://github.com/sparkjsdev/spark), `ffe210dc` | MIT | Dynamic splat generation, per-splat transforms, skeletal animation, editable shader graphs and mesh/splat hybrid in Three.js | WebGL/Three.js path; frame cost and animation fidelity unknown on Godot or target hardware |
| **A2 algorithms** | [netolcc06/gaussian-splat-renderer](https://github.com/netolcc06/gaussian-splat-renderer), `5abe77c8` | MIT | Four selectable methods, GPU radix/prefix-scan, Vulkan 1.3 + WebGPU, tight tile bound/packed data experiments, CPU renderer, image-diff/validation | New/small independent repository; self-reported speedups require reproduction; reference semantics/math may differ from other testbeds |
| **A2 reconstruction** | [Brush](https://github.com/ArthurBrussee/brush), `1388f74c` | Apache-2.0 | Cross-platform non-CUDA reconstruction/training with Rust/Burn/WebGPU, image masks, training-view inspection, animation viewing | Training/editor pipeline, not a drop-in Godot render pass |
| **A2 interchange** | [Niantic SPZ](https://github.com/nianticlabs/spz), `d5abdee9` | MIT | Compact splat format (authors report typically ~10x smaller than PLY), v4 independent compressed streams, C++ encode/decode | Storage compression does **not** imply GPU residency reduction or streamable hierarchical LOD |
| **A3 training** | [gsplat](https://github.com/nerfstudio-project/gsplat), `512d366b` | Apache-2.0 | CUDA-accelerated differentiable splat rasterization, training improvements, large-scene/batch/depth features | CUDA/PyTorch research dependency; not suitable as mandatory multi-vendor runtime |
| **A3 basic Godot study** | [2Retr0/GodotGaussianSplatting](https://github.com/2Retr0/GodotGaussianSplatting) | MIT | Small compute-based Godot renderer to compare against GDGS | README explicitly calls it a toy viewer; not a full engine integration |
| **A3 stochastic research** | [ubc-vision/StochasticSplats](https://github.com/ubc-vision/stochasticsplats), `b218f025` | MIT top-level license; audit bundled dependencies | ICCV 2025 OpenGL stochastic sorting-free renderer with desktop/VR modes | Monte Carlo noise/temporal costs; academic reported speedups are not Worlds Engine data |
| **A3 non-integrated training** | [WebODM/OpenSplat](https://github.com/WebODM/OpenSplat) | **AGPL-3.0** | Portable reconstruction training on CPU, AMD, NVIDIA, Apple GPU | Do not import AGPL code into our MIT-distributed engine without legal/architectural review; can study published methods separately |
| **Restricted reference** | [official INRIA 3DGS](https://github.com/graphdeco-inria/gaussian-splatting) | **Noncommercial/research** custom license | Historically significant foundational research implementation | **Do not copy, fork or incorporate code into the public Worlds Engine under its current license**; source assets/pretrained data have separate conditions |

These tags describe **provenance and task suitability**, not a full automated supply-chain audit. Before importing any permissive project: inspect all nested license headers, generated assets, dependencies, patents, NOTICE files, and the particular commit actually used. Apache-2.0 material retains its own notice/license conditions; a mixed-license repo cannot necessarily label every imported file MIT.

## Deep audit: GDGS (first-priority Godot baseline)

**Main external documentation:** [README](https://github.com/ReconWorldLab/godot-gaussian-splatting/blob/main/README.md), [architecture](https://github.com/ReconWorldLab/godot-gaussian-splatting/blob/main/docs/architecture.md), [rendering backend comparison](https://github.com/ReconWorldLab/godot-gaussian-splatting/blob/main/docs/rendering-backends.md), [relighting](https://github.com/ReconWorldLab/godot-gaussian-splatting/blob/main/docs/relighting.md).

GDGS 3.3.0 offers:
- **Compute:** GPU projection, 16×16 tile duplication and tile-depth sorting, tile-local compositing with existing Godot depth. Requires Forward+ and GPU compute; per-tile ordering is updated each frame. Plugin documentation reports around **240 bytes per splat** before variable tile/sort allocations and ~**2.8 GB for a 6M-splat example**. **Author-reported**, not our benchmark.
- **Raster:** one instanced quad per Gaussian integrated into Godot transparent pass, hardware depth test, lower encoded resource requirements: authors cite **144 bytes per splat**, plus a small sort-order texture. Threaded CPU global back-to-front order may be stale for one or two frames; Mobile and Compatibility paths are stated to work, real mobile-device coverage was in progress.
- **Mesh coexistence:** normal Godot meshes continue to draw, with backend-specific depth and blending. Compute path uses compositor and separate output, Raster the conventional transparent path.
- **Authoring:** imported `.ply`, `.compressed.ply`, `.splat`, `.sog`, glb and usdz variants, gizmos, static voxel/collision mesh generation.
- **Lighting:** lighting proxy bakes normals/AO from voxelized data, can modulate captured splat radiance with up to eight movable scene lights and cast shadows onto regular Godot geometry. Splats do **not** become ordinary physically based materials; baked-in shadows/reflections cannot be removed. Authors report +4.7% one-light frame-time increase in an example scene (self-reported).
- **Tests:** headless import/smoke, sorter/packing, backend selector, voxelization/lighting bake, plus visual A/B fixtures.

**Crucial format mismatch:** current GDGS docs support **SOG version 2 archives**; current PlayCanvas tools can emit newer SOG v3 / **Streamed SOG `lod-meta.json`** and SPZ v4. GDGS lists no native SPZ importer in its documented format list. Never assume these assets load directly; investigate formats and conversion in a standalone test. Do not embed a random third-party decoder in the core engine without license/format conformance checks.

**Integration posture:** validate plugin in a **separate benchmark Godot project first**. If needed, implement a minimal optional module or GDExtension-compatible adapter only after source, memory and renderer-interface constraints are understood. Do not merge plugin into the Godot engine root or overwrite regular project behavior merely because it is MIT.

## Advanced graphics: NVIDIA Vulkan testbed

Public [README](https://github.com/nvpro-samples/vk_gaussian_splatting) and project [technical documentation](https://nvpro-samples.github.io/vk_gaussian_splatting/). Project describes multiple interchangeable 3DGS raster, ray, unscented and hybrid pipelines. Its June/September 2026 releases document GGX metallic-roughness materials, environment lighting, shadows, improved stochastic transparency, billboard ray tracing, headless benchmark paths and asset support.

**Questions relevant to our engine:**
- Can splats participate in physically meaningful lighting and shadows while preserving consistent normal/roughness/depth and regular-mesh compatibility?
- How much do exact/approximate transparency, ray tracing and hybrid representations trade image error for VRAM and frame latency?
- What is a correct fallback on non-RTX / non-RT GPUs, including older AMD cards and Mobile/Compatibility backends?
- Can our existing RD graph represent the required passes and synchronization without a Vulkan-only renderer rewrite?

**Avoid conflating project screenshots, vendor benchmark performance, or author demos with engine-portable performance.** NVIDIA-specific features should not become mandatory for ordinary Godot games. The project is Apache-2.0 but additional dependencies/assets have their own notices.

## Large worlds and authoring: PlayCanvas ecosystem

Sources: [PlayCanvas Engine](https://github.com/playcanvas/engine), [Streamed SOG user guide](https://github.com/playcanvas/developer-site/blob/main/docs/user-manual/gaussian-splatting/building/lod-streaming.md), [splat-transform](https://github.com/playcanvas/splat-transform), [SuperSplat v3 launch](https://github.com/playcanvas/blog/blob/main/blog/2026-09-09-new-in-supersplat-editor-3-0-rebuilt-on-webgpu.md).

- **Streamed SOG:** pre-generate multi-level splat assets, organize spatial tree chunks, progressively load by view/LOD and respect a global splat budget. This is a strong design reference for our world-scale visual assets.
- **Production metadata:** root hierarchy, chunk identity, compressed payload URL/path, bounding region, per-level error/quality/cost, spatial coherence. Our own runtime schema must be defined independently, keep conventional mesh fallback, and bound CPU IO, VRAM, staging and per-view requests.
- **GPU sorting:** PlayCanvas release notes discuss GPU radix sorting, fallback to CPU on storage limits and alpha/sampling enhancements; evaluate portable compute vs CPU approaches for our hardware.
- **SuperSplat 3.0:** September 2026 WebGPU editor rework moved projection, selection, sorting and frame work to GPU; published author numbers show large **JavaScript heap** reductions at 4.4M splats. These are editor memory improvements, not runtime GPU VRAM or Godot numbers.
- **splat-transform:** interoperates with many formats and creates multi-LOD Streamed SOG; also supports export of collision voxels and chunk/lazy processing. Prefer treating it as an optional **external conversion/authoring tool** before incorporating any runtime code.

## Dynamic behavior: Spark

[World Labs Spark](https://github.com/sparkjsdev/spark) uses Three.js and an original programmable system for splat transformation and creation. Features stated by maintainers include GPU graph operations, per-splat animation/displacement, skeletal animation and multi-object hybrid composition. This is a useful **dynamic splat research reference**, not proof that captured people can match the skeletal material/lighting semantics of a full Godot NPC.

Research cases: a distant walking crowd, waving bushes, animated environmental ornaments, locally displaced impostors. Compare deformable splats with ordinary skinned meshes, texture cards and MultiMesh at **equivalent apparent quality and motion history**; preserve deterministic ECS-owned positions and transitions.

## Small independent performance/reference implementation

[netolcc06/gaussian-splat-renderer](https://github.com/netolcc06/gaussian-splat-renderer) has:
- Vulkan 1.3 C++20 and WebGPU implementations;
- a CPU-sort/splat-quad path, GPU-sort with indirect drawing, tile compute raster and point-cloud debug;
- packed FP16/8-bit experiments, tile-bounds optimization, per-Gaussian SH and splat order quality methods;
- synthetic scene generators, CPU reference, PSNR/image-diff, CTest and graphics validation hooks.

Maintainer-reported RTX 4060 Laptop numbers for 1080p benchmark scenes (e.g., compute tiles with tight bounds significantly faster than baseline quads) are **self-reported and not replicated**. This is a good *algorithmic sandbox*, not automatically the fastest renderer, and a tiny/new repo should be manually audited for correctness and dependency provenance.

## Standard mesh → Gaussian conversion (source verified, 2026-11-13)

**[Electronic Arts SEED Mesh2Splat](https://github.com/electronicarts/mesh2splat)** directly converts textured `.glb` triangle meshes into Gaussian-splat `.ply`, using surface geometry/normal/UV and material maps instead of image-capture optimization. Its converter supports diffuse, metallic-roughness and normal maps; its demonstration renderer includes PBR lighting, shadows and depth visualization. Authors report sub-millisecond conversion averages in their tested workloads; **these are not verified for Godot or our hardware**. This is especially relevant to an optional import-time representation chooser: *mesh source → conventional mesh fallback + Gaussian derivative*. The conversion does not manufacture extra original geometric detail and does not imply lower frame cost or VRAM.

**License caution:** repository `LICENSE.txt` contains an EA permissive-style redistribution license with extra trademark/mark clauses; `CITATION.cff` separately declares MIT. **Treat the discrepancy as unresolved** and confirm applicable terms and third-party asset licenses before incorporating any code. Concepts can be independently implemented without importing code. The project has a restriction/limitation note for nontriangle volumetric/hair/grass/foliage content. Source/version and outputs must be independently reviewed before adapting it to Godot's renderer.

A second, slower approach is to render a conventional model from many calibrated views and optimize Gaussians photometrically; this can fit a view-dependent baked appearance at a substantial offline computation cost. Compare these workflows against simple geometric surface splatting, and do not confuse a baked appearance capture with fully relightable material splats. Blender 5.3's initial native splat support is import/render-centric, not a general native mesh-to-3DGS converter. [Blender developer status](https://code.blender.org/2026/10/splatting-the-gaussians-into-blender/).

## Other useful components

- [Niantic SPZ](https://github.com/nianticlabs/spz): compact format, **v4 independently compressed attribute streams** with ZSTD and extension records. Compressing a file more does not necessarily reduce runtime sort buffers or make it incrementally renderable.
- [Brush](https://github.com/ArthurBrussee/brush): portable Rust/Burn/WebGPU reconstruction/training and viewer, including masks and some 4D/animation viewing. Useful for independently acquired reference assets and GPU-neutral *training* research.
- [gsplat](https://github.com/nerfstudio-project/gsplat): serious differentiable CUDA library and training research; keep offline workflows optional, not required in the renderer.
- [StochasticSplats paper](https://openaccess.thecvf.com/content/ICCV2025/html/Kheradmand_StochasticSplats_Stochastic_Rasterization_for_Sorting-Free_3D_Gaussian_Splatting_ICCV_2025_paper.html): sort-free stochastic alternative, with authors reporting >4× speed under their particular quality/workload; evaluate temporal noise/denoising and loss of fidelity in our conditions.
- [Mip-Splatting paper](https://openaccess.thecvf.com/content/CVPR2024/html/Yu_Mip-Splatting_Alias-free_3D_Gaussian_Splatting_CVPR_2024_paper.html): addresses aliasing under changing resolution/zoom; temporal quality is as important as raw splat/s count.

## Explicit reject / deferred criteria

- **Not integrate by default:** official INRIA code (research/noncommercial), AGPL OpenSplat training code, CUDA-only training as engine runtime, Vulkan-RT-only rendering, large binary demo assets without asset copyright/license evidence.
- **Not claim:** all splats are relightable; collision follows from splats; more Gaussians necessarily yield higher-quality visuals; compression makes sorting free; SPZ/SOG interoperability; browser JS timings predict Godot C++ GPU behavior.
- **Not replace:** dynamic physically simulated meshes, standard scene nodes, Godot material/pipeline rendering or Worlds-ECS entity identities.
- **Keep separate:** runtime renderer, offline reconstruction, authoring/conversion, codecs, native test harness and legal provenance.

## Recommended order of investigation (without hardware)

**A — Source and contracts:** audit GDGS imports and two backend passes, identify its compositor/depth attachments, resource lifetime/VRAM, multi-scene behavior and sorting implications. Source code can establish correctness obligations even without benchmark.

**B — Formats/streaming:** trace PlayCanvas `lod-meta.json`, SOG variant versions, SPZ v4 and GDGS importer. Propose a versioned, limits-checked common `WorldsSplatAsset` interface with converters kept offline.

**C — Algorithms:** use NVIDIA and MIT independent renderer to document reference quality/sort/compute/raster fallback alternatives. Add analytical CPU-only bounds, cull/LOD/residency state tests if useful.

**D — Temporal/light contract:** evaluate motion vectors, sorting pop, view cut, aliasing, depth convention, PBR/shadows and splat-to-mesh transitions based on [40](40-representation-continuity-and-2026-rendering-research.md). Defer actual integration until an opt-in test demonstrates parity.

**E — Hardware eventually:** compare good mesh/atlas/cluster/impostor controls with GDGS compute/raster and streamed low-res/high-res splats, with fixed GPU/memory/quality/camera sequence. Report p50/p95/p99, VRAM peak, IO, sorting overhead, alpha overdraw, silhouette/depth error, ghosting and lighting mismatch.

A renderer's published popularity or FPS is **not** a comparative measurement under shared conditions. We will make a final implementation decision only when the target hardware and backend have been tested.

**Source separation:** public permissive projects may permit implementation reuse with notices and dependency review. Unreal's authorized private fork remains reference-only and must not be copied into public Worlds-Engine. See [27](27-license-and-independent-implementation-protocol.md).

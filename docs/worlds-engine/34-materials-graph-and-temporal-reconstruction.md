# 34 — Material compatibility, render graph and temporal reconstruction: renderer integration traps

**Status:** research and proposed engineering contracts. No implementation. The purpose is to stop apparently fast demos from becoming incompatible with real Godot scenes.

## Why rendering-system details matter

A custom renderer that draws only untextured opaque cubes may greatly improve draw counts but break Godot scenes with real materials, lights, shadows, alpha masking, decals, animation, motion blur, TAA/upscaling, multiple viewports and editor selection. The feature is not ready for integration until its limits are explicit and fallbacks are reliable.

Unreal has separate source subsystems for rendering scene data, material binning, raster, temporal reconstruction and cache management. We can study this separation **as an architectural lesson** using publicly described concepts; not reuse restricted shader code.

## Shader pipeline baseline correction

Godot already has shader/pipeline caching and documented ubershader/precompilation paths. A new geometry path must measure *cold first-use* compilation, hot reload and pipeline variant growth, rather than assuming a new PSO cache is needed. [37](37-pipeline-stutter-and-pso-research.md) defines the specific test matrix.

## M1: standard Godot material contract

The standard `MeshInstance3D` and surface/material resource workflow must continue to work. New optional geometry/visibility modes require:
- material compatibility matrix, listing supported opaque, alpha-mask, transparent/blended, double-sided, skinning and vertex-displacement modes;
- material parameters and resource lifetimes that update without stale GPU records;
- consistent UV/normal/tangent/vertex color semantics;
- correct depth, color, motion and optional shadow outputs;
- shader parameter changes and editor live reload;
- shader compile variants counted and capped;
- a fallback to Godot's normal shader for every unsupported condition, rather than silent visual loss.

**Initial opt-in test:** one built-in StandardMaterial3D and one minimal ShaderMaterial, both unlit and PBR variants as appropriate; verify base color, normals, roughness, emission, alpha and two-sided behavior on supported implementation tiers.

**Public Godot starting paths:** `servers/rendering/renderer_rd/storage_rd/material_storage.cpp`, `renderer_rd/forward_clustered/scene_shader_forward_clustered.cpp`, `scene/resources/material.cpp`.

## M2: material work partitioning

Separating geometry visibility from material shading could allow expensive materials to be evaluated only where final pixels need them. But the approach increases intermediate resources, changes derivative and shading semantics, affects transparency and complicates hardware MSAA.

Independent research stages:
1. Use standard Godot raster/PBR and measure how much frame time is actually shader-bound.
2. If needed, experiment with a minimal *visibility identifier* buffer for one opaque material; retain conventional G-buffer/depth or forward output for comparison.
3. Validate correct UV gradients, anisotropy/normal maps, alpha coverage, sample count and depth edges.
4. Add distinct materials and group/bucket work; track unique pipelines and texture binds.
5. Evaluate whether GPU material regrouping offsets its dispatch, memory and shader variants cost.
6. Opaque only until evidence justifies transparent rendering changes.

This is not a plan to copy Nanite shading bin structures or its shaders.

## G1: RenderingDeviceGraph first, not a second RDG

Godot 4.8 beta code:
- `servers/rendering/rendering_device.cpp`: draw/compute/indirect dispatch, render command graph controls, resource submission, BLAS/TLAS interfaces.
- `servers/rendering/rendering_device_graph.cpp/.h`: resource dependency tracking, scheduling/reordering, grouped barriers and command execution.
- `servers/rendering/renderer_rd/renderer_scene_render_rd.cpp`: scene rendering entrypoints.
- `servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp`: existing pass order.
- `servers/rendering/renderer_rd/forward_mobile/render_forward_mobile.cpp`: separate backend path.

**Experiment:** instrument the existing graph's host-side build/submit and GPU execution timings under representative pass counts (single pass, many small compute passes, mixed framebuffer/compute, indirect buffer producer/consumer). Validate:
- resource tracking when compute fills indirect draw arguments;
- correct read/write barriers across pass transitions;
- lifetime of transient and persistent buffers;
- render thread ownership and nested recording restrictions;
- asynchronous dispatch only on independently verified backend configurations;
- graph overhead and shader cache/PSO creation vs work saved.

The audited Godot code explicitly disables secondary command buffers per frame by default due to vendor concerns. Do not casually enable it in the engine as a performance flag.

## T1: motion vectors and temporal validity

Any custom geometry route must eventually supply motion and depth consistently to temporal anti-aliasing, upscaling, reflections, occlusion and shadow denoising. **A static screenshot or FPS-only benchmark cannot validate temporal rendering.**

Independent temporal contract:
- track current and prior object transforms (or mark history invalid);
- derive per-pixel motion from actual raster-visible surface, not merely object origin in deforming cases;
- include camera jitter/projection and origin rebasing;
- explicitly mark disocclusion, geometry LOD changes, representation swaps and camera cuts;
- protect alpha-masked foliage and small/high-contrast moving objects against persistent trailing;
- invalidate history on resolution/viewport changes and renderer mode switches;
- do not reuse view history between unrelated cameras.

**Tests:** moving thin poles, fine grass, detailed wire mesh, a rotating reflective material, emissive moving surface, camera teleport, rapid strafing, perspective/orthographic switches, sudden full-resolution change and split-screen.

**Measures:** pixel error over frame sequences, ghosting/blur persistence, shimmer, stability of moving edges, occlusion mismatch, CPU/GPU cost and history memory.

## T2: progressive quality under camera movement

A geometry representation switch can affect:
- visible silhouettes and normals;
- depth and motion vectors;
- shadow casters;
- indirect lighting/radiance caches;
- reflections and ray tracing proxies.

A future `RepresentationEpoch` (proposed) should allow relevant effect caches to know geometry content changed. Avoid invalidating all effects globally whenever LOD changes; identify per-effect dependencies and quantify whether the invalidations erase savings.

## B1: backend feature matrix

| Backend | First experimental promise | Must test |
| --- | --- | --- |
| Vulkan Forward+ | RenderingDevice compute + indirect if supported by current build | buffer binding limits, synchronization, shader features, large buffers, drivers |
| D3D12 | Possible with proper Godot support, not assumed | binding API, shader compilation, indirect semantics and barriers |
| Metal | Possible with native compatible feature path, not assumed | buffer alignment, command encoding, indirect restrictions |
| Mobile | Normal Godot fallback first | GPU cost, thermal memory, shader features, power |
| Compatibility/headless | **Not a valid compute-rendering target** | conventional fallback or non-render test, no fake GPU timings |

Never infer portability solely because a RenderingDevice method appears in a C++ header.

## Handoff: release-blocking issues before a new renderer path is default

- [ ] Full feature fallback table
- [ ] Material/shader consistency test scenes
- [ ] Motion vector and temporal history correctness
- [ ] Shadow/depth and GI contribution verification
- [ ] High and low-quality GPUs compared on same asset set
- [ ] Editor live update, reimport and resource reload
- [ ] Multi-view/VR support or documented opt-out
- [ ] GPU synchronization and buffer lifetime validation
- [ ] Profiling of compilation and first-run stalls
- [ ] Shader source licensing and attribution

Public references: https://docs.godotengine.org/en/stable/classes/class_renderingdevice.html ; https://docs.godotengine.org/en/4.7/engine_details/architecture/internal_rendering_architecture.html ; https://dev.epicgames.com/documentation/unreal-engine/render-dependency-graph-in-unreal-engine ; https://www.khronos.org/blog/mesh-shading-for-vulkan .

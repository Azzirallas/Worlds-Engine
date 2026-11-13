# 05 — Rendering, geometry and visibility

## Objective

Draw visually rich, dense worlds with lower CPU submissions, controlled memory and stable frametimes. A million simulated objects is not a million visible draw calls. Compare alternative pipelines at equivalent visual quality and camera paths.

## Existing tools and constraints

Godot provides Forward+, Mobile and Compatibility renderers; RenderingDevice-backed drivers; RenderingServer; MultiMesh; mesh LOD and visibility/occlusion controls. MultiMesh can batch many instances efficiently, but culling normally occurs for a MultiMesh as a group rather than for individual instances. Spatially dividing MultiMeshes is therefore an important baseline.

Do not propose GPU-driven rendering as though Godot had no instancing or culling. First measure CPU submissions, visible triangle counts, overdraw, upload bandwidth, synchronization and GPU occupancy.

## Research tracks

### R1 — Batch-friendly world instances (near-term)

- Compare SceneTree MeshInstance3D, direct RenderingServer instances, region-bounded MultiMeshes and custom batched representations.
- Group by region, geometry, material, visibility and update cadence.
- Profile add/remove, scattered updates, bulk transform writes, moving lights, shadows and dynamic materials.
- Avoid rebuilding entire batches for a handful of changed entities.
- Reuse Godot assets and editor authoring wherever possible.
- Prove efficiency in both static vegetation and dynamically moving crowds.

### R2 — Better culling (near-to-mid-term)

- Understand current software occlusion, bounds updates, frustum culling and existing visibility ranges.
- Evaluate hierarchical CPU culling and potential GPU culling using depth pyramids / instance bounds.
- Consider per-instance or per-cluster culling for batches and GPU-computed visible lists.
- Document temporal lag, conservative bounds, moving occluders and camera teleports.
- Require correctness tests for no missing objects or popping at normal motion.

### R3 — Virtualized geometry / meshlet pipeline (longer-term)

An investigation into cluster/meshlet representations, offline or import-time preprocessing, hierarchical error metrics, compact GPU buffers, visibility-driven cluster selection, indirect draws, page streaming and fallback regular meshes.

**A meshlet pipeline is not automatically Nanite.** The hard issues are asset processing, dynamic deformation, material compatibility, GPU scheduling, shadow passes, streaming, platform support and debugging.

Proof of concept before productization:
1. One static densely detailed scene.
2. GPU-side visible-cluster generation and drawing.
3. Quantified CPU cost, GPU cost, memory use and visual error against standard LOD.
4. Multiple materials and shadow passes.
5. Streaming under movement and teleport.
6. Progressive support for dynamic instances and animation only if feasible.

### R4 — Geometry residency and textures

- Separate visibility selection from loading/residency decisions.
- Consider geometry page and texture mip streaming budgets.
- Measure shader compilation stutters, GPU upload stalls and fragmentation.
- Improve material/shader variant management rather than multiplying draw paths.
- Investigate virtual texturing only if texture residency measurements warrant it.

### R5 — Animation density

- Compare native animation systems and skinning paths.
- Investigate shared animation state, update-rate LOD, far-distance impostors, GPU skinning/compute and pose caching.
- Preserve skeletal animation quality and event correctness for close characters.
- Do not run full bone rigs for offscreen or negligible-on-screen entities.

## Fallback and compatibility

- Standard meshes and render methods must remain valid.
- Advanced geometry should degrade to imported LOD meshes if GPU features are absent.
- Preserve correct shadowing/material behavior or explicitly document exceptions.
- Support at least the baseline desktop renderer before considering mobile; never silently break Compatibility renderer.

## Measurement scenarios

Dense forest; wide outdoor terrain; constrained city street with occluders; interior; rapidly moving camera; 1k/10k/100k batched transforms; mixed static/dynamic geometry; character crowd with animated near and far tiers. Collect P50/P95/P99 CPU+GPU frametimes, visible geometry, draw/dispatch counts, upload bytes, residency and memory peaks.

## Decisions deferred

Do not select mesh shaders, meshlets, virtual texturing or a wholly new renderer until the compatibility and benchmark review.
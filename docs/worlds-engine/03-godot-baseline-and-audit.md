# 03 — Godot baseline and architecture audit

> This is a preliminary source-and-documentation inventory, not an exhaustive code-level audit or benchmark.

## Fork snapshot

- Repository: https://github.com/Azzirallas/Worlds-Engine
- Inspected on: 2026-11-13
- Branch at inspection: master
- Inspected head: 960f4db5be16e2f1f7b46f9db7c824c2e0af1035
- version.py at inspection: major 4, minor 8, patch 0, status beta.
- modules/jolt_physics/SCsub exists, so Jolt is integrated in the source tree. Runtime defaults and exact versions still need verification.
- Standard upstream source folders remain: core/, scene/, servers/, drivers/, modules/, editor/, platform/, tests/, thirdparty/ and doc/.
- The top-level README is upstream Godot's description; the Worlds-specific documentation is kept separate under docs/worlds-engine/.

**Important:** 4.8 beta does not imply a finalized 4.8 release, and this inspection does not prove what is compiled or enabled at runtime.

## Existing capabilities to build on

| Domain | Upstream capability already documented | What requires verification |
| --- | --- | --- |
| Rendering | Forward+, Mobile and Compatibility rendering paths | Fork-specific changes and exact feature support on target drivers |
| GPU abstraction | RenderingDevice for Forward+/Mobile; Vulkan/D3D12/Metal pathways | Backend behavior, GPU timelines, indirect draw and compute capabilities per driver |
| Instancing | MultiMesh and RenderingServer APIs | CPU upload cost, grouping, culling, material/light constraints, practical counts |
| Culling | Frustum/visibility mechanisms and occlusion culling | CPU cost, scenes where it wins, dynamic occluder limitations |
| Mesh detail | Imported/generated mesh LOD support | LOD generation quality, transitions, streaming and geometric density limits |
| Lighting | Built-in GI, shadows, reflections and post-processing options | Current 4.8 behavior and actual quality/performance trade-offs |
| Physics | GodotPhysics3D and Jolt source integration | Default project settings, performance/correctness by workload |
| Precision | Double-precision build option for large worlds | Compatibility, CPU/memory overhead, shader caveats and origin-rebasing needs |
| Parallel work | Worker threads, servers, threaded resource loading | Thread-safety boundaries, stalls and ownership rules |
| Authoring | Editor, scenes, resources, importers, scripting | Plugin and existing-project regressions |

**Avoid duplicating capabilities already provided by Godot.** A feature only becomes a development candidate if a measured or demonstrated gap remains.

## Initial source inspection map

- Rendering server interfaces: servers/rendering/
- Renderer implementations and rendering storage: servers/rendering/ and drivers/
- Shader and RenderingDevice details: servers/rendering/ and drivers/
- Scene objects and spatial indexing: scene/3d/, scene/resources/
- Physics abstraction: servers/physics_server_3d.*, modules/godot_physics_3d/, modules/jolt_physics/
- Worker infrastructure: core/object/, core/os/, core/templates/ and associated implementation files
- Import tooling and UI: editor/, modules/
- Testing: tests/, plus any module-local tests

Paths are navigational hints, not assertions about particular class signatures. Confirm on the exact commit before citing methods.

## Required audit artifacts

For each subsystem create an audit entry with: upstream version/commit; relevant source entry points; supported APIs and behavior; measured baseline; bottleneck hypothesis; alternatives (including no change); affected platforms; implementation cost; safety and compatibility risk; proof needed before coding.

Audit priority:
1. Frame composition (CPU vs GPU vs streaming stalls).
2. SceneTree/RenderingServer/MultiMesh instancing overhead.
3. Visibility and geometry LOD for broad/open terrain and dense cities.
4. Streaming, asynchronous imports and GPU residency.
5. Physics broadphase, sleeping, collision queries and destruction.
6. Lighting quality/cost and temporal artifacts.
7. Editor stability, feature flags and export regressions.

## Initial research references

- Godot rendering overview: https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html
- Internal rendering architecture: https://docs.godotengine.org/en/latest/engine_details/architecture/internal_rendering_architecture.html
- MultiMesh optimization: https://docs.godotengine.org/en/stable/tutorials/performance/using_multimesh.html
- Occlusion culling: https://docs.godotengine.org/en/stable/tutorials/3d/occlusion_culling.html
- Thread-safe APIs: https://docs.godotengine.org/en/stable/tutorials/performance/thread_safe_apis.html
- Large-world coordinates: https://docs.godotengine.org/en/stable/tutorials/physics/large_world_coordinates.html
- Jolt project setting reference: https://docs.godotengine.org/en/stable/classes/class_projectsettings.html
- Official release archive: https://godotengine.org/download/archive/

Documentation is a changing reference; pin a version for any implementation-specific claim.
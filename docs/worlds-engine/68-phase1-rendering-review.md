# Worlds Engine — Phase 1 rendering review and continuation

**Date:** 2026-11-17  
**Scope:** `Azzirallas/Worlds-Engine` Godot fork, especially offline geometry and Phase 1 rendering research.  
**Reference revision before this change:** `875dfee3127a11ffe31e3ed9651c3db2be8cb163`.  
**Status language:** *implemented* means source exists; *tested* describes an actually executed gate; *proposed* has no accepted implementation yet. The true meshoptimizer/WGC1 vendor-linked binary, native Godot module, real imported model tests, and GPU benchmarks have **not** passed and must not be reported as passed.

## Executive conclusion

The project has a sensible research-to-implementation architecture: keep Godot's conventional rendering stable, build opt-in geometry preparation separately, and require independent verification of source triangles before reusing derived data. Code now exists for surface preparation, meshlet generation with meshoptimizer, independent coverage auditing, boundary inspection, portable WGC1 serialization, SHA-256 source/settings identity, disk cache handling, and a Godot script-level bridge. The work is **not yet a production GPU renderer**, not a virtualized geometry hierarchy, and not benchmark evidence of higher framerate or fidelity. The immediate bottleneck is integrated validation and the fact that source/import provenance remains partially caller-provided.

This continuation introduces a conservative and measurable CPU-path fix: **boundary extraction is now explicitly opt-in**, rather than automatically performed before every WGC1 lookup. Successful meshlet coverage, bounds, provenance, checksum and source matching are still mandatory; boundary topology is a separate optional diagnostic. This reduces redundant diagnostic work without turning cache acceptance into a blind trust operation. A mocked-dependency regression compiled and ran with strict GCC and Clang ASan+UBSan against the exact new pipeline source (SHA-1 verified). The real-vendor and Godot gates remain pending.

---

## 1. What has been done?

### Project architecture and prior research

- Selected a Godot-derived engine while retaining familiar Node, scene, resource, editor, GDScript and C# behavior. Conventional rendering is the default/fallback; experimental work is opt-in behind module/capability boundaries.
- Audited Godot rendering and published approaches from Unreal, meshoptimizer, GPU culling, streaming, splat representations and GPU lifetime contracts. Important distinction: research and CPU policy reference models do not establish a working renderer.
- Created CPU reference models for instance visibility/identity, guarded indirect submission, upload lifetimes/epochs, residency and whole-asset LOD error policies. These remain isolated from a production render driver.

### Geometry preparation sequence (milestones 57–67)

| Area | Implemented capability | Evidence and caveat |
| --- | --- | --- |
| Indexed triangle topology | CPU index, orientation, degeneracy and edge diagnostic audits | Portable standalone suites run; Godot engine build not validated |
| Spatial border comparison | Exact-position seam diagnostics and oriented boundary-chain extraction | Standalone verification; not crack-free LOD proof |
| Mesh/ImporterMesh surface adapter | Reads original surfaces, base geometry and stored LOD index streams | Script-facing source added; full Godot compilation/headless execution pending |
| Meshlet construction | Uses vendored meshoptimizer, independently checks an exact oriented triangle multiset | Independent contract tested; vendor-linked end-to-end run pending |
| WGC1 cache format | Versioned bounded little-endian meshlet records, offsets, CRC32, provenance and bounds checks | Standalone codec test; not yet validated as a full Godot import path |
| SHA-256 asset identity | Deterministic hash over positions, oriented indices, source identity, import/generator settings | Native known-vector tests passed; input dependencies still caller-supplied |
| Disk cache | Bounded reads, hit/rebuild/fallback, exclusive temp publication, atomic rename | Isolated filesystem tests used a test-double codec; Windows and real vendor integration untested |
| Offline pipeline | Surface preparation → optional diagnostics → meshlet generation/cache → explicit statuses | Mock-backed C++ control tests passed; opt-in Godot bridge not built |
| Meshlet storage compaction | Removes unused vendor scratch capacity after independent verification, before WGC1 | 900 randomized standalone multi-meshlet tests passed; real vendor execution pending |

### This continuation: eliminate unnecessary border extraction (milestone 68)

**Problem:** `prepare_offline_geometry` was running `extract_mesh_boundaries` unconditionally **before** determining whether a WGC1 cache already contained a verified meshlet partition. Boundary extraction walks mesh geometry and allocates diagnostic data. The result is not needed to validate the independent oriented triangle partition, codec bounds or cache identity.

**Change:**
- New input flag `GeometryPipelineInput::analyze_boundaries`, default **false**.
- New result flag `GeometryPipelineResult::boundaries_analyzed` explicitly distinguishes a skipped analysis from a failure or genuine empty topology result.
- Only run `extract_mesh_boundaries` if explicitly requested. In the Godot report return `boundary_status="NOT_REQUESTED"` and `boundaries_analyzed=false` on the ordinary path.
- Keep existing dedicated topology analysis APIs for users who actually need border diagnostics; retain original mesh and conventional renderer for all cache statuses.
- Update the original mock-based integration and real-vendor end-to-end fixtures. The latter deliberately opts in to boundary checks where it asserts border data, and adds a separate fast-path cache-hit/miss scenario.

**Executed gate:** strict GCC C++17 and Clang 17 AddressSanitizer/UndefinedBehaviorSanitizer passed against a byte-for-byte matched copy of the new `geometry_import_pipeline.h/.cpp` with isolated function-level test doubles. Separate tests covered HIT, BUILT_STORED and BUILT_UNSTORED without diagnostics; explicitly requested diagnostics on hit and miss; and invalid input short-circuiting. This is **not** a full vendor-linked or Godot runtime result. The default path still performs a full cache source hash, WGC1 decode and independent verification on hits: it is *less redundant*, not O(1).

### Not yet completed

1. Full local linked execution with **real** `thirdparty/meshoptimizer` + WGC1 + SHA-256 + filesystem.
2. Full `scons ... module_worlds_geometry_enabled=yes` engine build and all headless GDScript smoke tests.
3. Automatic editor import callback, asset/dependency provenance, content-addressed naming, lifecycle/GC policy.
4. Multi-resolution cluster hierarchy with bounded error, crack-resilient transitions and missing-page fallback.
5. GPU-side culling, indirect draw, occlusion, streaming and memory budgeting. Material, shadow, motion-vector and skinned/deformed parity remain unverified.
6. Benchmark comparisons on named GPUs with equivalent output quality and regression tracking.

---

## 2. Why are we doing it?

**Goal:** a general-purpose, Godot-familiar engine that can visually support very large, persistent simulation worlds at better frametime stability and image quality without tying the authoritative world state to scene nodes. The separate Worlds-ECS simulation decides what exists and changes; a renderer projects relevant visual representations. The motivating workloads involve thousands of complex simulated people and tens of thousands of animals, **not** an expectation that every simulated agent is fully visible, animated and physically active every frame.

**Why clusters/meshlets:** whole-mesh draw and LOD policies can become inefficient on very dense geometry if much of the mesh is offscreen, occluded or too distant. Clusters enable finer-grained visibility tests and eventual screen-space-error LOD selection. They do not make arbitrary geometry free, and increase preprocessing, memory management and shader/work-submission complexity.

**Why WGC1 and SHA-256:** clustering and bounds generation should not be repeated when source geometry and generator settings are unchanged. A reproducible content fingerprint identifies a compatible result; bounded parsing, oriented triangle verification and bounds checks ensure a cache hit is not trusted blindly. SHA-256 is for stable content identity/collision resistance, **not bank-style encryption**, and cannot detect any external dependency the importer failed to include.

**Why preserve Godot:** Godot already supplies importers, scene/editor workflows, material/shadow passes, rendering backends, platform fallbacks and a large ecosystem. A bolt-on experimental path with an upstream-compatible fallback is significantly less risky than replacing a working rendering pipeline before any hardware evidence.

**Why CPU tests first:** research, source audits, deterministic correctness proofs and sanitizer testing can proceed without the primary GPU workstation. CPU tests cannot establish lighting parity, actual GPU performance, memory throughput, rendering-order correctness or hardware compatibility.

---

## 3. How can we improve?

### P0: stop carrying an unproven integration layer

**Required next gates, in order:**
1. From a complete checkout run `bash benchmarks/native_geometry/run_real_vendor_gate.sh` and its optional `CXX=clang++ SANITIZE=1` mode. This must compile/link/run the actual vendor `clusterizer.cpp`, `meshletutils.cpp`, WGC1 codec, SHA-256, cache store and end-to-end fixture. Record compiler/version, exit code, test outputs and any fixes.
2. Compile an opt-in native Godot editor, then execute `godot_mesh_source_smoke.gd`, `godot_meshlet_smoke.gd`, `godot_geometry_cache_smoke.gd` and `godot_importer_index_presence_smoke.gd`. Avoid mistaking `SKIP` for `PASS`.
3. Run real glTF and procedural assets with UV seams, multiple materials, multiple LODs, nonindexed surfaces and malformed/corrupted cache payloads. Protect the existing renderer for any failure.
4. Establish a fixed `Godot 4.8 beta fork commit + compiler + API` reproducibility matrix before treating the module as tested.

If full builds are unavailable, **do not block unrelated research indefinitely**: continue source-based tests and treat real native gates as pending. Do not claim fake vendor mock execution as full integration evidence.

### P1: make importing automatic and predictable

- Use a **content-addressed cache key**, derived from complete source geometry, relevant imported attributes, every geometry-affecting setting, generator version, platform variant and external glTF dependencies. Avoid duplicate work across identical assets; surface and LOD IDs must remain separate.
- Separate cheap preparation from expensive diagnostics. Make topology audit visible in a dedicated inspector/export report, not mandatory per cache hit.
- Record build time, hit/miss reason, bytes stored, bytes used, actual vertex-reference counts, cluster count, invalidation cause and last generator version. Track cache cleanup/eviction and avoid indefinite growth in `user://`.
- Use bounded workers/IO queues, progress/cancellation and lifecycle ownership; never block an editor or render frame on unbounded conversion work.
- Preserve material, UV, normal/tangent, blendshape, skin, and morph ownership in the original asset. WGC1 currently stores **geometry cluster metadata**, not a complete GPU-ready attribute/material representation.

### P2: validate the right GPU design before implementing it

- **Hardware baseline:** the RX 5700/RDNA1 generation is not a mesh-shader baseline. Start with standard Vulkan/RenderingDevice buffers, compute visibility, and conventional indirect indexed rendering where supported. Treat `VK_EXT_mesh_shader` as an optional second implementation for newer GPUs; require capability querying rather than model-name assumptions.
- First GPU experiment should render **one static opaque material** through original and experimental paths with identical camera, lighting, shadow and tone mapping. Verify pixel and primitive identity before chasing speed.
- Add a conservative CPU coarse-object visibility list, GPU cluster visibility, optional HZB occlusion, stable indirect commands and robust sync with frames in flight. Add stereo, teleports, near-plane intersections and camera cuts to the tests; avoid false-negative occlusion.
- Measure `CPU frame ms`, `GPU frame ms`, `P95/P99 frametime`, `draw commands`, `candidate/visible meshlets`, `GPU buffer bytes`, `upload bytes/frame`, `cache hit rate`, `cold-load stalls`, `artifact count` and `pixel/temporal difference` at equivalent render quality.
- Avoid early overengineering of software rasterization or custom command submission if existing rendering-device paths prove competitive.

### P2: cluster LODs and residency should be co-designed

- Evaluate open meshoptimizer `demo/clusterlod.h` as a **licensed MIT research reference**, including cluster group selection and combined simplification error; test its actual constraints and seam results instead of assuming it is production-ready or already included in Godot's vendor library.
- Model selection as a valid resident cut across a hierarchy, with a coarse fallback always available. Schedule streaming requests for preferred but absent detail; avoid holes under cache misses and dropped requests.
- Use explicit page IDs, dependencies, generation IDs, resource versions, LRU/priority budgets and GPU fence-safe retirement. Stress camera teleport, thrashing, rapid edits, lost devices and concurrent scene reload.
- Define an objective screen-space error metric and transition policy; independent edge simplification can create cracks or silhouette popping, requiring neighbor-aware constraints or defensible skirts/morph/crossfades.

### P3: quality, portability and long-term maintenance

- **Content classes:** static opaque architecture/sculpture, alpha-cutout foliage, skinned characters, morphs, dynamic destruction, terrain, large textured surfaces, translucent objects and particle/splat assets have very different bottlenecks. Benchmark specialized representations rather than forcing every asset through one clustered pipeline.
- **Material and light parity:** solve depth, shadows, transparent sorting, motion vectors, decals, GI compatibility and instance/material overrides. A faster unlit demo is not a replacement for Godot Forward+.
- **Worlds-ECS:** world state stays authoritative outside the renderer. Develop dirty-region/instance change packets, multi-camera visibility projections, stable IDs, streaming boundaries, render-lifetime generations and bounded per-frame consumption, without one Node per simulated object.
- **Upstream strategy:** minimize fork surface area, document any Godot API changes, keep regression cases attached to modules, and rebase deliberately. Maintain 2D/mobile/web/compatibility as fallbacks rather than quietly breaking them.
- **Splat rendering:** useful as an optional asset type for certain scanned/static content, but compositing, overdraw, transparency, editing, relighting, collision, animation and shadow consistency need their own research. Do not make splats the default replacement for conventional meshes.

---

## 4. What are we missing, and what should we learn?

### Missing capabilities that matter most

| Missing capability | Why it matters | How to investigate / prove |
| --- | --- | --- |
| Real vendor and engine integration | Current subsystem could still fail to link or behave incorrectly in Godot | Native no-mock runner + full SCons + real imported samples |
| Actual GPU baselines | Cannot claim superior performance without a control | Equal-quality side-by-side frame and memory captures on named GPUs |
| Cluster hierarchy and error model | Meshlets alone are not virtual geometry or adaptive detail | Evaluate open clusterlod ideas; build independent error/seam oracle |
| Bounded page streaming | Full-detail assets won't fit VRAM or load instantly | Multi-level residency simulator and real IO/GPU fence tests |
| Material/shadow integration | Geometry can be correct but render wrong | Automated pixel/reference and temporal tests in all relevant passes |
| Stable provenance | Stale caches can survive changes to external assets | Dependency hash traversal, importer version tracking, cache invalidation tests |
| GPU feature tiers | RDNA1 and integrated/mobile GPUs differ from modern mesh-shader targets | Runtime feature detection and compute/indirect fallbacks |
| Editable dynamic content | Simulated actors, vegetation, destructible objects may change | Asset classification and updates without invalidating whole worlds |
| Hard resource limits | Huge worlds require bounded CPU/GPU/IO memory and frame-time | Stress tests, telemetry, hot/cold paths, P99 budgets and cancellations |

### Concrete public research sources

1. **meshoptimizer's cluster LOD experiment (MIT):** https://github.com/zeux/meshoptimizer/blob/master/demo/clusterlod.h — group refinement, simplification error, optional spatial clustering. Beware its reference/demo maturity and evolving API.
2. **meshoptimizer README/API (MIT):** https://github.com/zeux/meshoptimizer — meshlet generation, bounds, cluster culling and optional hardware mesh shading. The fork vendors meshoptimizer **v1.3** at the reviewed revision.
3. **Godot internal rendering architecture:** https://docs.godotengine.org/en/stable/engine_details/architecture/internal_rendering_architecture.html — Forward+ material passes, RenderingDevice abstraction and platform tiers. Treat the checked Godot fork as authoritative if newer upstream documents disagree.
4. **Khronos mesh shading:** https://www.khronos.org/blog/mesh-shading-for-vulkan — portable extension capability, triangle-cluster use cases and task/mesh stage design. Not a mandate to use mesh shaders on incompatible hardware.
5. **Streaming and virtual geometry teaching reference:** https://courses.grainger.illinois.edu/cs418/fa2025/text/nanite.html — page residency, metadata, DAG cuts and missing-detail streaming in a public architectural overview. Learn concepts; do not port Epic's licensed implementation.
6. **AMD GPUOpen mesh shaders:** https://gpuopen.com/learn/mesh_shaders/mesh_shaders-from_vertex_shader_to_mesh_shader/ — hardware/pipeline prerequisites and best-practice context.
7. **Published high-detail geometry research:** https://momentsingraphics.de/HPG2023.html — micropolygon geometry, hierarchical LOD and ray tracing implications for future alternative representation paths.

### Decisions to retain, change, and defer

**Retain:** Godot renderer as fallback, engine-owned optional geometry module, verified clusters, versioned cache, conservative diagnostics, modular Worlds-ECS integration, no proprietary Unreal code reproduction.

**Change next:** close real-vendor acceptance; make boundary diagnostics explicit (implemented in this milestone); automate identity/import workflows; introduce measurable hardware baselines; make GPU feature tiers first-class.

**Defer until evidence:** a homegrown meshlet clustering algorithm instead of meshoptimizer; proprietary-Nanite-equivalent claims; a mandatory mesh-shader pipeline; software raster; splats as the universal representation; a wholesale Godot renderer rewrite.

## Proposed engineering gates

| Gate | Exit evidence | Current status |
| --- | --- | --- |
| A — Portable CPU unit correctness | Strict GCC + Clang sanitizer tests on exact native source | **Partially passed**; several standalones including new diagnostic-fast-path test |
| B — Real vendor end-to-end | Real meshoptimizer → WGC1 → disk write → hit/invalidation | **Unexecuted** |
| C — Godot import integration | SCons build and four headless smoke scripts | **Unexecuted** |
| D — Reference raster parity | Same opaque pixels/shadows from experimental and normal paths | **Not implemented** |
| E — LOD/streaming correctness | Bounded error, no missing content under nonresident page / teleport | **Reference models only** |
| F — Performance acceptance | Measured CPU/GPU ms, VRAM and P99 versus equivalent Godot baselines | **No measurements** |
| G — General engine quality | Material/skin/foliage/cross-platform/editor backward compatibility | **Not yet evidenced** |

## Next work package — constrained environment

1. Commit the boundary-opt-in change and native regression, keeping test-double status explicit.
2. Add a local one-command test target or a command in the native benchmark README that compiles this standalone test independently of the Godot module.
3. Use the complete source checkout (local CPU machine or accessible runner) for the real-vendor WGC1 gate when available; avoid spending scarce CI budget without approval.
4. Analyze meshoptimizer cluster hierarchy and identify an original data contract for error-bounded parent-child groups, with mesh/LOD seam tests, before attempting GPU implementation.
5. Only begin feature-gated `RenderingDevice` rendering once A–C are green. Maintain fallback for older GPUs.

**Bottom line:** valuable foundation and disciplined separation of concerns; no verified replacement renderer yet. The best return now is turning the source-level pieces into a **provably working end-to-end pipeline**, then benchmarking a minimal hardware-backed prototype against stock Godot before expanding features.

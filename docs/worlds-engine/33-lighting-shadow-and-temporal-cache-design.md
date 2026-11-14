# 33 — Lighting, shadow and temporal-cache research specification

**Status:** original research proposal / technical requirements. No new GI or virtual shadow renderer has been built. Godot already has SDFGI, VoxelGI, SSIL, shadow atlas/cascades and clustered Forward+ lighting: these are baselines and potential integration surfaces.

## Core thesis

For complex worlds, **the challenge is not solely to compute better lighting, but to compute the expensive parts only when their valid output changes enough to matter**. An explicit record of scene changes can improve reuse, but any missed invalidation turns performance into visibly incorrect lighting.

We should test a minimal independent `WorldsChangeJournal` before attempting a universal cross-effect cache. Each effect has distinct invalidation needs; a catch-all 'dirty object' flag is too coarse.

## Scene-change journal (independently designed)

**Event classes:**
- presentation instance create/destroy/transform/bounds changed;
- mesh/material/opacity/emission changed;
- light shape/position/angle/color/energy/cast-shadow changed;
- shadow-casting deformation or material vertex displacement;
- geometry streaming/LOD representation changed;
- camera/viewport/projection/resolution changed;
- environment/sky/volumetric weather changes.

Each event records an affected conservative volume or light-space influence, dependency category, source render-handle generation, and monotonic epoch. Coalesce multiple events for an entity per frame, but do not erase a 'deleted' event by coalescing into an unrelated new object reusing a slot.

**Consumers:** a cache states which epochs, representations and views it was built from. It can report `Valid`, `NeedsPartialRefresh`, `NeedsFullRefresh`, or `Unavailable`; renderer either refreshes or uses an explicitly permitted approximation. Validity is not determined solely by frame age.

**Correctness principle:** static geometry may be stable, but moving camera, shadows, normals, light sources, weather and view-space reconstruction can still change output. Never conflate simulation immobility with unchanged visual contribution.

## Experiment S1: sparse cached shadow prototype

**Control:** existing Godot directional shadow cascades / local-light atlas under identical scene, light, quality and camera path.

**Scope:** one static room or outdoor area + one moving object + one local light. Optional shadow atlas derivative; no attempt to replace all shadow passes.

**Research design:**
1. Partition a fixed virtual shadow coverage into independently cacheable tiles (the tile size is a local engineering choice, not sourced from UE).
2. Determine receiver demand from a conservative view/camera receiver set; use bounded physical pages.
3. Keep pages until evicted or their geometric/light dependencies invalidate them.
4. Separate stable geometry contribution from moving geometry *if measured worthwhile*; compose or re-render appropriately.
5. A moving light may invalidate far more pages than a moving small object; quantify damage.
6. Produce a debug overlay: resident, newly requested, invalidated, refreshed, fallback/undersampled.
7. Fail safely when all pages cannot be resident; never sample uninitialized depth.

**Critical accuracy tests:** large caster behind camera, directional light change, foliage displacement, camera cut, alpha test, coincident surfaces, deep cascades, high/low depth precision, moving caster crossing tiles, many overlapping lights.

**Measurements:** pages marked, cache hit rate, changed and unmodified shadow draw cost, P95/P99 render stalls, VRAM, depth accuracy and temporal shadow shimmer. A static scene without movement is insufficient as evidence.

**Public reference:** https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine . That page documents sparse shadow pages, invalidation and known foliage limitations; it is not a license for private shader code.

## Experiment GI1: selective GI refresh

**Control:** Godot SDFGI under the same static scene, dynamic light and camera trajectory. Godot docs explicitly note limited dynamic occluder/emission support; distinguish a **new correctness capability** from a speed optimization.

**Stage 0:** instrument existing SDFGI cost and probe/cascade refresh cadence; produce a reference test with stationary, moving and emissive objects.

**Stage 1:** test a simple world-space irradiance cache (only one local area; basic diffuse materials) derived from publicly available GI methods, or a minimal dirty-region update to a current Godot GI path if feasible.

**Stage 2:** associate cache entries with scene-change epochs; conservatively invalidate when changed geometry/light would affect them. Recognize indirect bounces create non-local dependencies: a changed wall may affect lighting beyond its immediate bounds.

**Stage 3:** prioritize updates by projected usage, lighting-change severity, age and quality error. Enforce a strict per-frame trace/refresh budget with a quality fail-safe.

**Stage 4:** compare screen-space, probe-based, spatial cache and hardware RT paths on their *actual* supported hardware. Cross-vendor, non-RT fallback mandatory.

**Accuracy:** reference high-sample offline or high-quality real-time output for test scenes; detect light leaks, lag, splotches, ghosting, missing bounce, reflection mismatch, emissive changes. A faster but stale GI solution is not a universal improvement.

**Public context:** https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine and https://docs.godotengine.org/en/latest/tutorials/3d/global_illumination/using_sdfgi.html .

## Experiment L1: dense direct lighting

**Control:** Godot Forward+ clustered light handling with the same light distribution and shadow method.

**Hypothesis:** a bounded stochastic light budget (sample important lights and reconstruct temporally) may outperform evaluating every affecting light in scenes with **very high light overlap**. At low overlap, clustered lighting may be better and higher quality.

**Independent conceptual test:** a basic importance-sampled direct-lighting research shader that:
- samples from a valid per-pixel/per-tile distribution, including periodic exploration of possibly important occluded sources;
- weights estimates to reduce bias;
- records estimator variance and image difference against exhaustive evaluation;
- compares sample count vs ray/shadow cost and reconstructed quality;
- avoids assuming RT or denoiser availability on all devices.

**Quality limitations:** finite samples can create noise and temporal trails; denoising may blur lighting, shadows or caustic highlights. Light importance estimates may be wrong at fast motion/camera cuts. Preserve ordinary clustered path by default.

**Public reference:** https://dev.epicgames.com/documentation/unreal-engine/megalights-in-unreal-engine .

## Cross-effect coordination: later research only

One scene change could invalidate geometry visibility, indirect lighting, shadow caster regions, reflection content and temporal history. A common event journal could reduce redundant change detection. However:
- each consumer has different invalidation propagation;
- coarse notifications over-invalidate and waste work;
- too-narrow notifications produce stale caches;
- shared invalidation may create high coupling and stall cascades.

Research per-consumer cache keys and monotonic epochs; implement cross-effect optimization **only after one independent cache is correct**.

## Future originality: predictable quality under bounded compute

Consider a *quality governor* choosing which shadow/GI cache refreshes fit current hardware budgets. It must report accumulated estimated error and offer deterministic degradation; not simply skip expensive work. Evaluate whether it lowers P99 spikes under realistic player motion and large-world changes. This is an unproven Worlds Engine design direction.

## Red flags

- Missing/reduced visual detail presented as improved quality.
- RT-only implementation mistaken for cross-platform replacement.
- Moving foliage causing almost all cached shadow pages to invalidate.
- A shadow or probe cache that appears correct only with static camera.
- No per-effect debug visualizations or GPU timing.
- Unbounded memory or automatic shader compilation spikes.
- Treating GPUScene, Nanite, Lumen or MegaLights as a single component to transplant.

Read [29 source ledger](29-renderer-subsystem-evidence-ledger.md) and [35 validation](35-phase-1-validation-and-next-actions.md) before implementation.

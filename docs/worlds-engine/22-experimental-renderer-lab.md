# 22 — Experimental renderer lab: prototype charter

**Status:** proposed experiment framework, not implemented. Design date: 2026-11-13.

## Why the lab exists

We want an ambitious renderer while protecting existing Godot games and the fork's ability to track upstream. A dedicated lab enables high-risk experiments without destabilizing scenes, importers, 2D and standard rendering.

## Boundaries

- Prefer a standalone benchmark scene or extension using existing Godot RenderingDevice/RenderingServer features before engine-core modification.
- Research prototypes should live in `experiments/rendering/` or a dedicated branch once actual code begins; do not merge into the ordinary renderer by default.
- No experimental feature should alter normal Godot projects without opt-in.
- No copied proprietary Unreal/Epic shaders, code, assets, data or decompiled implementations.
- Record source provenance and relevant licenses before importing any open-source code.

## Experiment E-01: adaptive region vs GPU cluster selection

### Objective

Establish whether GPU fine-grained visibility with indirect rendering beats a conventional, well-tuned spatial MultiMesh configuration for dense static 3D content. This is an experiment in **a new rendering path**, not just retuning an existing path.

### Three controlled competitors

- **A: Upstream-equivalent**: conventional MeshInstance3D and Godot mesh LOD.
- **B: Optimized existing**: region-bounded MultiMesh with sensible bounds/culling and equivalent asset detail.
- **C: Frontier prototype**: simple cluster hierarchy + GPU fine selection + indirect rendering (initially only static opaque geometry).

A/B remain controls even if C looks attractive. Candidate C must justify GPU data structure generation, scheduling, VRAM residency and CPU/GPU synchronization.

### First proof-of-concept boundaries

- One static mesh/material family; no transparency, skinning or shadows.
- One camera, reproducible path and density.
- Offline cluster preprocessing, simple hierarchy, fixed asset footprint.
- GPU-visible cluster output using compute where supported.
- Indirect drawing; conservative correctness and material fallback.
- Record preprocessing memory, GPU buffer size, CPU render cost, GPU cull and draw cost.
- Handle camera teleport, rapid orbit and every-face visibility without disappeared objects.

**Success:** controlled improvement at equivalent image quality and acceptable memory across a meaningful density range. **Failure:** slow at realistic game mesh densities, excessive memory, broken materials, poor frame pacing, nonportable backend. Publish both.

### Experiment layers

1. **E-01a** — static geometry compaction without hierarchical LOD (validates submission mechanics).
2. **E-01b** — hierarchical cluster visibility and projected error.
3. **E-01c** — residency and page streaming.
4. **E-01d** — shadows/material variety/dynamic instances only after earlier gates.

Do not build all four together. Each has independent metrics and stop/go gates.

## Experiment E-02: dynamic MultiMesh update policy

Compare bulk buffer writes, dirty-region setters, and region-specific conservative AABBs under 1%/25%/100% movement. Measure one-time cache/GPU readback transitions and steady-state changes. This is a cheap control and can reveal a near-term improvement without consuming E-01's research budget.

## Experiment E-03: selective rendering refresh

Test screen-space, scene-change and camera-motion-aware update policies for a single expensive secondary effect (such as a cacheable shadow or distant lighting region). Implement only one invalidation source at a time; show staleness maps and correctness triggers.

## Experiment E-04: microtriangle raster crossover

Compare a compute/software rasterizer **concept** with standard GPU raster at matched dense geometry, quality and memory. This may require dedicated high-end hardware. Do not turn a specialized proof of concept into a general default renderer.

## Experiment E-05: deformable ray tracing

Only after multi-vendor ray-tracing support has been confirmed on test hardware: compare an original deformable-cage representation with baseline dynamic BLAS updates. Include animation error, acceleration-memory use, BVH update time and total rendering time. Keep completely optional.

## Performance report required for every experiment

- Source/fork revision, renderer, OS, GPU, driver, API, display resolution and VSync.
- Identical scene seed, asset hash, camera path, draw materials and quality settings.
- P50/P95/P99 frame time, CPU frame, GPU frame, initialization stalls, build/import time, RAM/VRAM, draw/dispatch counts and upload bytes.
- Visual error with matched reference, camera motion and transition/disocclusion examples.
- Three to five repetitions where practical and comparison to the strongest conventional control.
- A documented acceptance/rejection decision and fallback path.

The existing [rendering baseline project](../../benchmarks/rendering/) provides a **scaffold** for the controls; it has not been validated or run yet. It is not a substitute for the complete experiment harness.

## When to attempt integration

An experimental feature should enter the main engine only after it wins a meaningful use case, passes correctness and fallback tests, and has a maintainable API compatible with Godot's ordinary editor/resources. No blanket requirement that every Godot feature be supported by the first experimental version.

## Priority

First: finish E-02 cheap comparative baseline and E-01a design feasibility in parallel. Then choose one code prototype using source evidence and hardware measurements. Follow [frontier strategy](21-frontier-rendering-research.md).

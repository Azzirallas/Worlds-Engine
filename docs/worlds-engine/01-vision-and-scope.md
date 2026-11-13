# 01 — Vision and scope

## Mission

Keep the user experience extremely close to Godot while making Worlds Engine capable of demanding, beautiful, large-scale real-time 3D worlds. A conventional Godot project should remain conventional: ordinary scenes, Nodes, resources, GDScript and C# continue to work. Advanced workflows should be additive, learnable and optional.

The core goal is **useful performance and image-quality improvements**, not maximal source-code divergence from Godot and not a reimplementation of Unreal.

## Target audiences

1. Existing Godot developers seeking familiar tools with optional faster rendering and better large-world infrastructure.
2. Developers building vast procedural worlds, dense environments and complex simulations.
3. Worlds-ECS / WorldSim projects where authoritative game state is external to the rendering engine.
4. Engine contributors who need testable components and a maintainable open-source fork.

Do not sacrifice audience 1 automatically to serve audience 3.

## Long-term aspirations (not promises)

- Seamless, expansive terrain and environments with bounded streaming stalls and predictable memory use.
- High-detail geometry, dense vegetation and many visible animated characters.
- Modern lighting, accurate shadows, strong temporal stability and scalable graphics quality tiers.
- Efficient, reliable physics, with optional detailed destruction and simulation LOD.
- Good CPU/GPU parallelism and efficient asset transfer to GPU.
- Low-overhead integration with a decoupled authoritative ECS, without hard coupling the engine to that ECS.
- Cross-platform builds and near-upstream compatibility.
- Repeatable, honest performance evidence rather than screenshots or peak-frame anecdotes.

## Simulation-specific reference workload

The motivating WorldSim project targets at least 5,000 cognitively complex NPCs and roughly 20,000–30,000 animals in a persistent world, with potential growth. **Those are simulated entity aspirations, not simultaneous visible or physically active counts.** The renderer must display only entities relevant to cameras; physics must activate relevant bodies; memory and decisions remain external to the renderer. No requirement to put every simulated entity into a Node or physics body.

## Explicit non-goals

- Reimplementing Godot's complete editor, scene system, scripting languages or 2D renderer.
- Replacing Worlds-ECS with a Godot-specific ECS.
- Automatically running full-fidelity physics and animations for every persistent entity.
- Making every advanced feature mandatory for every project.
- Copying proprietary Unreal source, assets, shaders or licensed implementations.
- Advertising speedups until compared to an equivalent, documented upstream baseline.
- Breaking old projects or lowering supported platforms without written justification and migration support.

## Definition of success

Success requires all three dimensions:

**Familiarity:** existing sample projects, editor workflows, scenes, import/export paths, scripting APIs and plug-ins continue to function to a published compatibility level.

**Measurable improvement:** targeted benchmarks show improved throughput, frametime stability, scalability, image quality, or authoring cost at controlled quality and hardware settings. Each result must include regressions and where the new path is slower.

**Maintainability:** new systems have owners, isolated interfaces, tests, platform fallbacks and a viable upstream-rebase strategy.

## Project identity

Worlds Engine is an independent fork of Godot, not an official Godot or Epic Games project. Preserve upstream credits, applicable notices, and licenses. We should not imply endorsement by either project.

## What to optimize for

Prefer clear long-term architecture over one-off demos. Prefer bounded memory and worst-case frame behavior over isolated maximum FPS. Prioritize features that unlock scale without adding everyday editor friction.
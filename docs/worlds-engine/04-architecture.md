# 04 — Proposed architecture

## Top-level view

    Godot editor, importers, scripting, SceneTree, UI and normal projects
                              |
                      Godot public APIs
                              |
      +-----------------------+--------------------------+
      |                       |                          |
    Existing scene path     Optional Worlds paths     Editor tooling
      |                       |                          |
      |                 World-region manager            |
      |                 Instance/geometry batches       |
      |                 Streaming and asset residency    |
      |                 Physics activation adapter      |
      |                       |                          |
      +-----------------------+--------------------------+
                              |
           Godot RenderingServer / PhysicsServer / resources
                              |
            RenderingDevice / drivers / supported backends

    [Optional external authoritative Worlds-ECS / WorldSim]
                              |
         Snapshot/delta commands and stable identity mapping
                              |
                 Scene and fast-path adapters

This is a **target decomposition**, not an implementation diagram. Do not invent a new universal abstraction for every subsystem unless the existing Godot abstractions fail a concrete benchmark.

## Mode A: familiar Godot development

- Scenes, nodes, signals, animation trees, native physics and standard materials.
- No Worlds-ECS required; users do not need to know custom systems exist.
- Existing plugin/tool ecosystem should remain viable.

## Mode B: Godot with optional accelerators

- Scalable instance groups, stronger culling and streaming via editor-exposed resources/nodes.
- High-end lighting and geometry features based on backend capability.
- Compatible ordinary assets continue to render; specialized resources may offer an improved performance path.
- Safe fallbacks for unsupported GPUs, renderers and platforms.

## Mode C: external authoritative simulation

- Worlds-ECS computes authoritative world state independent of framerate.
- Adapter tracks stable entity IDs to transient render/physics representatives.
- One entity may have a close-range Node, a far-range batched instance, an impostor, or no visual at all.
- Renderer does not own persistence, economics, NPC memory/knowledge or high-level decisions.
- Interaction commands flow back to the authoritative simulation at defined synchronization points.

## Data ownership and lifetime

**Authoritative:** entity identities, persistent positions, inventories, relationships and history live in Worlds-ECS or another sim if used.

**Projection:** world-region view, GPU resources, visible transforms, animation presentation and transient audio/FX live in Worlds Engine.

**Physics:** body state needs an explicitly documented ownership policy per entity type; dynamic player interaction may use physics authority for a bounded interval followed by reconciliation. Never silently let both sides write the same transform.

**Region state:** residency/priority metadata belongs to the streaming service; eviction never implies deletion of the authoritative entity.

## Frame-flow proposal

1. Collect input, region interest and camera state.
2. Advance or receive simulation updates at its own clock rate.
3. Select visible and near-visible representatives; coalesce dirty records.
4. Schedule streaming and physics activation within budgets.
5. Apply valid render/physics updates at safe synchronization boundaries.
6. Render with appropriate LOD, culling and shading.
7. Publish metrics; reclaim resources after appropriate GPU/physics synchronization.

This order is illustrative. Lock-free or zero-copy transport is not promised; first define threading, data ownership and correctness.

## Interfaces to investigate

- A stable batched instance API for add/update/remove using dense handles and dirty ranges.
- A world-region API for interest, priorities, streaming and eviction.
- A geometry representation API for mesh LOD, potential meshlet data and fallback meshes.
- A physics activation API for sleeping, waking and transferring collision representations.
- An optional simulation bridge API in C#/native code, usable without modifying the ECS.

## Risks and boundaries

The strongest threat is maintaining large divergent changes across Godot releases. Keep new features isolated, use existing Godot services and extension points where practical, upstream general improvements when suitable, and avoid requiring a custom fork feature for otherwise normal projects.
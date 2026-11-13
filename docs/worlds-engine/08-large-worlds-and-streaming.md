# 08 — Large worlds, terrain and streaming

## Objective

Enable expansive, diverse worlds with predictable frame, RAM, VRAM and I/O budgets. A large simulated world is not the same as an enormous simultaneously rendered or physically active scene.

## Existing basis

Godot has large-world coordinate builds, resource loading, scenes and visibility systems. Audit these precisely on this fork before designing replacements. The double-precision option has deployment and GPU limits; a floating-origin or region-local design must be evaluated rather than assumed.

## Coordinate and identity rules

- Use stable world-region IDs and persistent coordinates independent of render-relative positions.
- Keep authoritative ECS identities separate from temporary scene, collision and GPU handles.
- Specify transform precision for close rendering, far rendering, physics and persistent state individually.
- Test origin shifting with cameras, particles, shaders, animation, audio, navigation and networking.
- Unloading a region must not delete persistent simulation entities.

## Interest management

Maintain independent interest categories: visual, physics, audio, editor and simulation. Camera visibility is insufficient to determine physical relevance. Predictions should account for camera/player movement, fast projectiles and teleportation.

## Proposed streaming lifecycle

1. Discover desired regions from interest sets and camera path prediction.
2. Prioritize and request metadata, terrain and asset dependencies.
3. Decode/generate CPU-side assets off the critical path.
4. Queue bounded GPU uploads and resource registration.
5. Activate render, navigation and collision representations at safe synchronization points.
6. Evict only after references, asynchronous work and GPU/physics use retire.
7. Preserve persistent state across all residency transitions.

Track request generation IDs to reject stale completions; make cancellation, failures, repeated rapid movement and device loss explicit.

## Terrain research

Compare chunked heightfield, quadtree LOD, clipmaps, meshes, hybrid surface/cave solutions and virtualized geometry. Evaluate seams, collision alignment, materials, geomorphing, shader cost, sculpting and editor UX. Procedural generation should be pluggable; do not embed a particular game's terrain generator into engine core.

## Vegetation and structures

Use region-bounded batches, hierarchical LOD and efficient material variation. Wind should typically be visual rather than awake-physics work. Interior/exterior structures need occlusion, collision residency and consistent editor authoring. Support streaming structures assembled from conventional Godot assets.

## Budgeted workload

Record CPU decode time, GPU upload bytes/frame, queued bytes, memory high-water marks, I/O rates, cancellations, cache hit rates, residency thrash and teleport recovery. Establish fixed workload budgets and adaptive response to overload.

## Validation scenes

Coast and mountain traversal; dense forest; town + interiors; repeated camera reversal; high-speed movement; long-distance teleport; simultaneous edits; heavy assets; missing/corrupt assets; origin-shift boundary crossings.

## Decision gates

Choose region system size and precision policy only after profiling. No new universal streaming layer without demonstrating that existing loaders and resource APIs are insufficient.
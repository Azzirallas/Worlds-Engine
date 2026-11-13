# 07 — Physics, collision and destruction

## Objective

Support believable interactive physics, large environments and selective destruction without paying full simulation cost for every persistent object. Preserve ordinary Godot physics workflows. An unrelated external ECS may use engine physics as a service, but the engine must remain useful without that ECS.

## Baseline first

The inspected 4.8 beta source includes `modules/jolt_physics/` and `modules/godot_physics_3d/`. Confirm the fork's runtime defaults, project configuration, Jolt version, integration changes and platform support. The existence of Jolt is a reason to benchmark and extend it, not begin by replacing it.

Inspect PhysicsServer3D, shape types, character motion, broadphase, sleeping, constraints, substepping, threading, interpolation, determinism and query costs.

## Workstreams

### P1 — Workload-specific profiling
- Static world: large terrain/city with many static collision shapes.
- Dynamic density: active rigid bodies in confined and dispersed scenes.
- Mixed: many dormant/inactive representatives and a bounded number of active bodies.
- Characters: slopes, steps, obstacles and collision interactions.
- Destruction: fractured structures and debris with different sleeping/cleanup policies.
- Queries: raycasts, overlaps and line-of-sight under contention.

Capture broadphase, narrowphase, solver, callbacks and synchronization cost separately. Validate correctness as well as throughput.

### P2 — Physics activation and representation LOD

Research tiers ranging from persistent entity with no local physics body, to simplified/static collision, to nearby active physics and full contact simulation. Debris may settle, sleep or lose its physics representation, but must not silently lose permanent game state. Define activation rules around fast-moving hazards and gameplay interest (which differs from camera visibility).

### P3 — Destruction as an optional subsystem

Start with authored fracture assets and static support graphs; investigate procedural fracture later. Separate structural state, visual fragments, collision fragments and persistent consequences. Budget fragment generation and active shard counts. A collapse must not overwhelm a frame, corrupt saves or break ordinary Godot physics.

### P4 — Parallelism and broadphase

Test whether actual costs come from threading, wake/sleep churn, collision notifications, broadphase rebuilding or contact solving. Experiment with job settings and batching before invasive solver changes.

### P5 — Specialized physics

Vehicles, cloth, fluids, ropes and deformables require separate evaluation; they are not automatically solved by one rigid-body backend. Prefer optional, explicitly coupled systems.

## Acceptance and fallback

Collision correctness must match documented expectations; stepping and replay policy must be explicit; high-body-count scenes must provide P50/P95/P99 physics tick cost and active-body metrics; streaming and physics transfers must be race-free. Regular RigidBody3D, CharacterBody3D and physics-server interfaces remain functional.

## Open decisions

Physics authority during ECS interactions; tolerance for nondeterminism; precision strategy; long-lived fractured-object identity; whether CPU-side collision simplification is beneficial.
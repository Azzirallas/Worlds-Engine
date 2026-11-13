# 15 — Decision register, unknowns and research backlog

## Decisions to date

| ID | Status | Decision | Reason | Revisit if |
| --- | --- | --- | --- | --- |
| DEC-001 | Chosen | Preserve a familiar Godot editor/workflow | Accessibility and general-purpose use are primary | New UI is demonstrably necessary and opt-in |
| DEC-002 | Chosen | Retain conventional Godot scenes/nodes/scripts | Avoid unnecessary compatibility disruption | A narrow performance use-case requires an opt-in path |
| DEC-003 | Chosen | Prioritize serious graphics and scalability work | Project goal | Baseline data changes the priority order |
| DEC-004 | Chosen | Documentation and baseline audits precede code changes | Avoid speculative rewrites | Not applicable without explicit scope change |
| DEC-005 | Chosen | Keep Worlds-ECS independent and integration optional | Engine remains useful for other games | New constraints demand a modular alternative |
| DEC-006 | Chosen | Use legally appropriate public techniques and original code | Public fork and licensing compliance | Legal review changes policy |
| DEC-007 | Proposed | Use additive fast paths and flags for specialized systems | Preserve normal Godot projects | Benchmark shows maintenance complexity outweighs value |
| DEC-008 | Proposed | Start technical investigation with rendering/geometry | Graphics are key priority | Critical correctness/performance blockers emerge elsewhere |

Decisions are policies or proposals, not evidence that a subsystem already exists.

## Important questions to answer

**Renderer:** Does current Godot bottleneck on main-thread submission, GPU fragments, culling granularity, bandwidth or shader variants in our representative scenes? What GPU APIs/driver features can we rely on? Can robust virtualized geometry coexist with standard meshes?

**Geometry:** How does MultiMesh region sizing trade draw submissions for culling efficiency? Is cluster generation best at import time? What features degrade for skinned/morph/deformable geometry?

**GI:** Which current Godot GI/reflection/shadow shortcomings cause the largest perceptible loss in our content? What acceptable hardware/VRAM cost should a new quality tier target?

**Physics:** How does Godot-Jolt perform at high body counts? Which worlds need dynamic physics authority versus cheap collision and interest-driven activation?

**Large worlds:** Which precision model works across renderer, physics, navigation and shader effects? What regions should load based on noncamera simulation interest?

**Editor:** Which interfaces make specialized geometry/streaming discoverable without changing normal scenes? Do advanced import outputs need cross-platform caches?

**Testing:** What representative hardware targets and performance budgets are realistic? How will we track visual quality as well as FPS/frametime?

**Maintenance:** How often can we follow upstream Godot? Which changes can be upstreamed? Which experimental backends would create an unmaintainable fork?

## How to resolve a question

1. Verify source-version facts and public documentation.
2. Define observable workload and failure mode.
3. Select comparison options including doing nothing.
4. Create the smallest correct test.
5. Record results with confidence, caveats and tested devices.
6. Decide and update this register, then link implementation/benchmark evidence.

## Proposed research tickets (planning identifiers)

- RES-001 RenderingServer frame/data flow and submission costs.
- RES-002 MultiMesh bounds, culling and per-instance update costs.
- RES-003 GPU indirect rendering and meshlet feasibility per backend.
- RES-004 Current 4.8 GI and shadows capability/quality audit.
- RES-005 Streaming/residency architecture, incremental GPU uploads.
- RES-006 Large-world precision and origin-management evaluation.
- RES-007 Jolt integration defaults and physics scaling baseline.
- RES-008 Animation density and GPU skinning paths.
- RES-009 Worlds-ECS delta sync and identity handling.
- RES-010 Godot editor/scene/GDExtension compatibility coverage.

**First ticket:** RES-001, followed by RES-002. These map directly to the Stage 1 technical milestone.
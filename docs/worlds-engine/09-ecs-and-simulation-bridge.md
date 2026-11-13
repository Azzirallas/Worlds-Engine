# 09 — External ECS / simulation bridge

## Purpose

Worlds Engine is a general-purpose Godot fork. It may integrate Worlds-ECS or other authoritative simulation software, but **the ECS is not required to run the editor or ordinary games**. The connector should be modular and replaceable.

## Core contract

- **Authority:** ECS/WorldSim owns identity, needs, decisions, inventory, knowledge and persistent state. Godot owns visual/audio presentation and local transient resources.
- **No mandatory Node-per-entity:** use familiar Nodes for interactive nearby actors and batched render handles for distant or numerous instances.
- **Stable mapping:** persistent IDs are never GPU indices or transient physics-server handles.
- **Controlled sync:** simulation ticks and render frames are decoupled; interpolation/extrapolation is explicitly bounded.
- **Explicit physics handoff:** a selected authority owns each transform during an interaction window.
- **Reversible representation:** Node <-> batch instance <-> impostor <-> absent visual without losing persistent entity data.

## Candidate bridge

A plugin/native module or C# adapter receives compact snapshots and incremental changes. The interface should handle create/remove, transform, appearance/asset ID, animation state, relevance flags and optional physics requests, without exposing ECS internal storage to the renderer.

Proposed operations:
- Initialize/capability negotiation and version check.
- Receive snapshot with revision/tick number and entity registry.
- Submit ordered delta batches with create/update/destroy records.
- Request presentation transitions and callbacks for editor/game interaction.
- Report bridge timings, staleness, queue pressure and dropped/invalid changes.

These are conceptual operations, not implemented APIs.

## Threading, buffering and consistency

Evaluate double/triple buffering, dirty-range updates and queue ownership. Rendering must never read memory being mutated by simulation. Define producer/consumer ownership; cancellation; backpressure; world teardown; reconnect; and authoritative correction policy. No claim of zero-copy or lock-free behavior until proven safe.

## Rendering path selection

Representative selection uses camera distance, screen-space size, occlusion, gameplay interest and recent activity. Close agents may instantiate a scene with rich animation and interaction; mid-range agents may batch simplified rigs; distant agents may use impostors or be culled. Switching must preserve user-visible continuity, selection, audio and interaction where applicable.

## Scope boundary

The engine **must not** decide NPC goals, store social memories, track economies, generate history or impose one ECS schema. These belong in the simulation. The bridge communicates minimal presentation and interaction data.

## Test matrix

Repeated create/destroy; 5,000 complex simulated entities with only a fraction visible; 20,000–30,000 animals; large transform batches; rapid representation switching; teleports; pause/speed changes; corrupted packets; simulation and render running at unrelated rates; save/reload with stable IDs. Distinguish simulated entity totals from active rendered counts.

## Decision gate

Start with the least invasive extension (script/plugin/GDExtension/server APIs); modify engine source only after a benchmark proves necessary. Validate without introducing a dependency from engine core back to Worlds-ECS.
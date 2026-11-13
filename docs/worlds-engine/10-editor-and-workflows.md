# 10 — Editor and development workflow

## Design constraint

A Godot user should be able to open Worlds Engine and use it like Godot. Improving high-end 3D capabilities is not permission to replace the UI, force a proprietary pipeline or remove common workflows.

## Preserve

SceneTree, Nodes, signals, scenes, Resources, Inspector, filesystem dock, viewport controls, editor plugins, GDScript, C#/.NET support, GDExtension, import pipeline, build/export process, debugger, profiler and existing tutorials to the extent compatible with the pinned upstream baseline.

## Additive tooling ideas

- World/region preview panel showing loaded/desired/evicting regions and budgets.
- Geometry pipeline inspector: cluster counts, materials, LOD and fallback representations.
- GPU memory and upload timeline with attribution to region/resource.
- Culling visualization: visible, occluded, stream-pending and far-LOD groups.
- Physics activation heatmap and body lifetime telemetry.
- Reference benchmarks accessible from a reproducible sample project.
- Script-facing high-level configuration via standard Godot Resources and Project Settings.

Avoid overwhelming new users with advanced controls by default. Support discoverable presets and detailed diagnostics when requested.

## Content workflow

Existing .tscn/.tres and standard imported meshes should remain functional. Advanced geometry may use additional optional import data; it must offer preview, regeneration, validation, deterministically cached outputs, and a nonadvanced fallback.

Conventional Godot projects should never require a custom external Worlds-ECS build to open.

## Cross-platform UX

Test Windows, Linux, macOS editor behavior and export targets; review Mobile and Compatibility renderer fallbacks separately. Build tools and scripts should respect upstream cross-platform conventions. Avoid engine-wide environment assumptions based on one developer PC.

## Editor quality gates

- No breaking existing scene serialization without migration.
- No noticeable editor startup/import penalties in ordinary projects without opt-in.
- Debug UI accurately reflects resource lifetime and costs.
- New menus and settings follow established Godot patterns.
- A project created in upstream Godot should have an articulated compatibility path into Worlds Engine.
- A project using specialized features must have documented downgrade/export behavior.
# 02 — Engineering principles and compatibility contract

## Non-negotiable UX contract

- The editor should look, navigate and behave like Godot by default.
- SceneTree, Node, Resource, PackedScene, importers, signals and the usual scripting experience are first-class.
- GDScript, C#/.NET, GDExtension and existing project layouts remain supported within explicitly tested version/target constraints.
- Advanced features have understandable Project Settings and ordinary inspector/editor controls wherever feasible.
- The default rendering/physics behavior remains upstream-compatible unless an opt-in alternative is validated and intentionally selected.
- 2D, mobile, web and low-end paths must not be silently sacrificed to optimize desktop 3D.
- Engine-specific resource formats and APIs need migration or graceful fallback strategies.

## Architectural rules

1. **Improve before replace.** Profile the current system first.
2. **Use opt-in fast paths.** A conventional Node-based path and specialized high-throughput path may coexist.
3. **One truth for world state.** For Worlds-ECS integrations, simulation owns authoritative data; Godot presents a projection.
4. **Keep ownership explicit.** The world partition owns residency metadata; the ECS owns simulation identity; rendering owns GPU handles.
5. **Separate lifetime from visibility.** Unloading visuals must not delete persistent simulation entities.
6. **Avoid unbounded frame work.** Budget asset uploads, streaming, animation refresh and structural changes.
7. **Avoid gratuitous copies.** Batch coherent updates; track dirty data and incremental changes.
8. **Use evidence-based scheduling.** Work stealing, GPU compute and job systems are tools, not automatic wins.
9. **Maintain correctness first.** No data races, use-after-free, invisible-object leaks or gameplay/physics desynchronization.
10. **Document trade-offs.** Every alternative must specify downsides, supported platforms and fallback paths.

## Compatibility levels (proposed)

**Level A — Upstream path:** ordinary Godot project with experimental Worlds Engine features disabled. Strive for unchanged editor/runtime behavior and exported output.

**Level B — Additive features:** project opts into an optional subsystem; existing features keep working except explicitly documented interactions.

**Level C — Specialized worlds:** project uses custom world streaming, batched rendering or external ECS. These may require special asset conventions and authoring tools, but must not contaminate Level A.

## Compatibility test matrix

Track editor boot, project import, scene serialization, GDScript, C# builds, GDExtension loading, editor plug-ins, 2D, 3D, multiple rendering drivers and export templates. Test against representative upstream demo projects plus a Worlds Engine reference project.

Versions and targets must be named rather than saying 'fully compatible' globally. Document intentional incompatibilities with upgrade steps.

## Feature flag rules

- Default off for experimental changes until stable and validated.
- Toggle at Project Settings, renderer configuration, or feature capability level as appropriate.
- Feature flags may be runtime, editor-start or compile-time; document which.
- Fallback or clear diagnostics when a GPU/driver does not support the feature.
- Avoid flag combinations whose results are undefined; either validate or reject incompatible combinations.

## Developer-facing APIs

The public API should express *intent*: e.g., dynamic world region, virtualized geometry resource, batched instance set. Avoid exposing volatile backend internals in public scripts. Prefer Godot-compatible resources, editor inspectors, scene nodes for user-facing configuration, and server-level implementation beneath them.

## Standard for accepting changes

A feature is not complete until it has tests, versioned docs, measured impact, fallbacks, error handling, a stated maintenance cost and compatibility results.
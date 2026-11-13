# 16 — Correctness, regression and validation plan

## Definition of done

Performance improvements are rejected if they break basic correctness, standard workflows, stable asset loading or specified platforms. Every experiment needs a documented failure/fallback story.

## Levels of testing

**Unit:** math, bounds, handles/generation counters, region-state transitions, queues, allocators, resource accounting, LOD selection and invalid inputs.

**Integration:** RenderingServer/SceneTree interoperability, GPU resource lifecycle, physics streaming, import/export, renderer fallbacks, script and editor plugin use.

**End-to-end:** reference Godot projects, custom world-streaming scenes, ECS presentation stress tests, long camera paths and editor workflows.

**Stress and soak:** high object counts, many rapid loads/unloads, teleports, device loss where reproducible, zero-asset and corrupt-asset cases, resource churn and extended memory leak checks.

## Essential correctness invariants

- Each persistent entity maps to at most one active authoritative visual/physics representative per supported representation policy.
- Async tasks with expired generations cannot overwrite newer state.
- GPU buffers and handles are never reused before use retires.
- Origin shifts preserve world-relative collision and rendering alignment.
- Streaming does not leak resources or silently delete authoritative game state.
- Culling is conservative enough to avoid gameplay-relevant missing visuals at documented tolerances.
- Switching representation tiers does not mutate simulation identity or authoritative state.
- Experimental paths can be disabled or safely fallback when unsupported.
- Reproducing a benchmark scene gives stable, comparable behavior.

## Coverage matrix (proposed)

| Category | Tests |
| --- | --- |
| Editor | launch, project open, import, scene editing, Inspector, save/reload |
| Scripting | GDScript, C#/.NET, GDExtension, signals and resource property compatibility |
| Renderers | Forward+, Mobile, Compatibility where available |
| Graphics | static/dynamic geometry, material variants, shadows, transparency, teleport and resize |
| Physics | body motion, contact, constraints, queries, wake/sleep, activation boundaries |
| World | streaming priorities, region cancel, origin rebase, asset failures |
| Platform | Linux, Windows and macOS first; other platforms explicitly tracked |
| ECS bridge | connected/disconnected, version mismatch, concurrency, revision gaps, rapid churn |
| Saves | persistent data remains intact during visual unload and bridge restart |
| Packaging | engine binary, export templates and installation/distribution notices |

## Regression policy

A change introducing substantial new GPU/CPU/memory cost on standard projects requires explicit review, even if the specialized benchmark improves. Maintain side-by-side measurements on upstream-equivalent samples. All reported percentage differences need absolute values and device configuration.

## Tracking

Store each experiment's configuration, scene, commands and measurements in future `benchmarks/` or CI artifacts; link summarized evidence in the corresponding research document. Avoid bloating Git history with generated binary captures when dedicated artifact storage exists.

## Initial verification task

Before coding, audit baseline renderer code paths and existing test infrastructure. Then implement measurement scenes/tools with a separately reviewed plan. No tests are claimed to have been executed at the time this planning document is published.
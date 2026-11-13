# 06 — Lighting, shadows and visual fidelity

## Objective

Reach a high-quality, modern 3D presentation while providing scalable fallbacks and stable performance. Quality should be assessed with controlled comparisons, not labels such as 'AAA.'

## Begin with what Godot has

Audit current Forward+ support for SDFGI, VoxelGI, screen-space indirect lighting, reflection techniques, directional/positional shadows, volumetrics, SSAO, anti-aliasing, temporal upscaling and postprocessing. Feature availability and quality change between versions; confirm against the fork's 4.8 beta source and actual hardware. Do not assume that older Godot articles still describe its exact state.

SDFGI has documented limitations around dynamic occluders and emissive surfaces. Investigate actual needs instead of replacing all lighting.

## Study tracks

### L1 — Quality and stability audit

Create repeatable visual test scenes: indoor daylight, outdoor forest, foliage shadows, dusk/night, high-contrast interiors, dynamic doors, moving emissive objects, wet reflections, transparent materials, moving camera and characters.

Evaluate:
- Indirect light response, light leaking and moving occluders.
- Reflection quality and occlusion.
- Shadow aliasing, shimmering, distance stability and cost.
- Ghosting, disocclusion, temporal upscaling and camera jitter.
- Volumetric stability, exposure transitions and color management.
- VRAM footprint and scaling across quality presets.

### L2 — Improve existing systems

Before creating a replacement GI or shadow solution, investigate targeted changes: caching, update scheduling, lower-cost filtering, better temporal accumulation, hybrid techniques and smarter quality distribution.

### L3 — Dynamic GI alternatives

Research probe-based, irradiance cache, SDF-based, screen-space, software ray and hardware ray approaches. Prototypes must include dynamic lights, dynamic occluders, large outdoor spaces, material response, memory and target-GPU support. A 'Lumen-like' result is a research goal, not a licensed algorithm or a promised feature.

### L4 — Shadows and reflections

Consider virtualized/cached shadow-page concepts only if conventional shadows have measured scene-scaling or stability problems. Reflections may combine screen-space, probes and optional ray methods. Document fallback behavior when surfaces are outside the view.

### L5 — Asset realism and look development

High-quality visuals also depend on material authoring, consistent PBR inputs, normal/tangent handling, mesh quality, vegetation, atmosphere, animation and camera treatment. Avoid blaming the renderer for content/lighting setup failures.

## Quality tiers (proposed)

- Compatibility/base: upstream-equivalent behavior, modest hardware.
- Standard: balanced desktop features.
- High: enhanced shadows/lighting with bounded costs.
- Experimental: optional GPU-specific features, quality/performance telemetry and clear fallbacks.

## Acceptance tests

Image comparisons should use consistent camera paths, identical scene/assets/settings, captured GPU timings, VRAM usage and motion sequences. Report both where quality improves and where temporal artifacts or cost are worse. Preserve existing Godot workflows: WorldEnvironment, lights, materials and shader authoring.
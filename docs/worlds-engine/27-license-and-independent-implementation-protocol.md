# 27 — Licensed engine research and independent implementation protocol

**Status:** project risk-control policy, 2026-11-13. **Not legal advice** and not a legal opinion that any particular port is lawful. Obtain qualified legal advice before integrating code or publishing detailed source-derived designs.

## Why the source was accessed

The project owner has GitHub entitlement to an **access-restricted Unreal Engine source fork**. This allows lawful access within the applicable Epic agreement, but is **not** an MIT/BSD/open-source grant. Worlds Engine is a public Godot-derived project; Unreal code and derivatives must never be incorporated into its Git history.

Official Unreal EULA: https://www.unrealengine.com/eula/unreal

Relevant terms to review:
- Definition and license of **Engine Code** and Source Code (Section 1).
- Distribution restrictions for Engine Code and Engine Tools (Sections 4 and 5).
- Limited public source-code snippet allowance is **not** a general permission to publish implementation details or aggregate excerpts.
- Restrictions on combining Unreal technology with non-compatible licensed code (Section 6).
- Ownership, third-party technology, patents and other rights can be separate issues.

## Mandatory separation

**RESEARCH SOURCES**
1. Restricted Unreal source: permitted review only within the licensed context. Use to understand capabilities, trade-offs and public feature names; do not redistribute.
2. Public Epic technical docs: appropriate for high-level public conceptual descriptions with attribution.
3. Public academic papers, textbooks and independently licensed open-source projects: prefer these for implementation specifications, algorithms and test fixtures; verify each license and patents.
4. Godot source: MIT-licensed; check copyright headers, contributor licensing and third-party dependencies before edits.

**PUBLIC OUTPUT**
- May contain independently written problem statements, high-level architectural comparison, benchmark plans, known limitations and original prototypes.
- Must not include Unreal C++/HLSL, pseudocode adapted line by line, translated functions, copied tables/constants, codegen output, screenshots or large private source-derived call graphs.
- File names and pointer references are used solely as review breadcrumbs for licensed readers, with public documentation as the conceptual implementation source.
- Do not accidentally commit generated, downloaded or decompiled Epic assets into a public repository.

## A stronger clean-room-style process for implementations

1. **Researcher:** writes a problem statement and *public-source-supported* behavioral requirements. Distinguish third-party public techniques from Epic-specific design.
2. **Implementation spec:** uses independent mathematics, standard graphics literature and Godot interfaces; avoids source-specific choices such as private page layouts or exact work queues.
3. **Implementer:** codes exclusively from that spec and independently permissive references, **not** by translating Unreal source. Ideally the implementer has not reviewed restricted source for the feature being implemented.
4. **Reviewer:** checks naming, flow, data layouts, shader structure and comments for inappropriate similarity; compares capability against *outputs/benchmarks*, not against internal source statements.
5. **Provenance file:** lists every paper, URL, author, license, date and implementation author; keep relevant commit history intact.
6. **Release:** validate public fork contents and dependencies; consult counsel on disputed boundaries, patents, contractual restrictions and trademarks.

A single person reading a source file and later writing similar code does **not** automatically constitute an effective clean room. High-level ideas may be unprotectable in some jurisdictions, but code structure, expressive choices, patents, confidentiality and contract terms still create risk. **'We changed syntax' is not a legal test.**

## Decision guardrails

- Never claim 'reverse engineering is expressly permitted in all circumstances' from account access alone.
- Do not copy proprietary algorithms line-for-line and assume renaming variables makes them lawful.
- No public Unreal fork, sublicense or mixing Unreal files with MIT Godot source.
- No third-party shader/sample code until license and patent review.
- Prefer independently published approaches for cluster LOD, GPU compaction, sparse residency, radiance caching, stochastic sampling and tiled shadowing.
- Use generic descriptive names in engine code. 'Nanite-like' and 'Lumen-like' may appear as conceptual comparisons in notes but are not implementation identities.
- If uncertain, isolate the prototype, stop distribution and seek license/legal review.
- This also applies to code snippets, screenshots, data structures, shader binaries, model assets and bundled test scenes.

## Audit methodology and evidence levels

- **Verified-private-source:** observed directly at a pinned UE fork revision; public notes contain only general behavior already supported by public sources.
- **Verified-open-source:** observed in a pinned Godot source revision.
- **Publicly documented:** independently verifiable through Epic documentation or research.
- **Hypothesis:** might improve performance; requires experiments.
- **Measured:** benchmark with matching scene/quality/hardware and reported data.
- **Integrated:** actual Worlds Engine change behind test/compatibility review.

Never silently promote an idea or claimed upstream behavior to measured or integrated. When the licensed source changes, repeat source verification with new revision identifiers.

## Immediate safety check before any code PR

Does the PR contain any Unreal or third-party protected source, compiled artifact or recognizable translation? Is the implementation specification independently supportable by public references? Are all licenses and shaders documented? Has performance and accuracy been measured? Is a normal Godot fallback available?

If any answer is uncertain, do not merge.

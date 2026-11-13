# 13 — Research, licensing and intellectual-property boundaries

## Purpose

Build a public Godot-based project with original implementation, clear attribution, compatible licenses and low litigation/relicensing risk. This is an engineering policy, not legal advice.

## Primary source policy

Prefer publicly accessible papers, official technical blogs, talks, API documentation, patents with legal review, permissively licensed code, and experiments on our own assets. Record author, URL, publication/version, license, constraints and what idea is relevant.

Avoid assuming that "viewable source" means "open source." Some software exposes code under limited licenses that restrict copying, distribution or use in competing products.

## Unreal Engine reference boundary

Unreal Engine Source is generally access-controlled and governed by Epic's Unreal Engine EULA and related terms. **Do not copy, translate, mechanically transform, adapt, or distribute Unreal Engine code or proprietary assets into this Godot fork.** Public documentation and conference material may explain general techniques, but implementation must be original and reviewed for legal constraints.

Labels such as Nanite, Lumen, Chaos, World Partition and Mass refer to Unreal technologies and are research pointers, not names for our own shipped features. Do not imply the fork is affiliated with or endorsed by Epic.

Reversing software to derive protected implementation code is not made safe merely by rewriting syntax or publishing it elsewhere. When uncertain, avoid the source and request qualified legal review.

## Third-party software

Check source license, notices, patents/claims, dependencies, static/dynamic linking provisions and redistribution requirements before integrating. Preserve Godot's MIT notice and individual third-party licenses from LICENSE.txt and COPYRIGHT.txt. Record any new license in a dependency inventory.

Potentially useful references to evaluate (not approval to copy):
- Godot source and docs: https://github.com/godotengine/godot
- Jolt Physics: https://github.com/jrouwe/JoltPhysics
- meshoptimizer: https://github.com/zeux/meshoptimizer
- Vulkan specification: https://registry.khronos.org/vulkan/
- Khronos glTF: https://github.com/KhronosGroup/glTF
- SIGGRAPH real-time rendering papers/talks from primary publishers
- GPU vendor technical guides, considering applicability to vendor-neutral paths

## Research entry template

- Topic / system and key question
- Sources and dates, exact revision/license
- Core concept summarized in original words
- Applicability to Godot and expected user benefit
- Dependencies, hardware support and legal concerns
- Baseline gap and proposed proof of concept
- Test criteria and documented uncertainties

## Contributions and upstream

Write original, reviewable commits with tests and attribution where needed. Avoid imports of unknown provenance. Prefer upstream-friendly improvements when generic; track upstream discussions and relevant accepted alternatives. Review licensing before using proprietary shaders, datasets, demo assets or decompiled code.
# 14 — Upstream strategy and releases

## Strategy

Keep Worlds Engine closely synchronized with Godot rather than permanently maintaining a wholesale engine rewrite. This is both an engineering and user-experience requirement.

## Current fork baseline

At the first documentation audit (2026-11-13), version.py identified Godot 4.8 beta and the repository's master head was recorded in 03-godot-baseline-and-audit.md. This is a snapshot, not a fixed upstream base for all time.

## Branch and integration proposal

- Keep `master` buildable and relatively stable.
- Develop large experimental features on isolated branches, reviewed and merged only after tests.
- Maintain a machine-readable or documented upstream commit ancestry record before each sync.
- Prefer small feature branches with explicit docs/benchmarks.
- Avoid permanently modifying unrelated subsystems to bypass one local limitation.
- Plan periodic upstream syncs, particularly before declaring a release candidate.

These are recommendations; verify current GitHub branch protection and team workflow before enforcement.

## Source-change classification

A. Upstream-equivalent bug fixes: prefer reporting/contributing upstream.

B. Additive general-purpose features: design for potential upstreaming, behind flags as needed.

C. Specialized optimization paths: keep modular and optional; avoid changing baseline behavior.

D. Experimental renderer rewrites: isolate as research until cross-platform and maintenance risks are understood.

## Version naming

Distinguish upstream Godot version from Worlds Engine release. An eventual release should identify both the embedded Godot baseline and its own feature set. Do not market a planned feature as shipped. Include supported OS, GPU API, renderer, project format and known issues.

## Sync checklist

1. Identify exact upstream merge/rebase range, relevant security fixes and deprecations.
2. Resolve conflicts with minimal divergence and preserved notices.
3. Build and test target editor binaries, scripting bindings and export templates.
4. Run representative upstream Godot test projects.
5. Run Worlds Engine benchmarks against the previously published baseline.
6. Review all feature flag/fallback states and update compatibility notes.
7. Document regressions, unavoidable migration steps and open issues.

## Release quality bar

No release without a reproducible build, platform matrix, dependency license review, regression tests, changelog, known limitations and recorded benchmark results. Experimental features must be clearly identified and defeatable.

## Upstream community relation

Maintain factual, noncompetitive attribution: Worlds Engine is a community fork based on Godot. Improvements useful beyond this project should be considered for upstream contribution where feasible.
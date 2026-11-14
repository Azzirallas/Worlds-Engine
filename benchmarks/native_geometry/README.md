# Standalone native geometry topology audit

This is the **first compiled native-C++ research component** for Worlds Engine. It validates topology of indexed triangle surfaces without launching Godot, accessing graphics hardware, changing imported assets or touching the production renderer.

## Compile and execute, from the repository root

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
    -Imodules \
    modules/worlds_geometry/mesh_edge_audit.cpp \
    benchmarks/native_geometry/test_mesh_edge_audit.cpp \
    -o /tmp/worlds_mesh_audit_test
/tmp/worlds_mesh_audit_test
```

**Result on 2026-11-14:** the standalone C++ executable compiled and completed normally on the local Linux container, covering ten explicit input fixtures. This checks the **portable C++ core only**, not the Godot wrapper or Windows build. `assert` is used in these fixtures; run without `-DNDEBUG`.

## Inputs and reports

The original audit routine accepts a `std::vector<Point>` (double-coordinate XYZ positions) and a `std::vector<int32_t>` containing indexed triangles. It returns:

- index/triangle and invalid-data counts;
- degenerate, duplicated and zero-area triangle counts;
- unique, open (one incident face) and non-manifold (more than two incident faces) edge counts;
- winding conflicts for two triangles traversing their common edge in the same direction;
- conservative `valid_input` and `closed_oriented_2manifold` flags.

No vertex welding, floating-point epsilon merging, UV-seam reconstruction, triangle ray tracing or GPU upload is performed. Equal positions at different indices are treated as **different topological vertices**. UV/material vertex duplication can therefore produce apparent open edges; inspect mesh provenance before using the findings as asset errors. A closed/index-connected result is not proof of a physically watertight raster surface.

## Optional Godot wrapper

`modules/worlds_geometry/` contains the opt-in Godot `RefCounted` class `WorldsMeshTopology`, with a method that accepts `PackedVector3Array` and `PackedInt32Array`, copies them into the standalone auditor and returns a `Dictionary` of the above metrics.

The module defines `config.py:is_enabled() == False`: it is **disabled in default SCons builds**. To include this experimental wrapper when a full Godot build environment is available:

```sh
scons platform=linuxbsd target=editor module_worlds_geometry_enabled=yes
```

The Godot integration, reflection/class registration, full engine compilation, script API behavior and cross-platform builds are **not yet validated**. This module is a diagnostic stepping stone toward future imported mesh edge and cluster-border analysis, **not** a virtual geometry renderer.

Related: [57 — native audit and root policy comparison](../../docs/worlds-engine/57-regional-geometry-roots-and-native-mesh-edge-audit.md).

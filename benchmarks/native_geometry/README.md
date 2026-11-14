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

**Result on 2026-11-14:** the original indexed-topology standalone executable compiled and completed on the local Linux container, covering ten explicit fixtures. The new position-aware border auditor also compiled and passed **13 native fixtures**, including a separate undefined-behavior-sanitizer execution. These check **portable C++ source only**, not the Godot wrapper, Windows build, or GPU. `assert` is used in the fixtures; run without `-DNDEBUG`.

### Position-aware border audit

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic \
    -Imodules \
    modules/worlds_geometry/mesh_edge_audit.cpp \
    modules/worlds_geometry/mesh_border_audit.cpp \
    benchmarks/native_geometry/test_mesh_border_audit.cpp \
    -o /tmp/worlds_mesh_border_test
/tmp/worlds_mesh_border_test
```

For a separate Linux undefined-behavior-sanitizer run, replace `-O2` with `-O1 -g -fsanitize=undefined -fno-omit-frame-pointer`.

The new `analyze_position_topology` reports the difference between raw index connectivity and **exact XYZ-position-welded** connectivity, without changing the mesh. It distinguishes apparent open indexed edges from duplicate vertex indices at the same spatial position (common at UV seams). The new `compare_border_samples` checks oriented 3D boundary vertex sequences for matching positions, configurable distance tolerance, and missing split-vertex/T-junction risks. Neither method certifies truly watertight real 3D triangulation, floating-point raster correctness, or valid stitch meshes. Full details and synthetic policy results are in [58](../../docs/worlds-engine/58-hybrid-root-proxy-and-3d-mesh-border-audit.md).

## Inputs and reports

The original audit routine accepts a `std::vector<Point>` (double-coordinate XYZ positions) and a `std::vector<int32_t>` containing indexed triangles. It returns:

- index/triangle and invalid-data counts;
- degenerate, duplicated and zero-area triangle counts;
- unique, open (one incident face) and non-manifold (more than two incident faces) edge counts;
- winding conflicts for two triangles traversing their common edge in the same direction;
- conservative `valid_input` and `closed_oriented_2manifold` flags.

The **original indexed** auditor performs no vertex welding, epsilon merging, triangle ray tracing or GPU upload. UV/material vertex duplication can therefore produce apparent open indexed edges; the **additional position-aware diagnostic** reports how many edges change after *exact-position* equivalence. A closed/index-connected or position-welded topology result does not prove a physically watertight raster surface.

## Optional Godot wrapper

`modules/worlds_geometry/` contains the opt-in Godot `RefCounted` class `WorldsMeshTopology`. Its read-only methods are `analyze_indexed_surface(vertices, indices)`, `analyze_position_surface(vertices, indices)`, and `compare_border_samples(border_a, border_b, tolerance = 0.0)`. These copy packed Godot arrays into the portable C++ analyzers and return diagnostic `Dictionary` objects. The script-facing code has **not been compiled or executed inside Godot**, so it remains provisional.

The module defines `config.py:is_enabled() == False`: it is **disabled in default SCons builds**. To include this experimental wrapper when a full Godot build environment is available:

```sh
scons platform=linuxbsd target=editor module_worlds_geometry_enabled=yes
```

The Godot integration, reflection/class registration, full engine compilation, script API behavior and cross-platform builds are **not yet validated**. This module is a diagnostic stepping stone toward future imported mesh edge and cluster-border analysis, **not** a virtual geometry renderer.

Related: [57 — initial native topology audit](../../docs/worlds-engine/57-regional-geometry-roots-and-native-mesh-edge-audit.md) and [58 — native 3D border and hybrid policy](../../docs/worlds-engine/58-hybrid-root-proxy-and-3d-mesh-border-audit.md).

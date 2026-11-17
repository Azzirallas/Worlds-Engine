#!/usr/bin/env bash
# CPU-only Godot-independent geometry acceptance: exact source tests, then real vendor.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cxx="${CXX:-g++}"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT

flags=(-std=c++17 -O2 -Wall -Wextra -Werror -pedantic -I"$root" -I"$root/modules")
if [[ "${SANITIZE:-0}" == "1" ]]; then
    flags=(-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic
           -fsanitize=address,undefined -fno-omit-frame-pointer -I"$root" -I"$root/modules")
fi

"$cxx" "${flags[@]}" \
    "$root/modules/worlds_geometry/meshlet_payload.cpp" \
    "$root/benchmarks/native_geometry/test_meshlet_payload.cpp" \
    -o "$out/meshlet_payload"
"$out/meshlet_payload"
echo 'PASS: compact meshlet payload preserves oriented triangles'

"$cxx" "${flags[@]}" \
    "$root/modules/worlds_geometry/mesh_surface_source.cpp" \
    "$root/benchmarks/native_geometry/test_mesh_index_presence.cpp" \
    -o "$out/index_presence"
"$out/index_presence"
printf '%s\n' 'PASS: Godot importer empty-index and explicit-index contract'

"$cxx" "${flags[@]}" \
    "$root/modules/worlds_geometry/geometry_import_pipeline.cpp" \
    "$root/benchmarks/native_geometry/test_boundary_opt_in.cpp" \
    -o "$out/boundary_opt_in"
"$out/boundary_opt_in"
printf '%s\n' 'PASS: cache-hit boundary diagnostics opt-in (isolated dependencies)'

"$cxx" "${flags[@]}" \
    "$root/modules/worlds_geometry/mesh_surface_source.cpp" \
    "$root/modules/worlds_geometry/mesh_edge_audit.cpp" \
    "$root/modules/worlds_geometry/mesh_boundary_extract.cpp" \
    "$root/modules/worlds_geometry/meshlet_contract.cpp" \
    "$root/modules/worlds_geometry/meshlet_builder.cpp" \
    "$root/modules/worlds_geometry/meshlet_payload.cpp" \
    "$root/modules/worlds_geometry/geometry_cache.cpp" \
    "$root/modules/worlds_geometry/geometry_source_hash.cpp" \
    "$root/modules/worlds_geometry/geometry_cache_store.cpp" \
    "$root/modules/worlds_geometry/geometry_import_pipeline.cpp" \
    "$root/thirdparty/meshoptimizer/allocator.cpp" \
    "$root/thirdparty/meshoptimizer/clusterizer.cpp" \
    "$root/thirdparty/meshoptimizer/meshletutils.cpp" \
    "$root/benchmarks/native_geometry/test_geometry_import_end_to_end.cpp" \
    -o "$out/real_vendor_pipeline"
"$out/real_vendor_pipeline"
printf '%s\n' 'PASS: real meshoptimizer + WGC1 + SHA-256 + filesystem + importer CPU pipeline'

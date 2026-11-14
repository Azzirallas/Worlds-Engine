// Original CPU triangle topology audit; no Godot or graphics API dependencies.
#pragma once

#include <cstdint>
#include <vector>

namespace worlds_geometry {
struct Point {
    double x, y, z;
};

struct Report {
    std::uint64_t vertex_count = 0;
    std::uint64_t triangle_count = 0;
    std::uint64_t incomplete_indices = 0;
    std::uint64_t invalid_vertices = 0;
    std::uint64_t invalid_triangles = 0;
    std::uint64_t zero_area_triangles = 0;
    std::uint64_t duplicate_triangles = 0;
    std::uint64_t unique_edges = 0;
    std::uint64_t open_edges = 0;
    std::uint64_t nonmanifold_edges = 0;
    std::uint64_t orientation_conflicts = 0;
    bool valid_input = false;
    bool closed_oriented_2manifold = false;
};

// Uses vertex index identity, not geometric welding; shared UV seams need care.
Report analyze_indexed_triangles(const std::vector<Point> &positions,
                                 const std::vector<std::int32_t> &indices);
} // namespace worlds_geometry

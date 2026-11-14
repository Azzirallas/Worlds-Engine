// Original position-aware edge and boundary validator; no Godot dependencies.
#pragma once

#include "mesh_edge_audit.h"

#include <cstdint>
#include <vector>

namespace worlds_geometry {
struct PositionAudit {
    Report indexed;
    Report welded;
    std::uint64_t unique_positions = 0;
    std::uint64_t coincident_vertex_duplicates = 0;
    std::uint64_t indexed_open_edges_resolved = 0;
};

struct BorderMatch {
    bool valid_input = false;
    bool geometry_match = false;
    bool opposite_direction = false;
    bool same_direction = false;
    bool t_junction_risk = false;
    std::uint64_t samples_a = 0;
    std::uint64_t samples_b = 0;
    double max_opposing_gap = 0.0;
};

// Exact-coordinate welding is diagnostic only: it does not alter the mesh.
PositionAudit analyze_position_topology(const std::vector<Point> &positions,
                                        const std::vector<std::int32_t> &indices);

// Adjacent boundary segments must list identical positions in opposite order.
// Differences in point count fail closed even if points are collinear.
BorderMatch compare_border_samples(const std::vector<Point> &a,
                                   const std::vector<Point> &b,
                                   double tolerance = 0.0);
} // namespace worlds_geometry

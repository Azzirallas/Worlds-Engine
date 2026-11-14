// Standalone C++ checks for exact-position welding and oriented shared borders.
#include "worlds_geometry/mesh_border_audit.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

using worlds_geometry::Point;
using worlds_geometry::analyze_position_topology;
using worlds_geometry::compare_border_samples;

int main() {
    const std::vector<Point> tetra = {{0, 0, 0}, {1, 0, 0}, {0, 1, 0}, {0, 0, 1}};
    const std::vector<std::int32_t> triangles = {0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3};
    {
        // Explicitly duplicate every face's vertices, emulating split UV seams.
        std::vector<Point> duplicated;
        std::vector<std::int32_t> indices;
        for (std::int32_t index : triangles) {
            indices.push_back(static_cast<std::int32_t>(duplicated.size()));
            duplicated.push_back(tetra[index]);
        }
        const auto report = analyze_position_topology(duplicated, indices);
        assert(report.indexed.open_edges == 12);
        assert(report.welded.open_edges == 0);
        assert(report.welded.closed_oriented_2manifold);
        assert(report.coincident_vertex_duplicates == 8);
        assert(report.indexed_open_edges_resolved == 12);
    }
    {
        const auto report = analyze_position_topology(tetra, {0, 1, 2});
        assert(report.indexed.open_edges == 3 && report.welded.open_edges == 3);
        assert(report.indexed_open_edges_resolved == 0);
    }
    {
        const auto report = analyze_position_topology(tetra, triangles);
        assert(report.coincident_vertex_duplicates == 0);
        assert(report.welded.closed_oriented_2manifold);
    }
    {
        auto pts = tetra;
        pts[0].x = std::numeric_limits<double>::quiet_NaN();
        const auto report = analyze_position_topology(pts, {0, 1, 2});
        assert(!report.indexed.valid_input && !report.welded.valid_input);
    }
    const std::vector<Point> a = {{0, 0, 0}, {1, 0, 0}, {2, 0, 0}};
    const std::vector<Point> reversed = {{2, 0, 0}, {1, 0, 0}, {0, 0, 0}};
    {
        const auto result = compare_border_samples(a, reversed);
        assert(result.valid_input && result.geometry_match);
        assert(result.opposite_direction && !result.same_direction);
        assert(result.max_opposing_gap == 0.0);
    }
    {
        const auto result = compare_border_samples(a, a);
        assert(result.valid_input && !result.geometry_match);
        assert(result.same_direction && !result.opposite_direction);
    }
    {
        // Collinear but missing central shared vertex: a conservative T-junction risk.
        const auto result = compare_border_samples(a, {{2, 0, 0}, {0, 0, 0}});
        assert(result.t_junction_risk && !result.geometry_match);
    }
    {
        const auto result = compare_border_samples(a, {{2, 0, 0}, {1, 0.01, 0}, {0, 0, 0}}, 0.001);
        assert(result.valid_input && !result.geometry_match);
    }
    {
        const auto result = compare_border_samples(a, {{2, 0, 0}, {1, 0.01, 0}, {0, 0, 0}}, 0.02);
        assert(result.valid_input && result.geometry_match);
    }
    {
        const auto result = compare_border_samples(a, {{2, 0, 0}, {1, 0, 0}, {0, 0, 0}}, -1.0);
        assert(!result.valid_input);
    }
    {
        const auto result = compare_border_samples({{0, 0, 0}}, reversed);
        assert(!result.valid_input);
    }
    {
        const auto result = compare_border_samples(a, {{2, 0, 0}, {1, 0, 0},
                                                         {std::numeric_limits<double>::infinity(), 0, 0}});
        assert(!result.valid_input);
    }
    {
        const auto result = compare_border_samples(a, {{2, 0, 0}, {2, 0, 0}, {0, 0, 0}});
        assert(!result.valid_input);
    }
    return 0;
}

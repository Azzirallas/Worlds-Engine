// Standalone C++ core tests, intentionally independent of engine headers.
#include "worlds_geometry/mesh_edge_audit.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

using worlds_geometry::Point;
using worlds_geometry::Report;
using worlds_geometry::analyze_indexed_triangles;

int main() {
    const std::vector<Point> tetra = {{0, 0, 0}, {1, 0, 0}, {0, 1, 0}, {0, 0, 1}};
    const std::vector<std::int32_t> closed = {0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3};
    {
        const Report r = analyze_indexed_triangles(tetra, closed);
        assert(r.valid_input && r.closed_oriented_2manifold);
        assert(r.triangle_count == 4 && r.unique_edges == 6 && r.open_edges == 0);
    }
    {
        const Report r = analyze_indexed_triangles(tetra, {0, 1, 2});
        assert(r.valid_input && !r.closed_oriented_2manifold);
        assert(r.open_edges == 3 && r.nonmanifold_edges == 0);
    }
    {
        auto flipped = closed;
        std::swap(flipped[0], flipped[1]);
        const Report r = analyze_indexed_triangles(tetra, flipped);
        assert(!r.closed_oriented_2manifold && r.orientation_conflicts == 3);
    }
    {
        std::vector<Point> pts = tetra;
        pts.push_back({1, 1, 1});
        const Report r = analyze_indexed_triangles(pts, {0, 1, 2, 1, 0, 3, 0, 1, 4});
        assert(r.nonmanifold_edges == 1);
    }
    {
        const Report r = analyze_indexed_triangles(tetra, {0, -1, 2, 0, 2, 100});
        assert(!r.valid_input && r.invalid_triangles == 2);
    }
    {
        const Report r = analyze_indexed_triangles(tetra, {0, 1, 2, 1});
        assert(!r.valid_input && r.incomplete_indices == 1);
    }
    {
        const Report r = analyze_indexed_triangles({{0, 0, 0}, {1, 0, 0}, {2, 0, 0}}, {0, 1, 2});
        assert(r.valid_input && r.zero_area_triangles == 1 && r.unique_edges == 0);
    }
    {
        const Report r = analyze_indexed_triangles(tetra, {0, 1, 2, 2, 1, 0});
        assert(r.duplicate_triangles == 1 && !r.closed_oriented_2manifold);
    }
    {
        auto pts = tetra;
        pts[0].x = std::numeric_limits<double>::infinity();
        const Report r = analyze_indexed_triangles(pts, {0, 1, 2});
        assert(!r.valid_input && r.invalid_vertices == 1 && r.invalid_triangles == 1);
    }
    {
        const Report r = analyze_indexed_triangles(tetra, {});
        assert(r.valid_input && !r.closed_oriented_2manifold && r.triangle_count == 0);
    }
    return 0;
}

// Portable regression suite for extracted boundary loops and UV-split topology.
#include "worlds_geometry/mesh_boundary_extract.h"
#include "worlds_geometry/mesh_border_audit.h"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <random>
#include <string>
#include <vector>

using worlds_geometry::BoundaryStatus;
using worlds_geometry::BoundaryExtraction;
using worlds_geometry::Point;
using worlds_geometry::extract_mesh_boundaries;

namespace {
bool same(const Point &a, const Point &b) {
    return a.x == b.x && a.y == b.y && a.z == b.z;
}

std::vector<Point> derived_segment(const BoundaryExtraction &result, const Point &from,
                                   const Point &to) {
    for (const auto &chain : result.chains) {
        const auto &ids = chain.vertex_ids;
        const std::size_t count = chain.closed ? ids.size() : ids.size() - 1;
        for (std::size_t i = 0; i < count; ++i) {
            const auto &a = result.positions[static_cast<std::size_t>(ids[i])];
            const auto &b = result.positions[static_cast<std::size_t>(ids[(i + 1) % ids.size()])];
            if (same(a, from) && same(b, to)) {
                return {a, b};
            }
        }
    }
    return {};
}

void expect_loop(const std::vector<Point> &positions, const std::vector<std::int32_t> &indices,
                 std::size_t edge_count, std::size_t loop_count) {
    const auto r = extract_mesh_boundaries(positions, indices);
    assert(r.status == BoundaryStatus::OK && r.boundary_edges == edge_count);
    assert(r.chains.size() == loop_count);
    std::size_t counted = 0;
    for (const auto &chain : r.chains) {
        assert(chain.closed && chain.vertex_ids.size() >= 3);
        counted += chain.vertex_ids.size();
        for (const auto id : chain.vertex_ids) {
            assert(id >= 0 && static_cast<std::size_t>(id) < r.positions.size());
        }
    }
    assert(counted == edge_count);
}

void test_grid(int n) {
    std::vector<Point> points;
    for (int y = 0; y <= n; ++y) {
        for (int x = 0; x <= n; ++x) {
            points.push_back({static_cast<double>(x), static_cast<double>(y), 0});
        }
    }
    std::vector<std::int32_t> indices;
    const auto id = [n](int x, int y) { return static_cast<std::int32_t>(y * (n + 1) + x); };
    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            const auto a = id(x, y), b = id(x + 1, y);
            const auto c = id(x + 1, y + 1), d = id(x, y + 1);
            indices.insert(indices.end(), {a, b, c, a, c, d});
        }
    }
    expect_loop(points, indices, static_cast<std::size_t>(4 * n), 1);
    const auto r = extract_mesh_boundaries(points, indices);
    assert(r.internal_edges == static_cast<std::uint64_t>(3 * n * n - 2 * n));
}
} // namespace

int main() {
    const std::vector<Point> tetra = {{0, 0, 0}, {1, 0, 0}, {0, 1, 0}, {0, 0, 1}};
    const std::vector<std::int32_t> tetra_indices = {0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3};
    expect_loop({{0, 0, 0}, {1, 0, 0}, {0, 1, 0}}, {0, 1, 2}, 3, 1);
    expect_loop({{0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0}}, {0, 1, 2, 0, 2, 3}, 4, 1);
    {
        const auto r = extract_mesh_boundaries(tetra, tetra_indices);
        assert(r.status == BoundaryStatus::OK && r.boundary_edges == 0);
        assert(r.chains.empty() && r.internal_edges == 6);
    }
    {
        std::vector<Point> split;
        std::vector<std::int32_t> split_idx;
        const std::vector<Point> quad = {{0,0,0}, {1,0,0}, {1,1,0}, {0,1,0}};
        for (const int i : {0, 1, 2, 0, 2, 3}) {
            split_idx.push_back(static_cast<std::int32_t>(split.size()));
            split.push_back(quad[static_cast<std::size_t>(i)]);
        }
        const auto r = extract_mesh_boundaries(split, split_idx);
        assert(r.status == BoundaryStatus::OK && r.coincident_vertex_duplicates == 2);
        assert(r.boundary_edges == 4 && r.internal_edges == 1);
    }
    expect_loop({{0,0,0}, {1,0,0}, {0,1,0}, {3,0,0}, {4,0,0}, {3,1,0}},
                {0,1,2,3,4,5}, 6, 2);
    {
        const std::vector<Point> ring = {{0,0,0}, {3,0,0}, {3,3,0}, {0,3,0},
                                         {1,1,0}, {2,1,0}, {2,2,0}, {1,2,0}};
        const std::vector<std::int32_t> indices = {0,1,5, 0,5,4, 1,2,6, 1,6,5,
                                                    2,3,7, 2,7,6, 3,0,4, 3,4,7};
        expect_loop(ring, indices, 8, 2);
    }
    {
        const std::vector<Point> square = {{0,0,0}, {1,0,0}, {1,1,0}, {0,1,0}};
        assert(extract_mesh_boundaries(square, {0,1,2, 0,3,2}).status == BoundaryStatus::NONMANIFOLD_SURFACE);
        assert(extract_mesh_boundaries(square, {0,1,2, 0,1,2}).status == BoundaryStatus::INVALID_SURFACE);
        assert(extract_mesh_boundaries(square, {0,1,2, 0,2,3, 0,2,1}).status == BoundaryStatus::INVALID_SURFACE);
        assert(extract_mesh_boundaries({{0,0,0},{1,0,0},{0,1,0},{0,-1,0},{0,0,1}}, {0,1,2,1,0,3,0,1,4}).status == BoundaryStatus::NONMANIFOLD_SURFACE);
        assert(extract_mesh_boundaries(square, {0,1,1}).status == BoundaryStatus::INVALID_SURFACE);
        assert(extract_mesh_boundaries(square, {0,1,5}).status == BoundaryStatus::INVALID_SURFACE);
        assert(extract_mesh_boundaries(square, {0,1}).status == BoundaryStatus::INVALID_SURFACE);
        assert(extract_mesh_boundaries(square, {}).status == BoundaryStatus::INVALID_SURFACE);
        assert(extract_mesh_boundaries({{0,0,0}, {1,0,0}, {2,0,0}}, {0,1,2}).status == BoundaryStatus::INVALID_SURFACE);
        auto bad = square;
        bad[0].x = std::numeric_limits<double>::infinity();
        assert(extract_mesh_boundaries(bad, {0,1,2}).status == BoundaryStatus::INVALID_SURFACE);
    }
    {
        // Two separate faces touching only at one vertex have ambiguous cyclic order.
        const std::vector<Point> p = {{0,0,0}, {1,0,0}, {0,1,0}, {-1,0,0}, {0,-1,0}};
        assert(extract_mesh_boundaries(p, {0,1,2, 0,3,4}).status == BoundaryStatus::AMBIGUOUS_BOUNDARY);
    }
    {
        // Shared geometric edge of two patches has opposite oriented segments.
        const std::vector<Point> left = {{0,0,0}, {1,0,0}, {1,1,0}, {0,1,0}};
        const std::vector<Point> right = {{1,0,0}, {2,0,0}, {2,1,0}, {1,1,0}};
        const auto a = extract_mesh_boundaries(left, {0,1,2, 0,2,3});
        const auto b = extract_mesh_boundaries(right, {0,1,2, 0,2,3});
        assert(a.status == BoundaryStatus::OK && b.status == BoundaryStatus::OK);
        const auto left_edge = derived_segment(a, left[1], left[2]);
        const auto right_edge = derived_segment(b, right[3], right[0]);
        assert(left_edge.size() == 2 && right_edge.size() == 2);
        const auto matched = worlds_geometry::compare_border_samples(left_edge, right_edge);
        assert(matched.geometry_match && matched.opposite_direction);
    }
    for (int n : {1, 2, 3, 5, 8, 16}) {
        test_grid(n);
    }
    {
        // Deterministic reordering and cyclic triangle rotations must not change topology.
        std::mt19937 rng(0x4b1d);
        std::vector<Point> p = {{0,0,0}, {1,0,0}, {1,1,0}, {0,1,0}};
        for (int round = 0; round < 400; ++round) {
            std::vector<std::int32_t> ids = {0,1,2, 0,2,3};
            if (rng() % 2 == 0) {
                std::rotate(ids.begin(), ids.begin() + 3, ids.end());
            }
            for (int face = 0; face < 2; ++face) {
                std::rotate(ids.begin() + face * 3,
                            ids.begin() + face * 3 + static_cast<int>(rng() % 3),
                            ids.begin() + face * 3 + 3);
            }
            const auto r = extract_mesh_boundaries(p, ids);
            assert(r.status == BoundaryStatus::OK && r.boundary_edges == 4);
            assert(r.chains.size() == 1 && r.chains.front().closed);
        }
    }
    assert(std::string(worlds_geometry::boundary_status_string(BoundaryStatus::OK)) == "OK");
    return 0;
}

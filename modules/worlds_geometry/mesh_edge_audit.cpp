// Indexed-triangle edge incidence checks; conservative offline diagnostic only.
#include "mesh_edge_audit.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <set>
#include <unordered_map>

namespace worlds_geometry {
namespace {
struct EdgeCount {
    std::uint32_t incidents = 0;
    int orientation = 0;
};

bool finite(const Point &p) {
    return std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z);
}

bool valid_area(const Point &a, const Point &b, const Point &c, bool &is_zero) {
    const double ax = b.x - a.x, ay = b.y - a.y, az = b.z - a.z;
    const double bx = c.x - a.x, by = c.y - a.y, bz = c.z - a.z;
    const double cx = ay * bz - az * by;
    const double cy = az * bx - ax * bz;
    const double cz = ax * by - ay * bx;
    if (!std::isfinite(cx) || !std::isfinite(cy) || !std::isfinite(cz)) {
        return false;
    }
    is_zero = cx == 0.0 && cy == 0.0 && cz == 0.0;
    return true;
}

void count_edge(std::unordered_map<std::uint64_t, EdgeCount> &edges,
                std::uint32_t a, std::uint32_t b) {
    const std::uint32_t lo = std::min(a, b), hi = std::max(a, b);
    const std::uint64_t key = (static_cast<std::uint64_t>(lo) << 32) | hi;
    EdgeCount &edge = edges[key];
    ++edge.incidents;
    edge.orientation += a < b ? 1 : -1;
}
} // namespace

Report analyze_indexed_triangles(const std::vector<Point> &positions,
                                 const std::vector<std::int32_t> &indices) {
    Report report;
    report.vertex_count = positions.size();
    report.triangle_count = indices.size() / 3;
    report.incomplete_indices = indices.size() % 3;
    if (positions.size() > std::numeric_limits<std::uint32_t>::max()) {
        return report;
    }
    for (const Point &v : positions) {
        if (!finite(v)) {
            ++report.invalid_vertices;
        }
    }
    std::unordered_map<std::uint64_t, EdgeCount> edges;
    std::set<std::array<std::uint32_t, 3>> faces;
    for (std::size_t i = 0; i + 2 < indices.size(); i += 3) {
        std::array<std::uint32_t, 3> tri{};
        bool valid = true;
        for (int j = 0; j < 3; ++j) {
            const std::int32_t idx = indices[i + j];
            if (idx < 0 || static_cast<std::uint64_t>(idx) >= positions.size() ||
                    !finite(positions[static_cast<std::size_t>(idx)])) {
                valid = false;
                break;
            }
            tri[j] = static_cast<std::uint32_t>(idx);
        }
        if (!valid) {
            ++report.invalid_triangles;
            continue;
        }
        bool zero = false;
        if (tri[0] == tri[1] || tri[1] == tri[2] || tri[2] == tri[0] ||
                !valid_area(positions[tri[0]], positions[tri[1]], positions[tri[2]], zero)) {
            ++report.invalid_triangles;
            continue;
        }
        if (zero) {
            ++report.zero_area_triangles;
            continue;
        }
        auto sorted = tri;
        std::sort(sorted.begin(), sorted.end());
        if (!faces.insert(sorted).second) {
            ++report.duplicate_triangles;
        }
        count_edge(edges, tri[0], tri[1]);
        count_edge(edges, tri[1], tri[2]);
        count_edge(edges, tri[2], tri[0]);
    }
    report.unique_edges = edges.size();
    for (const auto &item : edges) {
        const EdgeCount &edge = item.second;
        if (edge.incidents == 1) {
            ++report.open_edges;
        } else if (edge.incidents > 2) {
            ++report.nonmanifold_edges;
        } else if (edge.orientation != 0) {
            ++report.orientation_conflicts;
        }
    }
    report.valid_input = report.incomplete_indices == 0 && report.invalid_vertices == 0 &&
                         report.invalid_triangles == 0;
    report.closed_oriented_2manifold = report.valid_input && report.triangle_count > 0 &&
            report.zero_area_triangles == 0 && report.duplicate_triangles == 0 &&
            report.open_edges == 0 && report.nonmanifold_edges == 0 &&
            report.orientation_conflicts == 0;
    return report;
}
} // namespace worlds_geometry

// Position-welded topology and border checks; tolerances are caller-defined.
#include "mesh_border_audit.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <map>

namespace worlds_geometry {
namespace {
bool finite_point(const Point &p) {
    return std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z);
}

bool equal_point(const Point &a, const Point &b) {
    return a.x == b.x && a.y == b.y && a.z == b.z;
}

bool well_formed_border(const std::vector<Point> &samples) {
    if (samples.size() < 2 || equal_point(samples.front(), samples.back())) {
        return false;
    }
    for (std::size_t i = 0; i < samples.size(); ++i) {
        if (!finite_point(samples[i])) {
            return false;
        }
        if (i > 0 && equal_point(samples[i], samples[i - 1])) {
            return false;
        }
    }
    return true;
}

double gap(const Point &a, const Point &b) {
    return std::hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}
} // namespace

PositionAudit analyze_position_topology(const std::vector<Point> &positions,
                                        const std::vector<std::int32_t> &indices) {
    PositionAudit result;
    result.indexed = analyze_indexed_triangles(positions, indices);
    if (positions.size() > static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max())) {
        return result;  // No risk of integer overflow when assigning welded IDs.
    }
    std::map<std::array<double, 3>, std::int32_t> position_ids;
    std::vector<Point> unique_positions;
    std::vector<std::int32_t> remap(positions.size(), -1);
    unique_positions.reserve(positions.size());
    for (std::size_t i = 0; i < positions.size(); ++i) {
        const Point &point = positions[i];
        if (!finite_point(point)) {
            continue;
        }
        const auto entry = position_ids.emplace(
                std::array<double, 3>{point.x, point.y, point.z},
                static_cast<std::int32_t>(unique_positions.size()));
        if (entry.second) {
            unique_positions.push_back(point);
        } else {
            ++result.coincident_vertex_duplicates;
        }
        remap[i] = entry.first->second;
    }
    result.unique_positions = unique_positions.size();
    std::vector<std::int32_t> welded_indices;
    welded_indices.reserve(indices.size());
    for (const std::int32_t index : indices) {
        if (index < 0 || static_cast<std::uint64_t>(index) >= remap.size()) {
            welded_indices.push_back(-1);
        } else {
            welded_indices.push_back(remap[static_cast<std::size_t>(index)]);
        }
    }
    result.welded = analyze_indexed_triangles(unique_positions, welded_indices);
    if (result.indexed.open_edges >= result.welded.open_edges) {
        result.indexed_open_edges_resolved = result.indexed.open_edges - result.welded.open_edges;
    }
    return result;
}

BorderMatch compare_border_samples(const std::vector<Point> &a,
                                   const std::vector<Point> &b, double tolerance) {
    BorderMatch result;
    result.samples_a = a.size();
    result.samples_b = b.size();
    if (!std::isfinite(tolerance) || tolerance < 0.0 ||
            !well_formed_border(a) || !well_formed_border(b)) {
        return result;
    }
    result.valid_input = true;
    result.t_junction_risk = a.size() != b.size();
    if (result.t_junction_risk) {
        return result;
    }
    bool reversed = true;
    bool forward = true;
    for (std::size_t i = 0; i < a.size(); ++i) {
        const double opposite_gap = gap(a[i], b[b.size() - i - 1]);
        const double forward_gap = gap(a[i], b[i]);
        result.max_opposing_gap = std::max(result.max_opposing_gap, opposite_gap);
        if (!(opposite_gap <= tolerance)) {
            reversed = false;
        }
        if (!(forward_gap <= tolerance)) {
            forward = false;
        }
    }
    result.opposite_direction = reversed;
    result.same_direction = forward;
    result.geometry_match = reversed;
    return result;
}
} // namespace worlds_geometry

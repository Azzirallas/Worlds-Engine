// Read-only indexed-triangle border extraction with exact-position seam diagnostics.
#include "mesh_boundary_extract.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <map>
#include <utility>

namespace worlds_geometry {
namespace {
struct DirectedEdge {
    std::int32_t from;
    std::int32_t to;
};

struct EdgeIncidence {
    std::uint32_t count = 0;
    DirectedEdge first{0, 0};
};

bool valid_faces(const Report &report) {
    return report.valid_input && report.triangle_count != 0 &&
           report.zero_area_triangles == 0 && report.duplicate_triangles == 0;
}

// Walk only unique outgoing edges; no branching or repeated edge is permitted.
bool walk_chain(std::int32_t start, const std::vector<std::int32_t> &outgoing,
                const std::vector<DirectedEdge> &edges, std::vector<bool> &visited,
                BoundaryChain &chain) {
    chain.vertex_ids.push_back(start);
    std::int32_t cursor = start;
    for (;;) {
        const std::int32_t edge_id = outgoing[static_cast<std::size_t>(cursor)];
        if (edge_id < 0) {
            return chain.vertex_ids.size() >= 2;
        }
        if (visited[static_cast<std::size_t>(edge_id)]) {
            return false;
        }
        visited[static_cast<std::size_t>(edge_id)] = true;
        cursor = edges[static_cast<std::size_t>(edge_id)].to;
        if (cursor == start) {
            chain.closed = true;
            return chain.vertex_ids.size() >= 3;
        }
        chain.vertex_ids.push_back(cursor);
    }
}
} // namespace

BoundaryExtraction extract_mesh_boundaries(const std::vector<Point> &source_positions,
                                           const std::vector<std::int32_t> &indices) {
    BoundaryExtraction result;
    if (source_positions.empty() || source_positions.size() >
            static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max()) ||
            !valid_faces(analyze_indexed_triangles(source_positions, indices))) {
        return result;
    }

    // Exact coordinate welding is for topology diagnostics only: never mutate input assets.
    std::map<std::array<double, 3>, std::int32_t> canonical;
    std::vector<std::int32_t> remap(source_positions.size(), -1);
    for (std::size_t i = 0; i < source_positions.size(); ++i) {
        const Point &p = source_positions[i];
        if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z)) {
            return result;
        }
        const std::array<double, 3> key{p.x, p.y, p.z};
        auto it = canonical.find(key);
        if (it == canonical.end()) {
            const auto id = static_cast<std::int32_t>(result.positions.size());
            it = canonical.emplace(key, id).first;
            result.positions.push_back(p);
        } else {
            ++result.coincident_vertex_duplicates;
        }
        remap[i] = it->second;
    }

    std::vector<std::int32_t> welded_indices;
    welded_indices.reserve(indices.size());
    for (const auto index : indices) {
        welded_indices.push_back(remap[static_cast<std::size_t>(index)]);
    }
    const Report welded = analyze_indexed_triangles(result.positions, welded_indices);
    if (!valid_faces(welded)) {
        result.status = BoundaryStatus::NONMANIFOLD_SURFACE;
        return result;
    }
    if (welded.nonmanifold_edges != 0 || welded.orientation_conflicts != 0) {
        result.status = BoundaryStatus::NONMANIFOLD_SURFACE;
        return result;
    }

    std::map<std::pair<std::int32_t, std::int32_t>, EdgeIncidence> incidences;
    for (std::size_t i = 0; i < welded_indices.size(); i += 3) {
        const std::array<std::int32_t, 3> tri{welded_indices[i], welded_indices[i + 1],
                                               welded_indices[i + 2]};
        for (int j = 0; j < 3; ++j) {
            const std::int32_t a = tri[static_cast<std::size_t>(j)];
            const std::int32_t b = tri[static_cast<std::size_t>((j + 1) % 3)];
            auto &record = incidences[std::minmax(a, b)];
            if (record.count == 0) {
                record.first = {a, b};
            }
            ++record.count;
        }
    }

    std::vector<DirectedEdge> border;
    border.reserve(incidences.size());
    for (const auto &entry : incidences) {
        if (entry.second.count == 1) {
            border.push_back(entry.second.first);
        } else if (entry.second.count == 2) {
            ++result.internal_edges;
        } else {
            result.status = BoundaryStatus::NONMANIFOLD_SURFACE;
            return result;
        }
    }
    if (border.size() > static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max())) {
        result.status = BoundaryStatus::INVALID_SURFACE;
        return result;
    }
    result.boundary_edges = border.size();

    std::vector<std::int32_t> outgoing(result.positions.size(), -1);
    std::vector<std::int32_t> incoming(result.positions.size(), -1);
    for (std::size_t i = 0; i < border.size(); ++i) {
        const auto &edge = border[i];
        auto &out = outgoing[static_cast<std::size_t>(edge.from)];
        auto &in = incoming[static_cast<std::size_t>(edge.to)];
        if (out != -1 || in != -1) {
            result.status = BoundaryStatus::AMBIGUOUS_BOUNDARY;
            return result;
        }
        out = static_cast<std::int32_t>(i);
        in = static_cast<std::int32_t>(i);
    }

    std::vector<bool> visited(border.size(), false);
    // Open paths first, then closed loops; both use stable canonical vertex ordering.
    for (int pass = 0; pass < 2; ++pass) {
        for (std::size_t v = 0; v < outgoing.size(); ++v) {
            const std::int32_t edge = outgoing[v];
            if (edge < 0 || visited[static_cast<std::size_t>(edge)] ||
                    (pass == 0 && incoming[v] >= 0)) {
                continue;
            }
            BoundaryChain chain;
            if (!walk_chain(static_cast<std::int32_t>(v), outgoing, border, visited, chain)) {
                result.status = BoundaryStatus::AMBIGUOUS_BOUNDARY;
                result.chains.clear();
                return result;
            }
            result.chains.push_back(std::move(chain));
        }
    }
    if (std::find(visited.begin(), visited.end(), false) != visited.end()) {
        result.status = BoundaryStatus::AMBIGUOUS_BOUNDARY;
        result.chains.clear();
        return result;
    }
    result.status = BoundaryStatus::OK;
    return result;
}

const char *boundary_status_string(BoundaryStatus status) {
    switch (status) {
        case BoundaryStatus::OK: return "OK";
        case BoundaryStatus::INVALID_SURFACE: return "INVALID_SURFACE";
        case BoundaryStatus::NONMANIFOLD_SURFACE: return "NONMANIFOLD_SURFACE";
        case BoundaryStatus::AMBIGUOUS_BOUNDARY: return "AMBIGUOUS_BOUNDARY";
    }
    return "UNKNOWN_STATUS";
}
} // namespace worlds_geometry

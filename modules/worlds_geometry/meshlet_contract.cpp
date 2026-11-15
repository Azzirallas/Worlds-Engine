// Reconstruct output triangles and reject lost, repeated or inverted geometry.
#include "meshlet_contract.h"

#include <algorithm>
#include <array>
#include <utility>
#include <map>

namespace worlds_geometry {
namespace {
using Triangle = std::array<std::uint32_t, 3>;

// Normalize cyclic rotations but keep reversed winding distinct.
Triangle oriented_key(std::uint32_t a, std::uint32_t b, std::uint32_t c) {
    const Triangle r0{a, b, c}, r1{b, c, a}, r2{c, a, b};
    return std::min(r0, std::min(r1, r2));
}

// Do not let a malicious offset+count wrap a size_t before comparison.
bool fits(std::size_t offset, std::size_t count, std::size_t limit) {
    return offset <= limit && count <= limit - offset;
}

bool disjoint(const std::vector<std::pair<std::size_t, std::size_t>> &ranges) {
    auto sorted = ranges;
    std::sort(sorted.begin(), sorted.end());
    for (std::size_t i = 1; i < sorted.size(); ++i) {
        if (sorted[i].first < sorted[i - 1].second) {
            return false;
        }
    }
    return true;
}
} // namespace

MeshletAudit audit_meshlets(const std::vector<std::uint32_t> &source_indices,
                           std::size_t source_vertex_count,
                           const std::vector<MeshletRange> &meshlets,
                           const std::vector<std::uint32_t> &meshlet_vertices,
                           const std::vector<std::uint8_t> &meshlet_triangles,
                           std::uint32_t max_vertices,
                           std::uint32_t max_triangles) {
    MeshletAudit result;
    result.source_triangles = source_indices.size() / 3;
    result.meshlets = meshlets.size();
    if (source_vertex_count == 0 || source_indices.empty() || source_indices.size() % 3 != 0 ||
            meshlets.empty() || max_vertices < 3 || max_vertices > 256 ||
            max_triangles == 0 || max_triangles > 512) {
        return result;
    }
    std::map<Triangle, std::size_t> expected;
    for (std::size_t i = 0; i < source_indices.size(); i += 3) {
        const auto a = source_indices[i], b = source_indices[i + 1], c = source_indices[i + 2];
        if (a >= source_vertex_count || b >= source_vertex_count || c >= source_vertex_count ||
                a == b || b == c || c == a) {
            result.reason = "INVALID_SOURCE_TRIANGLE";
            return result;
        }
        ++expected[oriented_key(a, b, c)];
    }
    std::vector<std::pair<std::size_t, std::size_t>> vertex_spans, triangle_spans;
    for (const MeshletRange &m : meshlets) {
        if (m.vertex_count < 3 || m.vertex_count > max_vertices ||
                m.triangle_count == 0 || m.triangle_count > max_triangles ||
                !fits(m.vertex_offset, m.vertex_count, meshlet_vertices.size()) ||
                !fits(m.triangle_offset, static_cast<std::size_t>(m.triangle_count) * 3,
                      meshlet_triangles.size())) {
            result.reason = "INVALID_MESHLET_RANGE";
            return result;
        }
        vertex_spans.emplace_back(m.vertex_offset, m.vertex_offset + m.vertex_count);
        triangle_spans.emplace_back(m.triangle_offset,
                                    m.triangle_offset + static_cast<std::size_t>(m.triangle_count) * 3);
        result.vertex_references += m.vertex_count;
        result.output_triangles += m.triangle_count;
        // A meshlet must not alias a global vertex through multiple local IDs.
        std::vector<std::uint32_t> local_vertices;
        for (std::size_t v = 0; v < m.vertex_count; ++v) {
            const std::uint32_t global = meshlet_vertices[m.vertex_offset + v];
            if (global >= source_vertex_count) {
                result.reason = "INVALID_GLOBAL_VERTEX";
                return result;
            }
            local_vertices.push_back(global);
        }
        std::sort(local_vertices.begin(), local_vertices.end());
        if (std::adjacent_find(local_vertices.begin(), local_vertices.end()) != local_vertices.end()) {
            result.reason = "DUPLICATE_LOCAL_VERTEX";
            return result;
        }
        for (std::size_t t = 0; t < m.triangle_count; ++t) {
            std::uint32_t tri[3];
            for (std::size_t corner = 0; corner < 3; ++corner) {
                const std::uint8_t local = meshlet_triangles[m.triangle_offset + t * 3 + corner];
                if (local >= m.vertex_count) {
                    result.reason = "INVALID_LOCAL_INDEX";
                    return result;
                }
                tri[corner] = meshlet_vertices[m.vertex_offset + local];
            }
            if (tri[0] == tri[1] || tri[1] == tri[2] || tri[2] == tri[0]) {
                result.reason = "DEGENERATE_OUTPUT";
                return result;
            }
            const auto key = oriented_key(tri[0], tri[1], tri[2]);
            auto it = expected.find(key);
            if (it == expected.end() || it->second == 0) {
                result.reason = "EXTRA_OR_REVERSED_TRIANGLE";
                return result;
            }
            --it->second;
        }
    }
    if (!disjoint(vertex_spans) || !disjoint(triangle_spans)) {
        result.reason = "OVERLAPPING_RANGES";
        return result;
    }
    if (result.output_triangles != result.source_triangles) {
        result.reason = "MISSING_TRIANGLES";
        return result;
    }
    for (const auto &it : expected) {
        if (it.second) {
            result.reason = "MISSING_TRIANGLES";
            return result;
        }
    }
    result.valid = true;
    result.reason = "OK";
    return result;
}
} // namespace worlds_geometry

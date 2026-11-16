// Repacks validated meshlet spans to avoid serializing unused builder buffer capacity.
#include "meshlet_payload.h"

#include <algorithm>
#include <limits>
#include <utility>
#include <vector>

namespace worlds_geometry {
namespace {
// Check an offset/count without allowing unsigned addition to overflow.
bool fits(std::size_t start, std::size_t count, std::size_t length) {
    return start <= length && count <= length - start;
}

// The source meshlet verifier already ensures disjoint ranges; defend this API too.
bool nonoverlapping(std::vector<std::pair<std::size_t, std::size_t>> spans) {
    std::sort(spans.begin(), spans.end());
    for (std::size_t i = 1; i < spans.size(); ++i) {
        if (spans[i].first < spans[i - 1].second) { return false; }
    }
    return true;
}
} // namespace

bool compact_meshlet_payload(MeshletBuild &build) {
    if (!build.valid || !build.coverage.valid || build.meshlets.empty()) { return false; }
    std::size_t vertex_count = 0;
    std::size_t triangle_bytes = 0;
    std::vector<std::pair<std::size_t, std::size_t>> vertex_spans;
    std::vector<std::pair<std::size_t, std::size_t>> triangle_spans;
    vertex_spans.reserve(build.meshlets.size());
    triangle_spans.reserve(build.meshlets.size());
    for (const MeshletInfo &m : build.meshlets) {
        const std::size_t vc = m.range.vertex_count;
        const std::size_t tc = m.range.triangle_count;
        if (vc < 3 || tc == 0 || tc > std::numeric_limits<std::size_t>::max() / 3) { return false; }
        const std::size_t tb = tc * 3;
        if (!fits(m.range.vertex_offset, vc, build.vertices.size()) ||
                !fits(m.range.triangle_offset, tb, build.triangles.size()) ||
                vc > build.vertices.size() - vertex_count ||
                tb > build.triangles.size() - triangle_bytes) { return false; }
        vertex_spans.emplace_back(m.range.vertex_offset, m.range.vertex_offset + vc);
        triangle_spans.emplace_back(m.range.triangle_offset, m.range.triangle_offset + tb);
        vertex_count += vc;
        triangle_bytes += tb;
    }
    if (!nonoverlapping(std::move(vertex_spans)) ||
            !nonoverlapping(std::move(triangle_spans))) { return false; }

    std::vector<std::uint32_t> packed_vertices;
    std::vector<std::uint8_t> packed_triangles;
    packed_vertices.reserve(vertex_count);
    packed_triangles.reserve(triangle_bytes);
    std::vector<MeshletRange> packed_ranges;
    packed_ranges.reserve(build.meshlets.size());
    // Build into independent buffers; do not alter references until all reads finish.
    for (const MeshletInfo &m : build.meshlets) {
        const std::size_t vo = m.range.vertex_offset;
        const std::size_t to = m.range.triangle_offset;
        const std::size_t vc = m.range.vertex_count;
        const std::size_t tb = std::size_t(m.range.triangle_count) * 3;
        MeshletRange updated = m.range;
        updated.vertex_offset = packed_vertices.size();
        updated.triangle_offset = packed_triangles.size();
        packed_ranges.push_back(updated);
        packed_vertices.insert(packed_vertices.end(), build.vertices.begin() + vo,
                               build.vertices.begin() + vo + vc);
        packed_triangles.insert(packed_triangles.end(), build.triangles.begin() + to,
                                build.triangles.begin() + to + tb);
    }
    // Commit offsets only when the entire repack succeeded.
    for (std::size_t i = 0; i < build.meshlets.size(); ++i) {
        build.meshlets[i].range = packed_ranges[i];
    }
    build.vertices.swap(packed_vertices);
    build.triangles.swap(packed_triangles);
    return true;
}
} // namespace worlds_geometry

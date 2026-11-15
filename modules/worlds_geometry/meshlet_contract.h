// Hardware-free proof contract for offline meshlet partition output.
#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>

namespace worlds_geometry {
struct MeshletRange {
    std::size_t vertex_offset = 0;
    std::size_t triangle_offset = 0; // byte offset in packed local triangle indices
    std::uint32_t vertex_count = 0;
    std::uint32_t triangle_count = 0;
};

struct MeshletAudit {
    bool valid = false;
    const char *reason = "INVALID_INPUT";
    std::size_t source_triangles = 0;
    std::size_t output_triangles = 0;
    std::size_t meshlets = 0;
    std::size_t vertex_references = 0;
};

// Requires each source triangle exactly once, including winding and duplicates.
MeshletAudit audit_meshlets(const std::vector<std::uint32_t> &source_indices,
                           std::size_t source_vertex_count,
                           const std::vector<MeshletRange> &meshlets,
                           const std::vector<std::uint32_t> &meshlet_vertices,
                           const std::vector<std::uint8_t> &meshlet_triangles,
                           std::uint32_t max_vertices,
                           std::uint32_t max_triangles);
} // namespace worlds_geometry

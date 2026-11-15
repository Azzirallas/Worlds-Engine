// Engine-independent index stream preparation for imported triangle surfaces.
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace worlds_geometry {
enum class SurfaceStatus {
    OK,
    UNSUPPORTED_PRIMITIVE,
    MISSING_VERTICES,
    TOO_MANY_VERTICES,
    EMPTY_INDICES,
    UNEXPECTED_INDICES,
    INCOMPLETE_TRIANGLES,
    INVALID_INDEX,
};

struct PreparedSurface {
    SurfaceStatus status = SurfaceStatus::MISSING_VERTICES;
    bool generated_indices = false;
    std::vector<std::int32_t> indices;
};

// Convert unindexed triangle lists to explicit indices without changing vertices.
PreparedSurface prepare_triangle_surface(std::size_t vertex_count, bool is_triangles,
                                         bool is_indexed,
                                         const std::vector<std::int32_t> &source_indices);

// Stable status strings for native diagnostics and GDScript dictionaries.
const char *surface_status_string(SurfaceStatus status);
} // namespace worlds_geometry

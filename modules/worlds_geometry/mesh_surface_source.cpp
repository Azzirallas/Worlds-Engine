// Validate source mesh/index conventions before the separate topology audit.
#include "mesh_surface_source.h"

#include <limits>

namespace worlds_geometry {
PreparedSurface prepare_triangle_surface(std::size_t vertex_count, bool is_triangles,
                                         bool is_indexed,
                                         const std::vector<std::int32_t> &source_indices) {
    PreparedSurface result;
    if (!is_triangles) {
        result.status = SurfaceStatus::UNSUPPORTED_PRIMITIVE;
        return result;
    }
    if (vertex_count == 0) {
        result.status = SurfaceStatus::MISSING_VERTICES;
        return result;
    }
    if (vertex_count > static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max())) {
        result.status = SurfaceStatus::TOO_MANY_VERTICES;
        return result;
    }
    if (is_indexed) {
        if (source_indices.empty()) {
            result.status = SurfaceStatus::EMPTY_INDICES;
            return result;
        }
        result.indices = source_indices;
    } else {
        if (!source_indices.empty()) {
            result.status = SurfaceStatus::UNEXPECTED_INDICES;
            return result;
        }
        result.generated_indices = true;
        result.indices.reserve(vertex_count);
        for (std::size_t i = 0; i < vertex_count; ++i) {
            result.indices.push_back(static_cast<std::int32_t>(i));
        }
    }
    if (result.indices.size() % 3 != 0) {
        result.status = SurfaceStatus::INCOMPLETE_TRIANGLES;
        return result;
    }
    for (std::int32_t index : result.indices) {
        if (index < 0 || static_cast<std::size_t>(index) >= vertex_count) {
            result.status = SurfaceStatus::INVALID_INDEX;
            return result;
        }
    }
    result.status = SurfaceStatus::OK;
    return result;
}

const char *surface_status_string(SurfaceStatus status) {
    switch (status) {
        case SurfaceStatus::OK: return "OK";
        case SurfaceStatus::UNSUPPORTED_PRIMITIVE: return "UNSUPPORTED_PRIMITIVE";
        case SurfaceStatus::MISSING_VERTICES: return "MISSING_VERTICES";
        case SurfaceStatus::TOO_MANY_VERTICES: return "TOO_MANY_VERTICES";
        case SurfaceStatus::EMPTY_INDICES: return "EMPTY_INDICES";
        case SurfaceStatus::UNEXPECTED_INDICES: return "UNEXPECTED_INDICES";
        case SurfaceStatus::INCOMPLETE_TRIANGLES: return "INCOMPLETE_TRIANGLES";
        case SurfaceStatus::INVALID_INDEX: return "INVALID_INDEX";
    }
    return "UNKNOWN_STATUS";
}
} // namespace worlds_geometry

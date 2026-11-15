// Standalone index preparation checks for Godot importer/runtime mesh surfaces.
#include "worlds_geometry/mesh_surface_source.h"

#include <cassert>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>
using namespace worlds_geometry;

int main() {
    {
        const auto s = prepare_triangle_surface(6, true, false, {});
        assert(s.status == SurfaceStatus::OK && s.generated_indices);
        assert((s.indices == std::vector<std::int32_t>{0, 1, 2, 3, 4, 5}));
    }
    {
        const auto s = prepare_triangle_surface(4, true, true, {0, 2, 1, 1, 2, 3});
        assert(s.status == SurfaceStatus::OK && !s.generated_indices);
        assert(s.indices.size() == 6 && s.indices[1] == 2);
    }
    {
        const auto s = prepare_triangle_surface(4, true, true, {0, 1, 2});
        assert(s.status == SurfaceStatus::OK && s.indices.size() == 3);
    }
    assert(prepare_triangle_surface(4, false, true, {0,1,2}).status == SurfaceStatus::UNSUPPORTED_PRIMITIVE);
    assert(prepare_triangle_surface(0, true, false, {}).status == SurfaceStatus::MISSING_VERTICES);
    assert(prepare_triangle_surface(4, true, true, {}).status == SurfaceStatus::EMPTY_INDICES);
    assert(prepare_triangle_surface(4, true, false, {0,1,2}).status == SurfaceStatus::UNEXPECTED_INDICES);
    assert(prepare_triangle_surface(4, true, true, {0,1}).status == SurfaceStatus::INCOMPLETE_TRIANGLES);
    assert(prepare_triangle_surface(4, true, false, {}).status == SurfaceStatus::INCOMPLETE_TRIANGLES);
    assert(prepare_triangle_surface(4, true, true, {-1,1,2}).status == SurfaceStatus::INVALID_INDEX);
    assert(prepare_triangle_surface(4, true, true, {0,1,4}).status == SurfaceStatus::INVALID_INDEX);
    assert(prepare_triangle_surface(static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max()) + 1,
                                    true, true, {0,1,2}).status == SurfaceStatus::TOO_MANY_VERTICES);
    assert(prepare_triangle_surface(3, true, false, {}).indices.size() == 3);
    assert(std::string(surface_status_string(SurfaceStatus::OK)) == "OK");
    assert(std::string(surface_status_string(SurfaceStatus::INVALID_INDEX)) == "INVALID_INDEX");
    return 0;
}

// Godot ImporterMesh semantics: an empty index stream is a nonindexed triangle list.
#include "worlds_geometry/mesh_surface_source.h"

#include <cassert>
#include <cstdint>
#include <vector>

using namespace worlds_geometry;
int main() {
    const std::vector<std::int32_t> empty;
    for (std::size_t vertices : {3u, 6u, 9u}) {
        // Both NIL and empty PackedInt32Array are nonindexed in Godot ImporterMesh.
        const bool importer_indexed = !empty.empty();
        const auto importer_empty = prepare_triangle_surface(vertices, true, importer_indexed, empty);
        assert(importer_empty.status == SurfaceStatus::OK && importer_empty.generated_indices);
        assert(importer_empty.indices.size() == vertices);
        for (std::size_t i = 0; i < vertices; ++i) {
            assert(importer_empty.indices[i] == static_cast<std::int32_t>(i));
        }
        // Explicitly declared indexed input is a stricter portable contract.
        const auto explicit_indexed = prepare_triangle_surface(vertices, true, true, empty);
        assert(explicit_indexed.status == SurfaceStatus::EMPTY_INDICES);
    }
    const std::vector<std::int32_t> indexed{0, 1, 2};
    const auto normal = prepare_triangle_surface(3, true, !indexed.empty(), indexed);
    assert(normal.status == SurfaceStatus::OK && !normal.generated_indices);
    assert(normal.indices == indexed);
    assert(prepare_triangle_surface(3, true, false, indexed).status == SurfaceStatus::UNEXPECTED_INDICES);
    assert(prepare_triangle_surface(3, false, true, empty).status == SurfaceStatus::UNSUPPORTED_PRIMITIVE);
    assert(prepare_triangle_surface(3, true, true, {0, -1, 2}).status == SurfaceStatus::INVALID_INDEX);
    assert(prepare_triangle_surface(3, true, true, {0, 1}).status == SurfaceStatus::INCOMPLETE_TRIANGLES);
    assert(prepare_triangle_surface(4, true, false, empty).status == SurfaceStatus::INCOMPLETE_TRIANGLES);
    return 0;
}

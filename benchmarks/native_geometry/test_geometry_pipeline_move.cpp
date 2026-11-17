// Verify the pipeline transfers large, verified cache payloads without deep-copying.
#include "worlds_geometry/geometry_import_pipeline.h"

#include <cassert>
#include <cstdint>
#include <filesystem>
#include <vector>

using namespace worlds_geometry;
namespace {
GeometryStoreStatus next_status = GeometryStoreStatus::HIT;
const std::uint32_t *expected_vertices = nullptr;
const std::uint8_t *expected_triangles = nullptr;
const MeshletInfo *expected_meshlets = nullptr;
int builder_calls = 0;
int boundary_calls = 0;
int cache_calls = 0;

MeshletBuild make_valid_build() {
    MeshletBuild b;
    b.valid = true;
    b.coverage.valid = true;
    b.coverage.source_triangles = 1;
    b.coverage.output_triangles = 1;
    b.meshlets.resize(128);
    b.vertices.resize(175000, 7);
    b.triangles.resize(350000, 2);
    b.status = "OK";
    return b;
}

GeometryPipelineInput input() {
    GeometryPipelineInput in;
    in.positions = {{0,0,0},{1,0,0},{0,1,0}};
    in.indices = {0,1,2};
    in.asset_identity = {'a'};
    in.import_settings = {'s'};
    in.cache_path = "move-test.wgc1";
    return in;
}
} // namespace

namespace worlds_geometry {
PreparedSurface prepare_triangle_surface(std::size_t vertex_count, bool triangle,
        bool indexed, const std::vector<std::int32_t> &indices) {
    assert(vertex_count == 3 && triangle && indexed);
    PreparedSurface result;
    result.status = SurfaceStatus::OK;
    result.indices = indices;
    return result;
}
BoundaryExtraction extract_mesh_boundaries(const std::vector<Point> &,
        const std::vector<std::int32_t> &) {
    ++boundary_calls;
    BoundaryExtraction result;
    result.status = BoundaryStatus::OK;
    return result;
}
MeshletBuild build_offline_meshlets(const std::vector<Point> &,
        const std::vector<std::int32_t> &, std::uint32_t, std::uint32_t) {
    ++builder_calls;
    return make_valid_build();
}
GeometryStoreResult load_or_build_geometry_cache(const std::filesystem::path &,
        GeometryCacheSource source, const std::vector<std::uint8_t> &asset,
        const std::vector<std::uint8_t> &settings, const std::function<MeshletBuild()> &build) {
    ++cache_calls;
    assert(source.source_triangles == std::vector<std::uint32_t>({0,1,2}));
    assert(asset == std::vector<std::uint8_t>({'a'}));
    assert(settings.size() == 6);
    GeometryStoreResult r;
    r.status = next_status;
    if (next_status == GeometryStoreStatus::HIT) {
        r.build = make_valid_build();
    } else if (next_status == GeometryStoreStatus::BUILT_STORED ||
            next_status == GeometryStoreStatus::BUILT_UNSTORED) {
        r.build = build();
    } else {
        return r;
    }
    expected_vertices = r.build.vertices.data();
    expected_triangles = r.build.triangles.data();
    expected_meshlets = r.build.meshlets.data();
    return r;
}
} // namespace worlds_geometry

int main() {
    for (const auto s : {GeometryStoreStatus::HIT,
            GeometryStoreStatus::BUILT_STORED, GeometryStoreStatus::BUILT_UNSTORED}) {
        next_status = s;
        expected_vertices = nullptr;
        expected_triangles = nullptr;
        expected_meshlets = nullptr;
        auto result = prepare_offline_geometry(input());
        assert(result.build.valid && result.build.coverage.valid);
        assert(result.build.vertices.size() == 175000);
        assert(result.build.triangles.size() == 350000);
        assert(result.build.meshlets.size() == 128);
        // A copy gives different storage addresses. A move preserves all three.
        assert(expected_vertices != nullptr && result.build.vertices.data() == expected_vertices);
        assert(expected_triangles != nullptr && result.build.triangles.data() == expected_triangles);
        assert(expected_meshlets != nullptr && result.build.meshlets.data() == expected_meshlets);
        assert(result.status == (s == GeometryStoreStatus::HIT ?
                GeometryPipelineStatus::READY_CACHED :
                s == GeometryStoreStatus::BUILT_STORED ?
                GeometryPipelineStatus::READY_STORED : GeometryPipelineStatus::READY_MEMORY_ONLY));
        assert(!result.boundaries_analyzed && boundary_calls == 0);
    }
    assert(builder_calls == 2 && cache_calls == 3);

    next_status = GeometryStoreStatus::BUILD_FAILED;
    auto failed = prepare_offline_geometry(input());
    assert(failed.status == GeometryPipelineStatus::BUILD_FAILED && !failed.build.valid);
    next_status = GeometryStoreStatus::INVALID_SOURCE;
    auto invalid = prepare_offline_geometry(input());
    assert(invalid.status == GeometryPipelineStatus::INVALID_PROVENANCE && !invalid.build.valid);
    return 0;
}

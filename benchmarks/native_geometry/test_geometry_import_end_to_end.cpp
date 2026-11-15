// Full CPU import/cache regression: real meshoptimizer + WGC1 + SHA-256 + disk store.
// This test must link actual vendored meshoptimizer; it has NO mock implementations.
#include "worlds_geometry/geometry_import_pipeline.h"

#include <cassert>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>
#include <vector>

using namespace worlds_geometry;
namespace {
struct TempDirectory {
    std::filesystem::path path;
    TempDirectory() {
        const auto base = std::filesystem::temp_directory_path();
        const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
        for (int i = 0; i < 100; ++i) {
            const auto candidate = base / ("worlds-wgc1-e2e-" + std::to_string(stamp) + "-" + std::to_string(i));
            std::error_code ec;
            if (std::filesystem::create_directory(candidate, ec)) { path = candidate; break; }
        }
        assert(!path.empty());
    }
    ~TempDirectory() { std::error_code ec; std::filesystem::remove_all(path, ec); }
};
GeometryPipelineInput quad(const std::filesystem::path &path) {
    GeometryPipelineInput in;
    in.positions = {{0,0,0},{2,0,0},{2,2,0},{0,2,0}};
    in.indices = {0,1,2,0,2,3};
    in.asset_identity = {'m','e','s','h','-','a'};
    in.import_settings = {'i','m','p','o','r','t','-','v','1'};
    in.cache_path = path;
    in.surface = 2;
    in.lod = -1;
    in.generator_version = 1;
    return in;
}
void expect_ready(const GeometryPipelineResult &r) {
    assert(r.build.valid && r.build.coverage.valid);
    assert(r.build.coverage.source_triangles == 2);
    assert(r.build.coverage.output_triangles == 2);
    assert(!r.build.meshlets.empty());
    assert(r.boundaries.status == BoundaryStatus::OK);
    assert(r.boundaries.boundary_edges == 4);
}
} // namespace

int main() {
    TempDirectory temp;
    auto in = quad(temp.path / "cache.wgc1");
    auto r = prepare_offline_geometry(in);
    assert(r.status == GeometryPipelineStatus::READY_STORED);
    expect_ready(r);
    assert(std::filesystem::file_size(in.cache_path) > 132);

    r = prepare_offline_geometry(in);
    assert(r.status == GeometryPipelineStatus::READY_CACHED);
    expect_ready(r);

    // Damaged on-disk data must regenerate, never result in a trusted cache hit.
    {
        std::fstream file(in.cache_path, std::ios::binary | std::ios::in | std::ios::out);
        assert(file);
        file.seekp(0); file.put('X'); file.flush();
        assert(file);
    }
    r = prepare_offline_geometry(in);
    assert(r.status == GeometryPipelineStatus::READY_STORED);
    expect_ready(r);

    // Altered identity, settings, surface, LOD and actual triangles invalidate cache.
    in.asset_identity.push_back('!');
    r = prepare_offline_geometry(in);
    assert(r.status == GeometryPipelineStatus::READY_STORED);
    in.import_settings.push_back('2');
    r = prepare_offline_geometry(in);
    assert(r.status == GeometryPipelineStatus::READY_STORED);
    ++in.surface;
    r = prepare_offline_geometry(in);
    assert(r.status == GeometryPipelineStatus::READY_STORED);
    in.lod = 0;
    r = prepare_offline_geometry(in);
    assert(r.status == GeometryPipelineStatus::READY_STORED);
    // Cyclic rotation preserves oriented geometry, but source index hash still changes.
    in.indices = {1,2,0,0,2,3};
    r = prepare_offline_geometry(in);
    assert(r.status == GeometryPipelineStatus::READY_STORED);
    expect_ready(r);

    // Distinct valid unindexed source, with its own cache file.
    auto unindexed = quad(temp.path / "unindexed.wgc1");
    unindexed.is_indexed = false;
    unindexed.positions = {{0,0,0},{2,0,0},{2,2,0}, {0,0,0},{2,2,0},{0,2,0}};
    unindexed.indices.clear();
    r = prepare_offline_geometry(unindexed);
    assert(r.status == GeometryPipelineStatus::READY_STORED && r.generated_indices);
    expect_ready(r);
    r = prepare_offline_geometry(unindexed);
    assert(r.status == GeometryPipelineStatus::READY_CACHED && r.generated_indices);

    // Fail-closed behavior: never accept a malformed source as ready.
    auto bad = quad(temp.path / "invalid.wgc1");
    bad.indices[0] = 99;
    r = prepare_offline_geometry(bad);
    assert(r.status == GeometryPipelineStatus::INVALID_SURFACE);
    assert(!std::filesystem::exists(bad.cache_path));
    bad = quad(temp.path / "invalid.wgc1"); bad.asset_identity.clear();
    r = prepare_offline_geometry(bad);
    assert(r.status == GeometryPipelineStatus::INVALID_PROVENANCE);
    assert(!std::filesystem::exists(bad.cache_path));
    return 0;
}

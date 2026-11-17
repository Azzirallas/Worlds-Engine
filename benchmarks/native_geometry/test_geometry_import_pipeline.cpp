// Offline orchestration behavior, tested against isolated vendor/store test doubles.
#include "worlds_geometry/geometry_import_pipeline.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

using namespace worlds_geometry;

namespace {
GeometryStoreStatus next_store = GeometryStoreStatus::BUILT_STORED;
bool return_invalid_success = false;
int builder_calls = 0;
int cache_calls = 0;
int boundary_calls = 0;
GeometryCacheSource seen_source;
std::vector<std::uint8_t> seen_settings;
MeshletBuild valid_build() {
    MeshletBuild b;
    b.valid = true;
    b.coverage.valid = true;
    b.status = "OK";
    return b;
}
GeometryPipelineInput basic() {
    GeometryPipelineInput in;
    in.positions = {{0,0,0},{1,0,0},{1,1,0},{0,1,0}};
    in.indices = {0,1,2,0,2,3};
    in.analyze_boundaries = true;
    in.asset_identity = {'a','s','s','e','t'};
    in.import_settings = {'s','e','t','t','i','n','g','s'};
    in.cache_path = "derived/mesh.wgc1";
    in.surface = 3;
    in.lod = 1;
    in.generator_version = 7;
    return in;
}
void reset() {
    builder_calls = 0;
    cache_calls = 0;
    boundary_calls = 0;
    next_store = GeometryStoreStatus::BUILT_STORED;
    return_invalid_success = false;
}
} // namespace

namespace worlds_geometry {
// Test double emulates only the public source-surface API.
PreparedSurface prepare_triangle_surface(std::size_t count, bool triangles, bool indexed,
                                         const std::vector<std::int32_t>& src) {
    PreparedSurface r;
    if (!triangles) { r.status = SurfaceStatus::UNSUPPORTED_PRIMITIVE; return r; }
    if (!count) { return r; }
    if (indexed) {
        if (src.empty()) { r.status = SurfaceStatus::EMPTY_INDICES; return r; }
        r.indices = src;
    } else {
        if (!src.empty()) { r.status = SurfaceStatus::UNEXPECTED_INDICES; return r; }
        r.generated_indices = true;
        for (std::size_t i=0;i<count;++i) { r.indices.push_back(static_cast<std::int32_t>(i)); }
    }
    if (r.indices.size() % 3) { r.status=SurfaceStatus::INCOMPLETE_TRIANGLES; return r; }
    for (auto id:r.indices) {
        if (id < 0 || static_cast<std::size_t>(id)>=count) { r.status=SurfaceStatus::INVALID_INDEX; return r; }
    }
    r.status = SurfaceStatus::OK;
    return r;
}
BoundaryExtraction extract_mesh_boundaries(const std::vector<Point> &p,
                                           const std::vector<std::int32_t> &indices) {
    ++boundary_calls;
    BoundaryExtraction r;
    assert(!indices.empty());
    r.status = p[0].x == 7.0 ? BoundaryStatus::NONMANIFOLD_SURFACE : BoundaryStatus::OK;
    r.boundary_edges = 4;
    return r;
}
MeshletBuild build_offline_meshlets(const std::vector<Point> &p,
                                   const std::vector<std::int32_t> &idx,
                                   std::uint32_t maxv, std::uint32_t maxt) {
    ++builder_calls;
    assert(p.size()==4 && idx.size()==6 && maxv==64 && maxt==124);
    return valid_build();
}
GeometryStoreResult load_or_build_geometry_cache(const std::filesystem::path &path,
        GeometryCacheSource src, const std::vector<std::uint8_t> &asset,
        const std::vector<std::uint8_t> &settings, const std::function<MeshletBuild()> &builder) {
    ++cache_calls;
    assert(path=="derived/mesh.wgc1" && asset.size()==5);
    seen_source = src;
    seen_settings = settings;
    GeometryStoreResult r;
    r.status = next_store;
    if (next_store == GeometryStoreStatus::HIT) { r.build = valid_build(); }
    else if (next_store==GeometryStoreStatus::BUILT_STORED ||
             next_store==GeometryStoreStatus::BUILT_UNSTORED) { r.build=builder(); }
    if (return_invalid_success) { r.build.valid=false; }
    return r;
}
} // namespace worlds_geometry

int main() {
    reset();
    auto input=basic();
    auto r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::READY_STORED);
    assert(r.store_status==GeometryStoreStatus::BUILT_STORED && r.build.valid);
    assert(r.boundaries_analyzed && r.boundaries.status==BoundaryStatus::OK && r.boundaries.boundary_edges==4);
    assert(boundary_calls==1);
    assert(builder_calls==1 && cache_calls==1);
    assert(seen_source.source_triangles == std::vector<std::uint32_t>({0,1,2,0,2,3}));
    assert(seen_source.surface==3 && seen_source.lod==1 && seen_source.generator_version==7);
    assert(seen_source.max_vertices==64 && seen_source.max_triangles==124);
    assert(seen_settings.size()==input.import_settings.size()+5);
    assert(seen_settings.back()==1);
    assert(std::string(geometry_pipeline_status_string(r.status))=="READY_STORED");

    reset(); next_store=GeometryStoreStatus::HIT;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::READY_CACHED && builder_calls==0 && cache_calls==1);
    assert(boundary_calls==1); // Explicit diagnostics still run on a cache hit.
    // Default import path skips boundary extraction on both miss and hit.
    reset(); input.analyze_boundaries=false; next_store=GeometryStoreStatus::HIT;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::READY_CACHED && !r.boundaries_analyzed);
    assert(boundary_calls==0 && builder_calls==0 && cache_calls==1);
    reset(); next_store=GeometryStoreStatus::BUILT_STORED;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::READY_STORED && !r.boundaries_analyzed);
    assert(boundary_calls==0 && builder_calls==1 && cache_calls==1);
    input.analyze_boundaries=true;
    reset(); next_store=GeometryStoreStatus::BUILT_UNSTORED;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::READY_MEMORY_ONLY && builder_calls==1);
    reset(); next_store=GeometryStoreStatus::BUILD_FAILED;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::BUILD_FAILED && builder_calls==0);
    reset(); next_store=GeometryStoreStatus::INVALID_SOURCE;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_PROVENANCE);
    reset(); next_store=GeometryStoreStatus::HIT; return_invalid_success=true;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::BUILD_FAILED && !r.build.valid);
    reset(); input.positions[0].x=7; // Pretend source topology is non-manifold.
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::READY_STORED &&
           r.boundaries.status==BoundaryStatus::NONMANIFOLD_SURFACE);

    reset(); input=basic(); input.is_triangles=false;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_SURFACE && cache_calls==0);
    reset(); input=basic(); input.indices.clear();
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_SURFACE && cache_calls==0);
    reset(); input=basic(); input.is_indexed=false;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_SURFACE && cache_calls==0);
    reset(); input=basic(); input.indices={0,1,9};
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_SURFACE && cache_calls==0);
    reset(); input=basic(); input.asset_identity.clear();
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_PROVENANCE && cache_calls==0);
    reset(); input=basic(); input.import_settings.clear();
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_PROVENANCE && cache_calls==0);
    reset(); input=basic(); input.cache_path.clear();
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_PROVENANCE && cache_calls==0);
    reset(); input=basic(); input.max_triangles=513;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_PROVENANCE && cache_calls==0);
    reset(); input=basic(); input.positions[0].x=std::numeric_limits<double>::infinity();
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_SURFACE && cache_calls==0);
    reset(); input=basic(); input.positions[0].x=std::numeric_limits<double>::quiet_NaN();
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::INVALID_SURFACE && cache_calls==0);

    // Unindexed triangles are explicitly normalized before building and hashing.
    reset(); input=basic(); input.indices.clear(); input.is_indexed=false;
    input.positions={{0,0,0},{1,0,0},{0,1,0},{1,1,0},{2,1,0},{1,2,0}};
    // The builder double currently only accepts the four-vertex square fixture;
    // a simulated cached hit still checks normalization and source metadata.
    next_store=GeometryStoreStatus::HIT;
    r=prepare_offline_geometry(input);
    assert(r.status==GeometryPipelineStatus::READY_CACHED && r.generated_indices);
    assert(seen_source.source_triangles == std::vector<std::uint32_t>({0,1,2,3,4,5}));
    assert(seen_settings.back()==0 && builder_calls==0);
    return 0;
}

// Connects standard indexed/unindexed surfaces to optional WGC1 offline preparation.
#include "geometry_import_pipeline.h"

#include <cmath>
#include <limits>
#include <utility>

namespace worlds_geometry {

GeometryPipelineResult prepare_offline_geometry(const GeometryPipelineInput &input) {
    GeometryPipelineResult out;
    const PreparedSurface prepared = prepare_triangle_surface(input.positions.size(),
            input.is_triangles, input.is_indexed, input.indices);
    out.surface_status = prepared.status;
    out.generated_indices = prepared.generated_indices;
    if (prepared.status != SurfaceStatus::OK) {
        return out;
    }
    // WGC1 uses these conservative per-surface diagnostic limits.
    constexpr std::size_t kMaxVertices = 750000;
    constexpr std::size_t kMaxTriangles = 250000;
    if (input.positions.size() > kMaxVertices || prepared.indices.empty() ||
            prepared.indices.size() / 3 > kMaxTriangles) {
        return out;
    }
    for (const Point &p : input.positions) {
        if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z) ||
                !std::isfinite(static_cast<float>(p.x)) ||
                !std::isfinite(static_cast<float>(p.y)) ||
                !std::isfinite(static_cast<float>(p.z))) {
            return out;
        }
    }
    if (input.cache_path.empty() || input.asset_identity.empty() ||
            input.import_settings.empty() || input.generator_version == 0 ||
            input.max_vertices < 3 || input.max_vertices > 256 ||
            input.max_triangles == 0 || input.max_triangles > 512) {
        out.status = GeometryPipelineStatus::INVALID_PROVENANCE;
        return out;
    }

    // Diagnostic-only topology analysis can be expensive on every cache hit.
    // Independently audited meshlet coverage and WGC1 bounds are still mandatory.
    if (input.analyze_boundaries) {
        out.boundaries = extract_mesh_boundaries(input.positions, prepared.indices);
        out.boundaries_analyzed = true;
    }
    GeometryCacheSource source;
    source.positions = input.positions;
    source.source_triangles.reserve(prepared.indices.size());
    for (const std::int32_t index : prepared.indices) {
        source.source_triangles.push_back(static_cast<std::uint32_t>(index));
    }
    source.surface = input.surface;
    source.lod = input.lod;
    source.generator_version = input.generator_version;
    source.max_vertices = input.max_vertices;
    source.max_triangles = input.max_triangles;

    // Include original primitive/index encoding in the import fingerprint. The caller
    // must supply all other geometry-affecting import settings and asset identity.
    std::vector<std::uint8_t> settings = input.import_settings;
    settings.push_back(0x57); // Fixed versioned pipeline-domain suffix: 'W','G','P',1.
    settings.push_back(0x47);
    settings.push_back(0x50);
    settings.push_back(1);
    settings.push_back(static_cast<std::uint8_t>(input.is_indexed));

    // The result owns potentially large decoded buffers; const would force a deep copy.
    GeometryStoreResult store = load_or_build_geometry_cache(input.cache_path,
            std::move(source), input.asset_identity, settings,
            [&input, &prepared]() {
                return build_offline_meshlets(input.positions, prepared.indices,
                        input.max_vertices, input.max_triangles);
            });
    out.store_status = store.status;
    out.build = std::move(store.build);
    switch (store.status) {
        case GeometryStoreStatus::HIT:
            out.status = GeometryPipelineStatus::READY_CACHED;
            break;
        case GeometryStoreStatus::BUILT_STORED:
            out.status = GeometryPipelineStatus::READY_STORED;
            break;
        case GeometryStoreStatus::BUILT_UNSTORED:
            out.status = GeometryPipelineStatus::READY_MEMORY_ONLY;
            break;
        case GeometryStoreStatus::INVALID_SOURCE:
            out.status = GeometryPipelineStatus::INVALID_PROVENANCE;
            break;
        case GeometryStoreStatus::BUILD_FAILED:
            out.status = GeometryPipelineStatus::BUILD_FAILED;
            break;
    }
    // Fail closed even if a storage implementation reports a success incorrectly.
    if ((out.status == GeometryPipelineStatus::READY_CACHED ||
            out.status == GeometryPipelineStatus::READY_STORED ||
            out.status == GeometryPipelineStatus::READY_MEMORY_ONLY) &&
            !(out.build.valid && out.build.coverage.valid)) {
        out.status = GeometryPipelineStatus::BUILD_FAILED;
        out.build = MeshletBuild{};
    }
    return out;
}

const char *geometry_pipeline_status_string(GeometryPipelineStatus status) {
    switch (status) {
        case GeometryPipelineStatus::READY_CACHED: return "READY_CACHED";
        case GeometryPipelineStatus::READY_STORED: return "READY_STORED";
        case GeometryPipelineStatus::READY_MEMORY_ONLY: return "READY_MEMORY_ONLY";
        case GeometryPipelineStatus::INVALID_SURFACE: return "INVALID_SURFACE";
        case GeometryPipelineStatus::INVALID_PROVENANCE: return "INVALID_PROVENANCE";
        case GeometryPipelineStatus::BUILD_FAILED: return "BUILD_FAILED";
    }
    return "UNKNOWN";
}
} // namespace worlds_geometry

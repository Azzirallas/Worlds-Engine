// Offline triangle-surface preparation, seam diagnostics and verified meshlet-cache lookup.
#pragma once

#include "geometry_cache_store.h"
#include "mesh_boundary_extract.h"
#include "mesh_surface_source.h"

#include <cstdint>
#include <filesystem>
#include <vector>

namespace worlds_geometry {

enum class GeometryPipelineStatus {
    READY_CACHED,
    READY_STORED,
    READY_MEMORY_ONLY,
    INVALID_SURFACE,
    INVALID_PROVENANCE,
    BUILD_FAILED,
};

struct GeometryPipelineInput {
    std::vector<Point> positions;
    std::vector<std::int32_t> indices;
    bool is_triangles = true;
    bool is_indexed = true;
    // Topology diagnostics are opt-in: WGC1 source/meshlet validation does not need them.
    bool analyze_boundaries = false;
    std::uint32_t surface = 0;
    std::int32_t lod = -1;
    std::uint32_t generator_version = 1;
    std::uint32_t max_vertices = 64;
    std::uint32_t max_triangles = 124;
    std::vector<std::uint8_t> asset_identity;
    std::vector<std::uint8_t> import_settings;
    std::filesystem::path cache_path;
};

struct GeometryPipelineResult {
    GeometryPipelineStatus status = GeometryPipelineStatus::INVALID_SURFACE;
    SurfaceStatus surface_status = SurfaceStatus::MISSING_VERTICES;
    GeometryStoreStatus store_status = GeometryStoreStatus::INVALID_SOURCE;
    bool generated_indices = false;
    bool boundaries_analyzed = false;
    // Diagnostic only: never certifies cross-LOD seam compatibility or renderability.
    BoundaryExtraction boundaries;
    MeshletBuild build;
};

// No resource mutation, renderer access, Godot allocations or implicit disk path selection.
GeometryPipelineResult prepare_offline_geometry(const GeometryPipelineInput &input);
const char *geometry_pipeline_status_string(GeometryPipelineStatus status);

} // namespace worlds_geometry

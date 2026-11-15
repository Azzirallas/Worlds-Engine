// CPU-only WGC1 cache lookup, regeneration and atomic file publication.
#pragma once

#include "geometry_source_hash.h"

#include <cstdint>
#include <filesystem>
#include <functional>
#include <vector>

namespace worlds_geometry {
enum class GeometryStoreStatus {
    HIT,              // Existing cache accepted by codec and source verification.
    BUILT_STORED,     // Cache miss or corruption, rebuilt and atomically published.
    BUILT_UNSTORED,   // Valid meshlets in memory; disk publication failed.
    BUILD_FAILED,     // Cannot generate a valid cache; use conventional Godot mesh.
    INVALID_SOURCE,   // Invalid geometry or invalid expected provenance.
};

struct GeometryStoreResult {
    GeometryStoreStatus status = GeometryStoreStatus::INVALID_SOURCE;
    MeshletBuild build;
};

// Source hashes are recomputed using original geometry and caller-supplied import bytes.
// Builder is called only on a miss (or invalid stored bytes) and must return valid meshlets.
// Concurrent writers may race, but a reader can never accept partial or wrong-source data.
GeometryStoreResult load_or_build_geometry_cache(
        const std::filesystem::path &cache_path, GeometryCacheSource source,
        const std::vector<std::uint8_t> &asset_bytes,
        const std::vector<std::uint8_t> &settings_bytes,
        const std::function<MeshletBuild()> &builder);

} // namespace worlds_geometry

// WGC1 portable, read-only geometry-cache codec; original imported meshes remain authoritative.
#pragma once

#include "meshlet_builder.h"

#include <array>
#include <cstdint>
#include <vector>

namespace worlds_geometry {
struct GeometryCacheSource {
    // Digests must be independently computed over the source and import/generator settings.
    std::array<std::uint8_t, 32> source_sha256{};
    std::array<std::uint8_t, 32> settings_sha256{};
    std::uint32_t generator_version = 0;
    std::uint32_t surface = 0;
    std::int32_t lod = -1;
    std::uint32_t max_vertices = 64;
    std::uint32_t max_triangles = 124;
    std::vector<Point> positions;
    std::vector<std::uint32_t> source_triangles;
};

enum class GeometryCacheStatus {
    OK,
    INVALID_SOURCE,
    INVALID_MESHLETS,
    INVALID_BOUNDS,
    INVALID_HEADER,
    WRONG_SOURCE,
    BAD_CHECKSUM,
    INVALID_PAYLOAD,
};

struct GeometryCacheBytes {
    GeometryCacheStatus status = GeometryCacheStatus::INVALID_SOURCE;
    std::vector<std::uint8_t> bytes;
};

struct GeometryCacheDecoded {
    GeometryCacheStatus status = GeometryCacheStatus::INVALID_HEADER;
    MeshletBuild build;
};

// Serialization does not write to disk; caller owns atomic cache file publishing.
GeometryCacheBytes encode_geometry_cache(const GeometryCacheSource &source, const MeshletBuild &build);
// Decoding requires the original geometry and independent expected SHA-256 digests.
GeometryCacheDecoded decode_geometry_cache(const GeometryCacheSource &source,
                                           const std::vector<std::uint8_t> &bytes);
const char *geometry_cache_status_string(GeometryCacheStatus status);
} // namespace worlds_geometry

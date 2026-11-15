// Portable SHA-256 and canonical geometry-cache provenance; no Godot dependencies.
#pragma once

#include "geometry_cache.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace worlds_geometry {
// Standard SHA-256 over arbitrary bytes (FIPS 180-4); does not require OpenSSL.
std::array<std::uint8_t, 32> geometry_sha256(const std::uint8_t *data, std::size_t size);

// Hashes canonical position/index data and caller-supplied asset/settings bytes.
// Asset bytes must include any external import identity relevant to the derived geometry.
// Rejects invalid source geometry rather than publishing incomplete provenance.
bool stamp_geometry_cache_source(GeometryCacheSource &source,
                                  const std::vector<std::uint8_t> &asset_bytes,
                                  const std::vector<std::uint8_t> &settings_bytes);

// Recalculate before trusting a cache hit, rather than relying on a caller's stale digests.
bool verify_geometry_cache_source(const GeometryCacheSource &source,
                                   const std::vector<std::uint8_t> &asset_bytes,
                                   const std::vector<std::uint8_t> &settings_bytes);
} // namespace worlds_geometry

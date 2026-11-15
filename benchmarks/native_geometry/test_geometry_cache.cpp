// Standalone deterministic WGC1 round-trip, corruption and source-provenance tests.
#include "worlds_geometry/geometry_cache.h"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <limits>
#include <random>
#include <string>
#include <vector>

using worlds_geometry::GeometryCacheSource;
using worlds_geometry::GeometryCacheStatus;
using worlds_geometry::MeshletBuild;
using worlds_geometry::MeshletInfo;
using worlds_geometry::encode_geometry_cache;
using worlds_geometry::decode_geometry_cache;

namespace {
GeometryCacheSource source() {
    GeometryCacheSource s;
    s.positions = {{0,0,0}, {1,0,0}, {1,1,0}, {0,1,0}};
    s.source_triangles = {0,1,2, 0,2,3};
    s.source_sha256.fill(13);
    s.settings_sha256.fill(29);
    s.generator_version = 2;
    s.surface = 3;
    s.lod = -1;
    return s;
}
MeshletBuild two_meshlets() {
    MeshletBuild b;
    b.valid = true;
    b.status = "OK";
    b.coverage.valid = true;
    b.vertices = {0,1,2, 0,2,3};
    b.triangles = {0,1,2, 0,1,2};
    MeshletInfo m;
    m.range = {0,0,3,1};
    m.center[0] = 0.5f; m.center[1] = 0.5f;
    m.radius = 1.0f;
    m.cone_axis[2] = 1.0f;
    m.cone_cutoff = 1.0f;
    b.meshlets.push_back(m);
    m.range = {3,3,3,1};
    b.meshlets.push_back(m);
    return b;
}
// Regenerate payload CRC so tests prove structural validation independently of the checksum.
void rewrite_crc(std::vector<std::uint8_t> &b) {
    std::uint32_t crc = 0xffffffffu;
    for (std::size_t i = 132; i < b.size(); ++i) {
        crc ^= b[i];
        for (unsigned j = 0; j < 8; ++j) {
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
        }
    }
    crc = ~crc;
    for (unsigned i = 0; i < 4; ++i) { b[20 + i] = std::uint8_t(crc >> (i * 8)); }
}
void mutate_u32(std::vector<std::uint8_t> &b, std::size_t offset, std::uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) { b[offset + i] = std::uint8_t(value >> (i * 8)); }
}
} // namespace

int main() {
    auto s = source();
    auto builder = two_meshlets();
    const auto encoded = encode_geometry_cache(s, builder);
    assert(encoded.status == GeometryCacheStatus::OK);
    assert(encoded.bytes.size() == 132 + 2 * 48 + 6 * 4 + 6);
    const auto decoded = decode_geometry_cache(s, encoded.bytes);
    assert(decoded.status == GeometryCacheStatus::OK && decoded.build.valid);
    assert(decoded.build.meshlets.size() == 2 && decoded.build.coverage.valid);
    assert(decoded.build.vertices == builder.vertices && decoded.build.triangles == builder.triangles);
    assert(encode_geometry_cache(s, decoded.build).bytes == encoded.bytes);
    assert(std::string(worlds_geometry::geometry_cache_status_string(GeometryCacheStatus::OK)) == "OK");
    {
        auto x = s; x.source_sha256[0] ^= 1;
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::WRONG_SOURCE);
        x = s; x.settings_sha256[4] ^= 1;
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::WRONG_SOURCE);
        x = s; ++x.generator_version;
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::WRONG_SOURCE);
        x = s; x.surface = 9;
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::WRONG_SOURCE);
        x = s; x.lod = 1;
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::WRONG_SOURCE);
        x = s; x.max_vertices = 32;
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::WRONG_SOURCE);
        x = s; x.source_triangles = {0,2,3, 0,1,2};
        // A different source with the SAME supplied digest is caught by the re-audit only
        // when triangle contents differ (ordering alone is intentionally equivalent).
        x.source_triangles = {0,1,2, 1,2,3};
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::INVALID_MESHLETS);
    }
    {
        auto x = s; x.source_sha256.fill(0);
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::INVALID_SOURCE);
        x = s; x.positions[0].x = std::numeric_limits<double>::infinity();
        assert(encode_geometry_cache(x, builder).status == GeometryCacheStatus::INVALID_SOURCE);
        x = s; x.source_triangles = {0,1};
        assert(decode_geometry_cache(x, encoded.bytes).status == GeometryCacheStatus::INVALID_SOURCE);
    }
    {
        auto x = builder;
        x.triangles[1] = 2; x.triangles[2] = 1; // Reverse one triangle.
        assert(encode_geometry_cache(s, x).status == GeometryCacheStatus::INVALID_MESHLETS);
        x = builder; x.meshlets[0].range.vertex_offset = 30000000;
        assert(encode_geometry_cache(s, x).status == GeometryCacheStatus::INVALID_MESHLETS);
        x = builder; x.meshlets[0].radius = 0.01f;
        assert(encode_geometry_cache(s, x).status == GeometryCacheStatus::INVALID_BOUNDS);
        x = builder; x.meshlets[0].cone_axis[0] = std::numeric_limits<float>::quiet_NaN();
        assert(encode_geometry_cache(s, x).status == GeometryCacheStatus::INVALID_BOUNDS);
    }
    {
        auto b = encoded.bytes;
        b[0] = 'Z';
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::INVALID_HEADER);
        b = encoded.bytes; b[4] = 2; // Version 2 not supported.
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::INVALID_HEADER);
        b = encoded.bytes; b[12] = 1; // Unknown required flag.
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::INVALID_HEADER);
        b = encoded.bytes; mutate_u32(b, 16, 0xffffffffu);
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::INVALID_HEADER);
        b = encoded.bytes; mutate_u32(b, 116, 0xffffffffu); // Huge claimed meshlet count.
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::INVALID_HEADER);
        b = encoded.bytes; b.back() ^= 1;
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::BAD_CHECKSUM);
        b = encoded.bytes; b[132 + 16] = 0xff; // Corrupt center float, with recomputed CRC.
        b[132 + 17] = 0xff; b[132 + 18] = 0xff; b[132 + 19] = 0x7f;
        rewrite_crc(b);
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::INVALID_BOUNDS);
        b = encoded.bytes; b[132 + 2 * 48 + 6 * 4] = 2; // Change local index.
        rewrite_crc(b);
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::INVALID_MESHLETS);
        for (std::size_t n = 0; n < encoded.bytes.size(); ++n) {
            const std::vector<std::uint8_t> truncated(b.begin(), b.begin() + n);
            assert(decode_geometry_cache(s, truncated).status != GeometryCacheStatus::OK);
        }
        b = encoded.bytes; b.push_back(0);
        assert(decode_geometry_cache(s, b).status == GeometryCacheStatus::INVALID_HEADER);
    }
    {
        // A valid CRC isn't enough: fuzz mutated payloads with a recomputed checksum.
        std::mt19937 rng(0x5ac1e);
        for (int i = 0; i < 700; ++i) {
            auto b = encoded.bytes;
            const auto where = 132 + (rng() % (b.size() - 132));
            b[where] ^= static_cast<std::uint8_t>(1u << (rng() % 8));
            rewrite_crc(b);
            const auto r = decode_geometry_cache(s, b);
            if (r.status == GeometryCacheStatus::OK) {
                assert(r.build.coverage.valid); // Mutation may only affect unreferenced padding, if any.
            }
        }
    }
    return 0;
}

// Versioned little-endian WGC1 meshlet data, bounded parsing and independent triangle audit.
#include "geometry_cache.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>

namespace worlds_geometry {
namespace {
constexpr std::size_t kHeader = 132;
constexpr std::size_t kRecord = 48;
constexpr std::size_t kMaxCache = 24 * 1024 * 1024;
constexpr std::size_t kMaxTriangles = 250000;
constexpr std::size_t kMaxVertices = 750000;

void put_u16(std::vector<std::uint8_t> &out, std::uint16_t v) {
    for (unsigned i = 0; i < 2; ++i) { out.push_back(static_cast<std::uint8_t>(v >> (i * 8))); }
}
void put_u32(std::vector<std::uint8_t> &out, std::uint32_t v) {
    for (unsigned i = 0; i < 4; ++i) { out.push_back(static_cast<std::uint8_t>(v >> (i * 8))); }
}
void put_f32(std::vector<std::uint8_t> &out, float f) {
    std::uint32_t v;
    static_assert(sizeof(v) == sizeof(f), "Expected 32-bit IEEE-like float");
    std::memcpy(&v, &f, sizeof(v));
    put_u32(out, v);
}
bool get_u16(const std::vector<std::uint8_t> &b, std::size_t &at, std::uint16_t &v) {
    if (at > b.size() || b.size() - at < 2) { return false; }
    v = static_cast<std::uint16_t>(b[at]) | static_cast<std::uint16_t>(b[at + 1]) << 8;
    at += 2;
    return true;
}
bool get_u32(const std::vector<std::uint8_t> &b, std::size_t &at, std::uint32_t &v) {
    if (at > b.size() || b.size() - at < 4) { return false; }
    v = 0;
    for (unsigned i = 0; i < 4; ++i) { v |= std::uint32_t(b[at + i]) << (i * 8); }
    at += 4;
    return true;
}
bool get_f32(const std::vector<std::uint8_t> &b, std::size_t &at, float &f) {
    std::uint32_t v;
    if (!get_u32(b, at, v)) { return false; }
    std::memcpy(&f, &v, sizeof(f));
    return true;
}
void patch_u32(std::vector<std::uint8_t> &b, std::size_t at, std::uint32_t v) {
    for (unsigned i = 0; i < 4; ++i) { b[at + i] = static_cast<std::uint8_t>(v >> (i * 8)); }
}
std::uint32_t crc32(const std::vector<std::uint8_t> &b) {
    std::uint32_t crc = 0xffffffffu;
    for (std::size_t i = kHeader; i < b.size(); ++i) {
        crc ^= b[i];
        for (unsigned j = 0; j < 8; ++j) {
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
        }
    }
    return ~crc;
}
bool valid_source(const GeometryCacheSource &s) {
    if (s.generator_version == 0 || s.positions.empty() || s.positions.size() > kMaxVertices ||
            s.source_triangles.empty() || s.source_triangles.size() % 3 != 0 ||
            s.source_triangles.size() / 3 > kMaxTriangles || s.max_vertices < 3 ||
            s.max_vertices > 256 || s.max_triangles == 0 || s.max_triangles > 512 ||
            !std::any_of(s.source_sha256.begin(), s.source_sha256.end(), [](auto b) { return b != 0; }) ||
            !std::any_of(s.settings_sha256.begin(), s.settings_sha256.end(), [](auto b) { return b != 0; })) {
        return false;
    }
    for (const Point &p : s.positions) {
        if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z) ||
                !std::isfinite(static_cast<float>(p.x)) ||
                !std::isfinite(static_cast<float>(p.y)) ||
                !std::isfinite(static_cast<float>(p.z))) {
            return false;
        }
    }
    return true;
}
bool valid_bounds(const GeometryCacheSource &s, const MeshletBuild &build) {
    for (const MeshletInfo &m : build.meshlets) {
        if (!std::isfinite(m.radius) || m.radius < 0 || !std::isfinite(m.cone_cutoff)) {
            return false;
        }
        for (unsigned axis = 0; axis < 3; ++axis) {
            if (!std::isfinite(m.center[axis]) || !std::isfinite(m.cone_axis[axis])) {
                return false;
            }
        }
        // The derived sphere must conservatively contain all referenced source positions.
        for (std::size_t v = 0; v < m.range.vertex_count; ++v) {
            const auto idx = build.vertices[m.range.vertex_offset + v];
            const Point &p = s.positions[idx];
            const double dx = double(static_cast<float>(p.x)) - m.center[0];
            const double dy = double(static_cast<float>(p.y)) - m.center[1];
            const double dz = double(static_cast<float>(p.z)) - m.center[2];
            if (!(std::hypot(dx, dy, dz) <= double(m.radius) + 1e-4 * std::max(1.0, double(m.radius)))) {
                return false;
            }
        }
    }
    return true;
}
bool valid_build(const GeometryCacheSource &s, const MeshletBuild &b) {
    if (b.meshlets.empty() || b.meshlets.size() > kMaxTriangles ||
            b.vertices.size() > kMaxVertices || b.triangles.size() > 3 * kMaxTriangles) {
        return false;
    }
    std::vector<MeshletRange> ranges;
    ranges.reserve(b.meshlets.size());
    for (const MeshletInfo &m : b.meshlets) { ranges.push_back(m.range); }
    return audit_meshlets(s.source_triangles, s.positions.size(), ranges, b.vertices, b.triangles,
                          s.max_vertices, s.max_triangles).valid;
}
bool valid_size(std::uint32_t count, std::uint32_t vertex_refs, std::uint32_t triangle_bytes,
                std::size_t actual) {
    if (count == 0 || count > kMaxTriangles || vertex_refs > kMaxVertices ||
            triangle_bytes > 3 * kMaxTriangles) { return false; }
    const std::uint64_t expected = kHeader + std::uint64_t(count) * kRecord +
                                   std::uint64_t(vertex_refs) * 4 + triangle_bytes;
    return expected <= kMaxCache && expected == actual;
}
} // namespace

GeometryCacheBytes encode_geometry_cache(const GeometryCacheSource &source, const MeshletBuild &build) {
    GeometryCacheBytes result;
    if (!valid_source(source)) { return result; }
    if (!valid_build(source, build)) { result.status = GeometryCacheStatus::INVALID_MESHLETS; return result; }
    if (!valid_bounds(source, build)) { result.status = GeometryCacheStatus::INVALID_BOUNDS; return result; }
    const auto mc = static_cast<std::uint32_t>(build.meshlets.size());
    const auto vc = static_cast<std::uint32_t>(build.vertices.size());
    const auto tc = static_cast<std::uint32_t>(build.triangles.size());
    const std::uint64_t size = kHeader + std::uint64_t(mc) * kRecord + std::uint64_t(vc) * 4 + tc;
    if (size > kMaxCache) { result.status = GeometryCacheStatus::INVALID_MESHLETS; return result; }
    auto &b = result.bytes;
    b.reserve(static_cast<std::size_t>(size));
    b.insert(b.end(), {'W', 'G', 'C', '1'});
    put_u16(b, 1); put_u16(b, 0); // Format version.
    put_u32(b, static_cast<std::uint32_t>(kHeader)); put_u32(b, 0); // Flags.
    put_u32(b, static_cast<std::uint32_t>(size)); put_u32(b, 0); // CRC patched last.
    b.insert(b.end(), source.source_sha256.begin(), source.source_sha256.end());
    b.insert(b.end(), source.settings_sha256.begin(), source.settings_sha256.end());
    put_u32(b, source.generator_version);
    put_u32(b, source.surface);
    put_u32(b, static_cast<std::uint32_t>(source.lod));
    put_u32(b, static_cast<std::uint32_t>(source.positions.size()));
    put_u32(b, static_cast<std::uint32_t>(source.source_triangles.size() / 3));
    put_u32(b, mc); put_u32(b, vc); put_u32(b, tc);
    put_u32(b, source.max_vertices); put_u32(b, source.max_triangles);
    put_u32(b, 0); // Reserved, must remain zero.
    if (b.size() != kHeader) { result.bytes.clear(); result.status = GeometryCacheStatus::INVALID_HEADER; return result; }
    for (const MeshletInfo &m : build.meshlets) {
        put_u32(b, static_cast<std::uint32_t>(m.range.vertex_offset));
        put_u32(b, static_cast<std::uint32_t>(m.range.triangle_offset));
        put_u32(b, m.range.vertex_count); put_u32(b, m.range.triangle_count);
        for (float x : m.center) { put_f32(b, x); }
        put_f32(b, m.radius);
        for (float x : m.cone_axis) { put_f32(b, x); }
        put_f32(b, m.cone_cutoff);
    }
    for (std::uint32_t v : build.vertices) { put_u32(b, v); }
    b.insert(b.end(), build.triangles.begin(), build.triangles.end());
    if (b.size() != size) { result.bytes.clear(); result.status = GeometryCacheStatus::INVALID_PAYLOAD; return result; }
    patch_u32(b, 20, crc32(b));
    result.status = GeometryCacheStatus::OK;
    return result;
}

GeometryCacheDecoded decode_geometry_cache(const GeometryCacheSource &source,
                                           const std::vector<std::uint8_t> &bytes) {
    GeometryCacheDecoded result;
    if (!valid_source(source)) { result.status = GeometryCacheStatus::INVALID_SOURCE; return result; }
    if (bytes.size() < kHeader || bytes.size() > kMaxCache ||
            !std::equal(bytes.begin(), bytes.begin() + 4, "WGC1")) { return result; }
    std::size_t at = 4;
    std::uint16_t major, minor;
    std::uint32_t header, flags, size, crc, generator, surface, lod, vertices, faces;
    std::uint32_t meshlets, vertex_refs, triangle_bytes, maxv, maxt, reserved;
    if (!get_u16(bytes, at, major) || !get_u16(bytes, at, minor) ||
            !get_u32(bytes, at, header) || !get_u32(bytes, at, flags) ||
            !get_u32(bytes, at, size) || !get_u32(bytes, at, crc) ||
            major != 1 || minor != 0 || header != kHeader || flags != 0 || size != bytes.size()) {
        return result;
    }
    const bool hashes_match = std::equal(source.source_sha256.begin(), source.source_sha256.end(),
                                         bytes.begin() + at) &&
                              std::equal(source.settings_sha256.begin(), source.settings_sha256.end(),
                                         bytes.begin() + at + 32);
    at += 64;
    if (!get_u32(bytes, at, generator) || !get_u32(bytes, at, surface) ||
            !get_u32(bytes, at, lod) || !get_u32(bytes, at, vertices) ||
            !get_u32(bytes, at, faces) || !get_u32(bytes, at, meshlets) ||
            !get_u32(bytes, at, vertex_refs) || !get_u32(bytes, at, triangle_bytes) ||
            !get_u32(bytes, at, maxv) || !get_u32(bytes, at, maxt) ||
            !get_u32(bytes, at, reserved) || at != kHeader || reserved != 0 ||
            !valid_size(meshlets, vertex_refs, triangle_bytes, bytes.size())) {
        return result;
    }
    if (!hashes_match || generator != source.generator_version || surface != source.surface ||
            lod != static_cast<std::uint32_t>(source.lod) || vertices != source.positions.size() ||
            faces != source.source_triangles.size() / 3 || maxv != source.max_vertices ||
            maxt != source.max_triangles) {
        result.status = GeometryCacheStatus::WRONG_SOURCE;
        return result;
    }
    if (crc32(bytes) != crc) { result.status = GeometryCacheStatus::BAD_CHECKSUM; return result; }
    auto &b = result.build;
    b.meshlets.reserve(meshlets);
    for (std::uint32_t i = 0; i < meshlets; ++i) {
        MeshletInfo m;
        std::uint32_t vo, to;
        if (!get_u32(bytes, at, vo) || !get_u32(bytes, at, to) ||
                !get_u32(bytes, at, m.range.vertex_count) ||
                !get_u32(bytes, at, m.range.triangle_count)) {
            result.status = GeometryCacheStatus::INVALID_PAYLOAD; return result;
        }
        m.range.vertex_offset = vo; m.range.triangle_offset = to;
        for (float &x : m.center) { if (!get_f32(bytes, at, x)) { return result; } }
        if (!get_f32(bytes, at, m.radius)) { return result; }
        for (float &x : m.cone_axis) { if (!get_f32(bytes, at, x)) { return result; } }
        if (!get_f32(bytes, at, m.cone_cutoff)) { return result; }
        b.meshlets.push_back(m);
    }
    b.vertices.reserve(vertex_refs);
    for (std::uint32_t i = 0; i < vertex_refs; ++i) {
        std::uint32_t v;
        if (!get_u32(bytes, at, v)) { result.status = GeometryCacheStatus::INVALID_PAYLOAD; return result; }
        b.vertices.push_back(v);
    }
    if (at > bytes.size() || bytes.size() - at != triangle_bytes) {
        result.status = GeometryCacheStatus::INVALID_PAYLOAD; return result;
    }
    b.triangles.insert(b.triangles.end(), bytes.begin() + at, bytes.end());
    if (!valid_build(source, b)) {
        result.status = GeometryCacheStatus::INVALID_MESHLETS; return result;
    }
    if (!valid_bounds(source, b)) {
        result.status = GeometryCacheStatus::INVALID_BOUNDS; return result;
    }
    b.coverage.valid = true;
    b.coverage.reason = "OK";
    b.coverage.source_triangles = source.source_triangles.size() / 3;
    b.coverage.output_triangles = b.coverage.source_triangles;
    b.coverage.meshlets = b.meshlets.size();
    for (const auto &m : b.meshlets) { b.coverage.vertex_references += m.range.vertex_count; }
    b.valid = true;
    b.status = "OK";
    result.status = GeometryCacheStatus::OK;
    return result;
}

const char *geometry_cache_status_string(GeometryCacheStatus status) {
    switch (status) {
        case GeometryCacheStatus::OK: return "OK";
        case GeometryCacheStatus::INVALID_SOURCE: return "INVALID_SOURCE";
        case GeometryCacheStatus::INVALID_MESHLETS: return "INVALID_MESHLETS";
        case GeometryCacheStatus::INVALID_BOUNDS: return "INVALID_BOUNDS";
        case GeometryCacheStatus::INVALID_HEADER: return "INVALID_HEADER";
        case GeometryCacheStatus::WRONG_SOURCE: return "WRONG_SOURCE";
        case GeometryCacheStatus::BAD_CHECKSUM: return "BAD_CHECKSUM";
        case GeometryCacheStatus::INVALID_PAYLOAD: return "INVALID_PAYLOAD";
    }
    return "UNKNOWN_STATUS";
}
} // namespace worlds_geometry

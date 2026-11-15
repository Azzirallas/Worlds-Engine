// Independent FIPS SHA-256 implementation and endian-stable mesh provenance.
#include "geometry_source_hash.h"

#include <array>
#include <cmath>
#include <cstring>
#include <limits>

namespace worlds_geometry {
namespace {
constexpr std::uint32_t k[64] = {
    0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
    0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
    0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
    0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
    0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
    0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
    0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
    0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u};
constexpr std::uint32_t iv[8] = {0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,
                                  0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u};
std::uint32_t rotr(std::uint32_t x, unsigned n) { return (x >> n) | (x << (32 - n)); }

class Sha256 {
    std::array<std::uint32_t, 8> state{};
    std::array<std::uint8_t, 64> block{};
    std::size_t buffered = 0;
    std::uint64_t total = 0;
    void compress() {
        std::uint32_t w[64]{};
        for (unsigned i = 0; i < 16; ++i) {
            const unsigned j = i * 4;
            w[i] = std::uint32_t(block[j]) << 24 | std::uint32_t(block[j + 1]) << 16 |
                   std::uint32_t(block[j + 2]) << 8 | std::uint32_t(block[j + 3]);
        }
        for (unsigned i = 16; i < 64; ++i) {
            const auto s0 = rotr(w[i-15],7) ^ rotr(w[i-15],18) ^ (w[i-15] >> 3);
            const auto s1 = rotr(w[i-2],17) ^ rotr(w[i-2],19) ^ (w[i-2] >> 10);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }
        auto a=state[0],b=state[1],c=state[2],d=state[3];
        auto e=state[4],f=state[5],g=state[6],h=state[7];
        for (unsigned i = 0; i < 64; ++i) {
            const auto s1 = rotr(e,6) ^ rotr(e,11) ^ rotr(e,25);
            const auto ch = (e & f) ^ (~e & g);
            const auto t1 = h + s1 + ch + k[i] + w[i];
            const auto s0 = rotr(a,2) ^ rotr(a,13) ^ rotr(a,22);
            const auto maj = (a & b) ^ (a & c) ^ (b & c);
            const auto t2 = s0 + maj;
            h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
        }
        state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;
        state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
    }
public:
    Sha256() { for (unsigned i = 0; i < 8; ++i) { state[i] = iv[i]; } }
    void update(const std::uint8_t *input, std::size_t count) {
        if (count == 0) { return; }
        // SHA-256 message length is represented in bits in a 64-bit field.
        // Caller caps all encoded geometry; this generic API rejects no data silently.
        total += static_cast<std::uint64_t>(count);
        for (std::size_t i = 0; i < count; ++i) {
            block[buffered++] = input[i];
            if (buffered == 64) { compress(); buffered = 0; }
        }
    }
    void u32(std::uint32_t v) {
        std::uint8_t bytes[4]{};
        for (unsigned i=0;i<4;++i) { bytes[i] = static_cast<std::uint8_t>(v >> (8*i)); }
        update(bytes,4);
    }
    void u64(std::uint64_t v) {
        std::uint8_t bytes[8]{};
        for (unsigned i=0;i<8;++i) { bytes[i] = static_cast<std::uint8_t>(v >> (8*i)); }
        update(bytes,8);
    }
    std::array<std::uint8_t,32> finish() {
        const std::uint64_t bits = total * 8;
        block[buffered++] = 0x80;
        if (buffered > 56) {
            while (buffered < 64) { block[buffered++] = 0; }
            compress(); buffered = 0;
        }
        while (buffered < 56) { block[buffered++] = 0; }
        for (unsigned i=0;i<8;++i) { block[56+i] = static_cast<std::uint8_t>(bits >> (56 - 8*i)); }
        compress();
        std::array<std::uint8_t,32> digest{};
        for (unsigned i=0;i<8;++i) {
            for (unsigned j=0;j<4;++j) { digest[4*i+j] = static_cast<std::uint8_t>(state[i] >> (24 - 8*j)); }
        }
        return digest;
    }
};

void bytes(Sha256 &hash, const std::vector<std::uint8_t> &data) {
    hash.u64(data.size());
    hash.update(data.data(), data.size());
}

bool valid_geometry(const GeometryCacheSource &s) {
    static_assert(sizeof(double)==8 && std::numeric_limits<double>::is_iec559,
                  "Canonical geometry digest requires IEEE-754 binary64");
    if (s.generator_version == 0 || s.positions.empty() || s.positions.size() > 750000 ||
            s.source_triangles.empty() || s.source_triangles.size() % 3 != 0 ||
            s.source_triangles.size()/3 > 250000 || s.max_vertices < 3 || s.max_vertices > 256 ||
            s.max_triangles == 0 || s.max_triangles > 512) { return false; }
    for (const Point &p : s.positions) {
        if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z) ||
            !std::isfinite(static_cast<float>(p.x)) ||
            !std::isfinite(static_cast<float>(p.y)) ||
            !std::isfinite(static_cast<float>(p.z))) { return false; }
    }
    for (const auto index : s.source_triangles) {
        if (index >= s.positions.size()) { return false; }
    }
    return true;
}

void hash_coord(Sha256 &hash, double value) {
    // -0 and +0 have the same geometry. All other finite binary64 bits are preserved.
    if (value == 0.0) { value = 0.0; }
    std::uint64_t bits;
    std::memcpy(&bits,&value,sizeof(bits));
    hash.u64(bits);
}
} // namespace

std::array<std::uint8_t, 32> geometry_sha256(const std::uint8_t *data, std::size_t size) {
    Sha256 hash;
    if (size != 0 && data == nullptr) { return {}; }
    hash.update(data,size);
    return hash.finish();
}

bool stamp_geometry_cache_source(GeometryCacheSource &source,
                                  const std::vector<std::uint8_t> &asset_bytes,
                                  const std::vector<std::uint8_t> &settings_bytes) {
    if (!valid_geometry(source)) { return false; }
    Sha256 geometry;
    constexpr std::uint8_t geometry_domain[] = "Worlds.WGC1.Geometry.V1";
    geometry.update(geometry_domain,sizeof(geometry_domain));
    geometry.u64(source.positions.size());
    for (const Point &p : source.positions) {
        hash_coord(geometry,p.x);hash_coord(geometry,p.y);hash_coord(geometry,p.z);
    }
    geometry.u64(source.source_triangles.size());
    for (std::uint32_t i : source.source_triangles) { geometry.u32(i); }
    bytes(geometry,asset_bytes);
    Sha256 settings;
    constexpr std::uint8_t settings_domain[] = "Worlds.WGC1.Settings.V1";
    settings.update(settings_domain,sizeof(settings_domain));
    settings.u32(source.generator_version);
    settings.u32(source.surface);
    settings.u32(static_cast<std::uint32_t>(source.lod));
    settings.u32(source.max_vertices);
    settings.u32(source.max_triangles);
    bytes(settings,settings_bytes);
    source.source_sha256 = geometry.finish();
    source.settings_sha256 = settings.finish();
    return true;
}

bool verify_geometry_cache_source(const GeometryCacheSource &source,
                                   const std::vector<std::uint8_t> &asset_bytes,
                                   const std::vector<std::uint8_t> &settings_bytes) {
    GeometryCacheSource check = source;
    if (!stamp_geometry_cache_source(check,asset_bytes,settings_bytes)) { return false; }
    return check.source_sha256 == source.source_sha256 &&
           check.settings_sha256 == source.settings_sha256;
}
} // namespace worlds_geometry

// CPU-only compaction proof: retain local oriented triangles, discard only unused gaps.
#include "worlds_geometry/meshlet_payload.h"

#include <array>
#include <cassert>
#include <limits>
#include <random>
#include <vector>

using namespace worlds_geometry;
namespace {
MeshletBuild sample() {
    MeshletBuild b;
    b.valid = true;
    b.coverage.valid = true;
    b.coverage.meshlets = 2;
    b.coverage.source_triangles = 2;
    b.coverage.output_triangles = 2;
    b.coverage.vertex_references = 6;
    b.status = "OK";
    b.vertices = {99, 0, 1, 2, 88, 77, 0, 2, 3, 66, 55, 44};
    b.triangles = {99, 77, 0, 1, 2, 88, 66, 0, 1, 2, 55};
    MeshletInfo a;
    a.range = {1, 2, 3, 1};
    b.meshlets.push_back(a);
    a.range = {6, 7, 3, 1};
    b.meshlets.push_back(a);
    return b;
}
// Reconstruct every oriented global triangle; compaction must preserve this stream.
std::vector<std::array<std::uint32_t, 3>> reconstructed(const MeshletBuild &b) {
    std::vector<std::array<std::uint32_t, 3>> tris;
    for (const auto &m : b.meshlets) {
        for (std::size_t t = 0; t < m.range.triangle_count; ++t) {
            std::array<std::uint32_t, 3> tri{};
            for (std::size_t corner = 0; corner < 3; ++corner) {
                const auto local = b.triangles[m.range.triangle_offset + 3 * t + corner];
                assert(local < m.range.vertex_count);
                tri[corner] = b.vertices[m.range.vertex_offset + local];
            }
            tris.push_back(tri);
        }
    }
    return tris;
}
}
int main() {
    {
        auto b = sample();
        const auto original_triangles = reconstructed(b);
        assert(compact_meshlet_payload(b));
        assert(reconstructed(b) == original_triangles);
        assert(b.vertices == std::vector<std::uint32_t>({0,1,2,0,2,3}));
        assert(b.triangles == std::vector<std::uint8_t>({0,1,2,0,1,2}));
        assert(b.meshlets[0].range.vertex_offset == 0 && b.meshlets[0].range.triangle_offset == 0);
        assert(b.meshlets[1].range.vertex_offset == 3 && b.meshlets[1].range.triangle_offset == 3);
        assert(b.coverage.source_triangles == 2 && b.coverage.vertex_references == 6);
        assert(compact_meshlet_payload(b)); // Idempotent with already packed storage.
        assert(b.vertices.size() == 6 && b.triangles.size() == 6);
    }
    {
        auto b = sample();
        b.valid = false;
        assert(!compact_meshlet_payload(b));
        assert(b.vertices.size() == 12 && b.meshlets[0].range.vertex_offset == 1);
    }
    {
        auto b = sample();
        b.coverage.valid = false;
        assert(!compact_meshlet_payload(b));
    }
    {
        auto b = sample();
        b.meshlets[0].range.vertex_offset = std::numeric_limits<std::size_t>::max();
        assert(!compact_meshlet_payload(b));
        assert(b.vertices.size() == 12 && b.meshlets[0].range.vertex_offset == std::numeric_limits<std::size_t>::max());
    }
    {
        auto b = sample();
        b.meshlets[1].range.triangle_offset = 9;
        assert(!compact_meshlet_payload(b)); // Second span would overrun the source array.
        assert(b.triangles.size() == 11 && b.meshlets[0].range.vertex_offset == 1);
    }
    {
        auto b = sample();
        b.meshlets[1].range.vertex_offset = 2;
        assert(!compact_meshlet_payload(b)); // Overlapping vertex spans.
        assert(b.vertices.size() == 12);
    }
    {
        auto b = sample();
        b.meshlets[1].range.triangle_offset = 3;
        assert(!compact_meshlet_payload(b)); // Overlapping triangle spans.
    }
    {
        auto b = sample();
        b.meshlets[0].range.vertex_count = 0;
        assert(!compact_meshlet_payload(b));
    }
    {
        auto b = sample();
        b.meshlets.clear();
        assert(!compact_meshlet_payload(b));
    }
    // Multi-cluster padding fixtures: varying gaps, meshlets and global IDs.
    std::mt19937 rng(0x67c01);
    for (int iteration = 0; iteration < 900; ++iteration) {
        MeshletBuild b;
        b.valid = true;
        b.coverage.valid = true;
        const int clusters = 1 + int(rng() % 40);
        for (int n = 0; n < clusters; ++n) {
            const int vp = int(rng() % 11);
            const int tp = int(rng() % 11);
            for (int k = 0; k < vp; ++k) { b.vertices.push_back(777u); }
            for (int k = 0; k < tp; ++k) { b.triangles.push_back(255u); }
            MeshletInfo m;
            m.range = {b.vertices.size(), b.triangles.size(), 3, 1};
            const auto base = std::uint32_t(n * 3 + iteration * 123);
            b.vertices.insert(b.vertices.end(), {base, base + 1, base + 2});
            b.triangles.insert(b.triangles.end(), {0,1,2});
            b.meshlets.push_back(m);
        }
        b.vertices.insert(b.vertices.end(), 37, 999u);
        b.triangles.insert(b.triangles.end(), 19, 255u);
        const auto before = reconstructed(b);
        assert(compact_meshlet_payload(b));
        assert(reconstructed(b) == before);
        assert(b.vertices.size() == std::size_t(clusters * 3));
        assert(b.triangles.size() == std::size_t(clusters * 3));
        assert(compact_meshlet_payload(b));
        assert(reconstructed(b) == before);
    }
    return 0;
}

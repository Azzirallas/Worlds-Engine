// Run native meshlet partition correctness checks without Godot or GPU.
#include "meshlet_contract.h"
#include <cassert>
#include <cstdint>
#include <limits>
#include <random>
#include <vector>
#include <string>

using worlds_geometry::MeshletRange;
using worlds_geometry::audit_meshlets;

int main() {
    const std::vector<std::uint32_t> source{0, 1, 2, 3, 4, 5, 0, 2, 6};
    const std::vector<MeshletRange> regions{{0, 0, 6, 2}, {6, 6, 3, 1}};
    const std::vector<std::uint32_t> vertex_map{0, 1, 2, 3, 4, 5, 0, 2, 6};
    const std::vector<std::uint8_t> packed{0, 1, 2, 3, 4, 5, 0, 1, 2};
    auto check = [&](const auto &src, const auto &groups, const auto &verts, const auto &tris,
                     std::size_t max_v = 7, std::size_t max_t = 2) {
        return audit_meshlets(src, 7, groups, verts, tris, std::uint32_t(max_v), std::uint32_t(max_t));
    };
    assert(check(source, regions, vertex_map, packed).valid);
    assert(std::string(check(source, regions, vertex_map, packed).reason) == "OK");
    { // Preserve cyclic winding rotations.
        auto bytes = packed; bytes[0] = 1; bytes[1] = 2; bytes[2] = 0;
        assert(check(source, regions, vertex_map, bytes).valid);
    }
    { // Reversed winding must fail even if vertices match.
        auto bytes = packed; bytes[1] = 2; bytes[2] = 1;
        assert(!check(source, regions, vertex_map, bytes).valid);
    }
    { // Duplicate triangle substituted for a different triangle must fail.
        auto verts = vertex_map; verts[6] = 0; verts[7] = 1; verts[8] = 2;
        assert(!check(source, regions, verts, packed).valid);
    }
    { auto groups = regions; groups[1].triangle_count = 0;
      assert(!check(source, groups, vertex_map, packed).valid); }
    { auto groups = regions; groups[0].vertex_offset = std::numeric_limits<std::size_t>::max();
      assert(!check(source, groups, vertex_map, packed).valid); }
    { auto groups = regions; groups[1].triangle_offset = 3;
      assert(!check(source, groups, vertex_map, packed).valid); }
    { auto groups = regions; groups[1].vertex_offset = 3;
      assert(!check(source, groups, vertex_map, packed).valid); }
    { auto verts = vertex_map; verts[6] = 100;
      assert(!check(source, regions, verts, packed).valid); }
    { auto verts = vertex_map; verts[7] = 0;
      assert(!check(source, regions, verts, packed).valid); }
    { auto bytes = packed; bytes[7] = 5;
      assert(!check(source, regions, vertex_map, bytes).valid); }
    { auto bytes = packed; bytes[8] = 1;
      assert(!check(source, regions, vertex_map, bytes).valid); }
    { auto src = source; src.push_back(0);
      assert(!check(src, regions, vertex_map, packed).valid); }
    { auto src = source; src[0] = 7;
      assert(!check(src, regions, vertex_map, packed).valid); }
    { auto src = source; src[1] = 0;
      assert(!check(src, regions, vertex_map, packed).valid); }
    { auto groups = regions; groups[0].triangle_count = 3;
      assert(!check(source, groups, vertex_map, packed).valid); }
    { auto groups = regions; groups[0].vertex_count = 2;
      assert(!check(source, groups, vertex_map, packed).valid); }
    { assert(!audit_meshlets(source, 7, regions, vertex_map, packed, 2, 2).valid); }
    { assert(!audit_meshlets(source, 7, regions, vertex_map, packed, 257, 2).valid); }
    { assert(!audit_meshlets(source, 7, regions, vertex_map, packed, 7, 513).valid); }
    { assert(!audit_meshlets({}, 7, {}, {}, {}, 7, 2).valid); }
    { // Duplicate input triangles are allowed, but must be represented twice.
        const std::vector<std::uint32_t> duplicate{0, 1, 2, 0, 1, 2};
        const std::vector<MeshletRange> one{{0, 0, 3, 2}};
        const std::vector<std::uint8_t> tri{0, 1, 2, 0, 1, 2};
        assert(check(duplicate, one, std::vector<std::uint32_t>{0, 1, 2}, tri).valid);
        assert(!check(duplicate, one, std::vector<std::uint32_t>{0, 1, 2}, std::vector<std::uint8_t>{0, 1, 2, 0, 2, 1}).valid);
    }
    { // Random 800 valid disjoint, exhaustive partitions with varied local maps.
        std::mt19937 rng(8891);
        for (int rep = 0; rep < 800; ++rep) {
            const std::uint32_t count = 1 + rng() % 30;
            std::vector<std::uint32_t> src;
            std::vector<MeshletRange> groups;
            std::vector<std::uint32_t> verts;
            std::vector<std::uint8_t> local;
            for (std::uint32_t i = 0; i < count; ++i) {
                const std::uint32_t base = i * 3;
                src.insert(src.end(), {base, base + 1, base + 2});
                groups.push_back({verts.size(), local.size(), 3, 1});
                verts.insert(verts.end(), {base, base + 1, base + 2});
                local.insert(local.end(), {0, 1, 2});
            }
            auto result = audit_meshlets(src, count * 3, groups, verts, local, 64, 64);
            assert(result.valid && result.meshlets == count && result.output_triangles == count);
            local[local.size() - 1] = 1;
            assert(!audit_meshlets(src, count * 3, groups, verts, local, 64, 64).valid);
        }
    }
    return 0;
}

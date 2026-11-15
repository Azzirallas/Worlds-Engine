// Standalone native WGC1 URI traversal and path-shape regression tests.
#include "worlds_geometry/geometry_cache_uri.h"

#include <cassert>
#include <random>
#include <string>

using worlds_geometry::valid_geometry_cache_uri;

int main() {
    const std::string root = "user://worlds_geometry_cache/";
    for (const char *name : {"mesh.wgc1", "mesh-01.wgc1", "r0/mesh_2.wgc1",
                                     "nested/region_01/LOD-2.wgc1"}) {
        assert(valid_geometry_cache_uri(root + name));
    }
    for (const char *name : {"", ".wgc1", "folder/.wgc1", "../escape.wgc1",
                                     "foo/../escape.wgc1", "foo//bar.wgc1", "/root.wgc1",
                                     "folder/.hidden.wgc1", "folder/../../x.wgc1", "x.WGC1",
                                     "x.wgc1/extra", "x.wgc1.exe", "x\\y.wgc1", "x:y.wgc1",
                                     "x%2fy.wgc1", "hello world.wgc1", "abc\nxyz.wgc1"}) {
        assert(!valid_geometry_cache_uri(root + name));
    }
    assert(!valid_geometry_cache_uri("res://worlds_geometry_cache/a.wgc1"));
    assert(!valid_geometry_cache_uri("user://other_cache/a.wgc1"));
    assert(!valid_geometry_cache_uri("user://worlds_geometry_cache../a.wgc1"));
    assert(!valid_geometry_cache_uri(root + std::string(235, 'a') + ".wgc1"));

    std::mt19937 random(0x5fe512);
    const std::string alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
    for (int trial = 0; trial < 1500; ++trial) {
        std::string name;
        const int segments = 1 + int(random() % 4);
        for (int segment = 0; segment < segments; ++segment) {
            if (segment != 0) { name += '/'; }
            const int length = 1 + int(random() % 20);
            for (int j = 0; j < length; ++j) {
                name += alphabet[random() % alphabet.size()];
            }
        }
        assert(valid_geometry_cache_uri(root + name + ".wgc1"));
        const std::size_t location = random() % name.size();
        name[location] = '.'; // Every arbitrary dot before extension is forbidden.
        assert(!valid_geometry_cache_uri(root + name + ".wgc1"));
    }
    return 0;
}

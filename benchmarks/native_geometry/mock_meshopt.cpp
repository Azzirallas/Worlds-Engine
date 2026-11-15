// Test double for API boundary; NOT a substitute for meshoptimizer verification.
#include "mock_include/thirdparty/meshoptimizer/meshoptimizer.h"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>

int meshopt_test_mode = 0;
size_t meshopt_buildMeshletsBound(size_t index_count, size_t, size_t) { return index_count / 3; }
size_t meshopt_buildMeshlets(meshopt_Meshlet* meshlets, unsigned int* verts,
                            unsigned char* tris, const unsigned int* indices,
                            size_t count, const float*, size_t, size_t,
                            size_t max_vertices, size_t max_triangles, float) {
    assert(max_vertices >= 3 && max_triangles >= 1);
    for (size_t i = 0; i < count / 3; ++i) {
        meshlets[i] = {unsigned(i * 3), unsigned(i * 3), 3, 1};
        for (size_t j = 0; j < 3; ++j) {
            verts[i * 3 + j] = indices[i * 3 + j];
            tris[i * 3 + j] = static_cast<unsigned char>(j);
        }
    }
    if (meshopt_test_mode == 1 && count >= 3) {
        std::swap(tris[0], tris[1]); // Damaged winding: independent audit must reject.
    }
    return count / 3;
}
meshopt_Bounds meshopt_computeMeshletBounds(const unsigned int* vertices,
                                           const unsigned char* triangles, size_t count,
                                           const float* positions, size_t n, size_t stride) {
    assert(count > 0 && n > 0 && stride == 12);
    meshopt_Bounds b{};
    float lo[3]{1e20f, 1e20f, 1e20f}, hi[3]{-1e20f, -1e20f, -1e20f};
    for (size_t i = 0; i < count * 3; i++) {
        const unsigned int v = vertices[triangles[i]];
        assert(v < n);
        for (int k = 0; k < 3; k++) {
            float f = positions[v * 3 + k];
            lo[k] = std::min(lo[k], f); hi[k] = std::max(hi[k], f);
        }
    }
    for (int k = 0; k < 3; k++) b.center[k] = (lo[k] + hi[k]) / 2;
    b.radius = meshopt_test_mode == 2 ? std::numeric_limits<float>::quiet_NaN() : 1.0f;
    b.cone_axis[2] = 1.0f;
    return b;
}

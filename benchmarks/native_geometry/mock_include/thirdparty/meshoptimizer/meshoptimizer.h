// COMPILE-ONLY fake vendor surface matching the checked Godot meshoptimizer API.
#pragma once
#include <cstddef>
struct meshopt_Meshlet {
    unsigned int vertex_offset;
    unsigned int triangle_offset;
    unsigned int vertex_count;
    unsigned int triangle_count;
};
struct meshopt_Bounds {
    float center[3]; float radius;
    float cone_apex[3]; float cone_axis[3]; float cone_cutoff;
    signed char cone_axis_s8[3]; signed char cone_cutoff_s8;
};
extern "C" {
size_t meshopt_buildMeshletsBound(size_t index_count, size_t max_vertices, size_t max_triangles);
size_t meshopt_buildMeshlets(meshopt_Meshlet*, unsigned int*, unsigned char*,
                             const unsigned int*, size_t, const float*, size_t,
                             size_t, size_t, size_t, float);
meshopt_Bounds meshopt_computeMeshletBounds(const unsigned int*, const unsigned char*,
                                            size_t, const float*, size_t, size_t);
}

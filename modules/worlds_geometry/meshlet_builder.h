// Offline meshoptimizer meshlet generation with independent coverage certification.
#pragma once
#include "meshlet_contract.h"
#include "mesh_edge_audit.h"

#include <cstdint>
#include <vector>

namespace worlds_geometry {
struct MeshletInfo {
    MeshletRange range;
    float center[3]{};
    float radius = 0;
    float cone_axis[3]{};
    float cone_cutoff = 0;
};

struct MeshletBuild {
    const char *status = "INVALID_INPUT";
    bool valid = false;
    std::vector<MeshletInfo> meshlets;
    std::vector<std::uint32_t> vertices;
    std::vector<std::uint8_t> triangles;
    MeshletAudit coverage;
};

// Does not simplify, rewrite or replace the source triangle stream.
MeshletBuild build_offline_meshlets(const std::vector<Point> &positions,
                                   const std::vector<std::int32_t> &indices,
                                   std::uint32_t max_vertices = 64,
                                   std::uint32_t max_triangles = 124);
} // namespace worlds_geometry

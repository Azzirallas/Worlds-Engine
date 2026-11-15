// Extract conservative oriented boundary loops from real indexed triangle surfaces.
#pragma once

#include "mesh_edge_audit.h"

#include <cstdint>
#include <vector>

namespace worlds_geometry {
enum class BoundaryStatus {
    OK,
    INVALID_SURFACE,
    NONMANIFOLD_SURFACE,
    AMBIGUOUS_BOUNDARY,
};

struct BoundaryChain {
    // Canonical position IDs, ordered by triangle winding; closed loops omit a repeated end.
    std::vector<std::int32_t> vertex_ids;
    bool closed = false;
};

struct BoundaryExtraction {
    BoundaryStatus status = BoundaryStatus::INVALID_SURFACE;
    std::vector<Point> positions; // Original local-space coordinates, exact-position welded for analysis.
    std::vector<BoundaryChain> chains;
    std::uint64_t coincident_vertex_duplicates = 0;
    std::uint64_t internal_edges = 0;
    std::uint64_t boundary_edges = 0;
};

// Rejects degenerate faces, inconsistent winding, non-manifold edges and branched borders.
// This is a read-only diagnostic, NOT proof that a mesh is watertight or LOD-compatible.
BoundaryExtraction extract_mesh_boundaries(const std::vector<Point> &positions,
                                           const std::vector<std::int32_t> &indices);
const char *boundary_status_string(BoundaryStatus status);
} // namespace worlds_geometry

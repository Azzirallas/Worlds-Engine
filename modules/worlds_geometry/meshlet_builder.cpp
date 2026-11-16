// Uses Godot's existing meshoptimizer library; rejects unverified output.
#include "meshlet_builder.h"
#include "mesh_surface_source.h"
#include "meshlet_payload.h"

#include <thirdparty/meshoptimizer/meshoptimizer.h>

#include <cmath>

namespace worlds_geometry {
MeshletBuild build_offline_meshlets(const std::vector<Point> &positions,
                                   const std::vector<std::int32_t> &indices,
                                   std::uint32_t max_vertices,
                                   std::uint32_t max_triangles) {
    MeshletBuild result;
    if (max_vertices < 3 || max_vertices > 256 || max_triangles < 1 || max_triangles > 512) {
        result.status = "INVALID_LIMITS";
        return result;
    }
    // Diagnostic-specific work ceiling; no unbounded allocations via editor scripts.
    constexpr std::size_t kMaxTriangles = 250000;
    if (positions.size() > 750000 || indices.size() > kMaxTriangles * 3) {
        result.status = "DIAGNOSTIC_CAP";
        return result;
    }
    const PreparedSurface prepared = prepare_triangle_surface(positions.size(), true,
                                                               !indices.empty(), indices);
    if (prepared.status != SurfaceStatus::OK) {
        result.status = surface_status_string(prepared.status);
        return result;
    }
    std::vector<float> vertex_data;
    vertex_data.reserve(positions.size() * 3);
    for (const auto &p : positions) {
        if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z)) {
            result.status = "NONFINITE_POSITION";
            return result;
        }
        const float x = static_cast<float>(p.x), y = static_cast<float>(p.y), z = static_cast<float>(p.z);
        if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
            result.status = "FLOAT_OVERFLOW";
            return result;
        }
        vertex_data.insert(vertex_data.end(), {x, y, z});
    }
    std::vector<unsigned int> unsigned_indices;
    unsigned_indices.reserve(prepared.indices.size());
    for (std::int32_t index : prepared.indices) {
        unsigned_indices.push_back(static_cast<unsigned int>(index));
    }
    // Reject topology meshoptimizer is not being asked to simplify or repair.
    for (std::size_t i = 0; i < unsigned_indices.size(); i += 3) {
        const auto a = unsigned_indices[i], b = unsigned_indices[i + 1], c = unsigned_indices[i + 2];
        if (a == b || b == c || c == a) {
            result.status = "DEGENERATE_SOURCE";
            return result;
        }
        const float *pa = &vertex_data[3 * a], *pb = &vertex_data[3 * b], *pc = &vertex_data[3 * c];
        const double ux = double(pb[0]) - pa[0], uy = double(pb[1]) - pa[1], uz = double(pb[2]) - pa[2];
        const double vx = double(pc[0]) - pa[0], vy = double(pc[1]) - pa[1], vz = double(pc[2]) - pa[2];
        const double cx = uy * vz - uz * vy, cy = uz * vx - ux * vz, cz = ux * vy - uy * vx;
        if (!(cx != 0 || cy != 0 || cz != 0) ||
                !std::isfinite(cx) || !std::isfinite(cy) || !std::isfinite(cz)) {
            result.status = "DEGENERATE_SOURCE";
            return result;
        }
    }
    const std::size_t bound = meshopt_buildMeshletsBound(unsigned_indices.size(), max_vertices, max_triangles);
    if (bound == 0 || bound > unsigned_indices.size()) {
        result.status = "INVALID_BUILDER_BOUND";
        return result;
    }
    std::vector<meshopt_Meshlet> raw(bound);
    result.vertices.resize(unsigned_indices.size());
    result.triangles.resize(unsigned_indices.size());
    const size_t count = meshopt_buildMeshlets(raw.data(), result.vertices.data(), result.triangles.data(),
                                               unsigned_indices.data(), unsigned_indices.size(),
                                               vertex_data.data(), positions.size(), sizeof(float) * 3,
                                               max_vertices, max_triangles, 0.0f);
    if (count == 0 || count > bound) {
        result.status = "BUILDER_FAILED";
        return result;
    }
    std::vector<MeshletRange> ranges;
    ranges.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        const meshopt_Meshlet &m = raw[i];
        ranges.push_back({m.vertex_offset, m.triangle_offset, m.vertex_count, m.triangle_count});
    }
    result.coverage = audit_meshlets(unsigned_indices, positions.size(), ranges,
                                     result.vertices, result.triangles, max_vertices, max_triangles);
    if (!result.coverage.valid) {
        result.status = result.coverage.reason;
        return result;
    }
    for (size_t i = 0; i < count; ++i) {
        const meshopt_Meshlet &m = raw[i];
        const meshopt_Bounds bounds = meshopt_computeMeshletBounds(
                result.vertices.data() + m.vertex_offset, result.triangles.data() + m.triangle_offset,
                m.triangle_count, vertex_data.data(), positions.size(), sizeof(float) * 3);
        if (!(std::isfinite(bounds.radius) && bounds.radius >= 0.0f &&
                std::isfinite(bounds.cone_cutoff))) {
            result.status = "INVALID_BOUNDS";
            return result;
        }
        MeshletInfo item;
        item.range = ranges[i];
        item.radius = bounds.radius;
        item.cone_cutoff = bounds.cone_cutoff;
        for (int k = 0; k < 3; ++k) {
            if (!std::isfinite(bounds.center[k]) || !std::isfinite(bounds.cone_axis[k])) {
                result.status = "INVALID_BOUNDS";
                return result;
            }
            item.center[k] = bounds.center[k];
            item.cone_axis[k] = bounds.cone_axis[k];
        }
        result.meshlets.push_back(item);
    }
    // Compact only after the vendor bounds and independent coverage audit succeed.
    // Meshoptimizer's output arrays are initially sized to index_count capacity;
    // do not carry their unused tails into WGC1 or later GPU staging.
    result.valid = true;
    if (!compact_meshlet_payload(result)) {
        result.valid = false;
        result.status = "INVALID_MESHLET_STORAGE";
        return result;
    }
    result.status = "OK";
    return result;
}
} // namespace worlds_geometry

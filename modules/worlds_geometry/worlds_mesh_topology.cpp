// Bridges Godot packed mesh arrays to the independently compiled CPU auditor.
#include "worlds_mesh_topology.h"
#include "mesh_edge_audit.h"

#include "core/object/class_db.h"

void WorldsMeshTopology::_bind_methods() {
    ClassDB::bind_method(D_METHOD("analyze_indexed_surface", "vertices", "indices"),
            &WorldsMeshTopology::analyze_indexed_surface);
}

Dictionary WorldsMeshTopology::analyze_indexed_surface(const PackedVector3Array &p_vertices,
                                                        const PackedInt32Array &p_indices) const {
    std::vector<worlds_geometry::Point> positions;
    positions.reserve(p_vertices.size());
    for (int i = 0; i < p_vertices.size(); ++i) {
        const Vector3 v = p_vertices[i];
        positions.push_back({ static_cast<double>(v.x), static_cast<double>(v.y), static_cast<double>(v.z) });
    }

    std::vector<std::int32_t> indices;
    indices.reserve(p_indices.size());
    for (int i = 0; i < p_indices.size(); ++i) {
        indices.push_back(p_indices[i]);
    }

    const worlds_geometry::Report r = worlds_geometry::analyze_indexed_triangles(positions, indices);
    Dictionary result;
    result["vertex_count"] = static_cast<int64_t>(r.vertex_count);
    result["triangle_count"] = static_cast<int64_t>(r.triangle_count);
    result["incomplete_indices"] = static_cast<int64_t>(r.incomplete_indices);
    result["invalid_vertices"] = static_cast<int64_t>(r.invalid_vertices);
    result["invalid_triangles"] = static_cast<int64_t>(r.invalid_triangles);
    result["zero_area_triangles"] = static_cast<int64_t>(r.zero_area_triangles);
    result["duplicate_triangles"] = static_cast<int64_t>(r.duplicate_triangles);
    result["unique_edges"] = static_cast<int64_t>(r.unique_edges);
    result["open_edges"] = static_cast<int64_t>(r.open_edges);
    result["nonmanifold_edges"] = static_cast<int64_t>(r.nonmanifold_edges);
    result["orientation_conflicts"] = static_cast<int64_t>(r.orientation_conflicts);
    result["valid_input"] = r.valid_input;
    result["closed_oriented_2manifold"] = r.closed_oriented_2manifold;
    return result;
}

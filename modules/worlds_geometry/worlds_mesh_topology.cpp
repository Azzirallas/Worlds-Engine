// Bridges Godot mesh arrays to the standalone topology and border auditors.
#include "worlds_mesh_topology.h"
#include "mesh_border_audit.h"
#include "mesh_edge_audit.h"

#include "core/object/class_db.h"

namespace {
// Copy once into engine-independent double-precision positions.
std::vector<worlds_geometry::Point> to_points(const PackedVector3Array &p_vertices) {
    std::vector<worlds_geometry::Point> result;
    result.reserve(p_vertices.size());
    for (int i = 0; i < p_vertices.size(); ++i) {
        const Vector3 v = p_vertices[i];
        result.push_back({ static_cast<double>(v.x), static_cast<double>(v.y), static_cast<double>(v.z) });
    }
    return result;
}

// Preserve signed indices so malformed negative values can be reported.
std::vector<std::int32_t> to_indices(const PackedInt32Array &p_indices) {
    std::vector<std::int32_t> result;
    result.reserve(p_indices.size());
    for (int i = 0; i < p_indices.size(); ++i) {
        result.push_back(p_indices[i]);
    }
    return result;
}

// Keep one stable script-facing schema for raw and welded reports.
Dictionary report_dictionary(const worlds_geometry::Report &r) {
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
} // namespace

void WorldsMeshTopology::_bind_methods() {
    ClassDB::bind_method(D_METHOD("analyze_indexed_surface", "vertices", "indices"),
            &WorldsMeshTopology::analyze_indexed_surface);
    ClassDB::bind_method(D_METHOD("analyze_position_surface", "vertices", "indices"),
            &WorldsMeshTopology::analyze_position_surface);
    ClassDB::bind_method(D_METHOD("compare_border_samples", "border_a", "border_b", "tolerance"),
            &WorldsMeshTopology::compare_border_samples, DEFVAL(0.0));
}

Dictionary WorldsMeshTopology::analyze_indexed_surface(const PackedVector3Array &p_vertices,
                                                        const PackedInt32Array &p_indices) const {
    return report_dictionary(worlds_geometry::analyze_indexed_triangles(
            to_points(p_vertices), to_indices(p_indices)));
}

Dictionary WorldsMeshTopology::analyze_position_surface(const PackedVector3Array &p_vertices,
                                                         const PackedInt32Array &p_indices) const {
    const worlds_geometry::PositionAudit r = worlds_geometry::analyze_position_topology(
            to_points(p_vertices), to_indices(p_indices));
    Dictionary result;
    result["indexed"] = report_dictionary(r.indexed);
    result["welded"] = report_dictionary(r.welded);
    result["unique_positions"] = static_cast<int64_t>(r.unique_positions);
    result["coincident_vertex_duplicates"] = static_cast<int64_t>(r.coincident_vertex_duplicates);
    result["indexed_open_edges_resolved"] = static_cast<int64_t>(r.indexed_open_edges_resolved);
    return result;
}

Dictionary WorldsMeshTopology::compare_border_samples(const PackedVector3Array &p_border_a,
                                                       const PackedVector3Array &p_border_b,
                                                       double p_tolerance) const {
    const worlds_geometry::BorderMatch r = worlds_geometry::compare_border_samples(
            to_points(p_border_a), to_points(p_border_b), p_tolerance);
    Dictionary result;
    result["valid_input"] = r.valid_input;
    result["geometry_match"] = r.geometry_match;
    result["opposite_direction"] = r.opposite_direction;
    result["same_direction"] = r.same_direction;
    result["t_junction_risk"] = r.t_junction_risk;
    result["samples_a"] = static_cast<int64_t>(r.samples_a);
    result["samples_b"] = static_cast<int64_t>(r.samples_b);
    result["max_opposing_gap"] = r.max_opposing_gap;
    return result;
}

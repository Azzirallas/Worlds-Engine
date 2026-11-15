// Bridges Godot mesh arrays to the standalone topology and border auditors.
#include "worlds_mesh_topology.h"
#include "mesh_border_audit.h"
#include "mesh_edge_audit.h"
#include "mesh_surface_source.h"

#include "core/object/class_db.h"
#include "scene/resources/3d/importer_mesh.h"
#include "scene/resources/mesh.h"

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
    ClassDB::bind_method(D_METHOD("analyze_mesh_surface", "mesh", "surface", "include_lods"),
            &WorldsMeshTopology::analyze_mesh_surface, DEFVAL(true));
    ClassDB::bind_method(D_METHOD("analyze_importer_mesh_surface", "mesh", "surface", "include_lods"),
            &WorldsMeshTopology::analyze_importer_mesh_surface, DEFVAL(true));
    ClassDB::bind_method(D_METHOD("build_meshlets_mesh_surface", "mesh", "surface", "lod_level", "max_vertices", "max_triangles"),
            &WorldsMeshTopology::build_meshlets_mesh_surface, DEFVAL(-1), DEFVAL(64), DEFVAL(124));
    ClassDB::bind_method(D_METHOD("build_meshlets_importer_surface", "mesh", "surface", "lod_level", "max_vertices", "max_triangles"),
            &WorldsMeshTopology::build_meshlets_importer_surface, DEFVAL(-1), DEFVAL(64), DEFVAL(124));
    ClassDB::bind_method(D_METHOD("prepare_mesh_surface_cache", "mesh", "surface", "asset_identity", "import_settings", "cache_path", "lod_level", "max_vertices", "max_triangles"),
            &WorldsMeshTopology::prepare_mesh_surface_cache, DEFVAL(-1), DEFVAL(64), DEFVAL(124));
    ClassDB::bind_method(D_METHOD("prepare_importer_surface_cache", "mesh", "surface", "asset_identity", "import_settings", "cache_path", "lod_level", "max_vertices", "max_triangles"),
            &WorldsMeshTopology::prepare_importer_surface_cache, DEFVAL(-1), DEFVAL(64), DEFVAL(124));
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

namespace {
// Keep malformed variant arrays explicit instead of silently accepting empties.
bool read_surface_arrays(const Array &p_arrays, std::vector<worlds_geometry::Point> &r_positions,
                         std::vector<std::int32_t> &r_indices) {
    if (p_arrays.size() != Mesh::ARRAY_MAX ||
            p_arrays[Mesh::ARRAY_VERTEX].get_type() != Variant::PACKED_VECTOR3_ARRAY) {
        return false;
    }
    const Variant &raw_indices = p_arrays[Mesh::ARRAY_INDEX];
    if (raw_indices.get_type() != Variant::NIL &&
            raw_indices.get_type() != Variant::PACKED_INT32_ARRAY) {
        return false;
    }
    r_positions = to_points(p_arrays[Mesh::ARRAY_VERTEX]);
    if (raw_indices.get_type() == Variant::PACKED_INT32_ARRAY) {
        r_indices = to_indices(raw_indices);
    }
    return true;
}

// Audit prepared indices against both index identity and exact spatial identity.
Dictionary audit_prepared(const std::vector<worlds_geometry::Point> &p_positions,
                          const std::vector<std::int32_t> &p_indices,
                          bool p_triangles, bool p_indexed) {
    const worlds_geometry::PreparedSurface prepared =
            worlds_geometry::prepare_triangle_surface(p_positions.size(), p_triangles, p_indexed, p_indices);
    Dictionary result;
    result["status"] = String(worlds_geometry::surface_status_string(prepared.status));
    result["generated_indices"] = prepared.generated_indices;
    result["vertex_count"] = static_cast<int64_t>(p_positions.size());
    result["index_count"] = static_cast<int64_t>(prepared.indices.size());
    if (prepared.status == worlds_geometry::SurfaceStatus::OK) {
        const worlds_geometry::PositionAudit audit =
                worlds_geometry::analyze_position_topology(p_positions, prepared.indices);
        Dictionary detail;
        detail["indexed"] = report_dictionary(audit.indexed);
        detail["welded"] = report_dictionary(audit.welded);
        detail["unique_positions"] = static_cast<int64_t>(audit.unique_positions);
        detail["coincident_vertex_duplicates"] = static_cast<int64_t>(audit.coincident_vertex_duplicates);
        detail["indexed_open_edges_resolved"] = static_cast<int64_t>(audit.indexed_open_edges_resolved);
        result["analysis"] = detail;
    }
    return result;
}

// Preserve LOD index streams untouched; only copy them for validation.
std::vector<std::int32_t> copy_lod_indices(const PackedInt32Array &p_indices) {
    return to_indices(p_indices);
}
} // namespace

Dictionary WorldsMeshTopology::analyze_mesh_surface(const Ref<Mesh> &p_mesh,
                                                     int p_surface, bool p_include_lods) const {
    Dictionary result;
    result["source"] = "Mesh";
    result["surface"] = p_surface;
    if (p_mesh.is_null()) {
        result["status"] = "NULL_MESH";
        return result;
    }
    if (p_surface < 0 || p_surface >= p_mesh->get_surface_count()) {
        result["status"] = "INVALID_SURFACE";
        return result;
    }
    const Array arrays = p_mesh->surface_get_arrays(p_surface);
    std::vector<worlds_geometry::Point> positions;
    std::vector<std::int32_t> indices;
    if (!read_surface_arrays(arrays, positions, indices)) {
        result["status"] = "INVALID_ARRAYS";
        return result;
    }
    const bool indexed = p_mesh->surface_get_format(p_surface).has_flag(Mesh::ARRAY_FORMAT_INDEX);
    const Mesh::PrimitiveType primitive = p_mesh->surface_get_primitive_type(p_surface);
    result["primitive"] = static_cast<int>(primitive);
    const Dictionary base = audit_prepared(positions, indices, primitive == Mesh::PRIMITIVE_TRIANGLES, indexed);
    result["status"] = base["status"];
    result["base"] = base;
    Array lod_reports;
    if (p_include_lods && primitive == Mesh::PRIMITIVE_TRIANGLES) {
        const Dictionary lods = p_mesh->surface_get_lods(p_surface);
        Array distances = lods.keys();
        distances.sort();
        for (int i = 0; i < distances.size(); ++i) {
            const Variant distance = distances[i];
            const Variant raw_indices = lods[distance];
            Dictionary entry;
            entry["distance"] = distance;
            if (raw_indices.get_type() == Variant::PACKED_INT32_ARRAY) {
                entry = audit_prepared(positions, copy_lod_indices(raw_indices), true, true);
                entry["distance"] = distance;
            } else {
                entry["status"] = "INVALID_LOD_ARRAY";
            }
            lod_reports.push_back(entry);
        }
    }
    result["lods"] = lod_reports;
    return result;
}

Dictionary WorldsMeshTopology::analyze_importer_mesh_surface(const Ref<ImporterMesh> &p_mesh,
                                                              int p_surface, bool p_include_lods) const {
    Dictionary result;
    result["source"] = "ImporterMesh";
    result["surface"] = p_surface;
    if (p_mesh.is_null()) {
        result["status"] = "NULL_MESH";
        return result;
    }
    if (p_surface < 0 || p_surface >= p_mesh->get_surface_count()) {
        result["status"] = "INVALID_SURFACE";
        return result;
    }
    const Array arrays = p_mesh->get_surface_arrays(p_surface);
    std::vector<worlds_geometry::Point> positions;
    std::vector<std::int32_t> indices;
    if (!read_surface_arrays(arrays, positions, indices)) {
        result["status"] = "INVALID_ARRAYS";
        return result;
    }
    // ImporterMesh stores flags separately; the index array itself determines indexing.
    const bool indexed = !indices.empty();
    const Mesh::PrimitiveType primitive = p_mesh->get_surface_primitive_type(p_surface);
    result["primitive"] = static_cast<int>(primitive);
    result["name"] = p_mesh->get_surface_name(p_surface);
    const Dictionary base = audit_prepared(positions, indices, primitive == Mesh::PRIMITIVE_TRIANGLES, indexed);
    result["status"] = base["status"];
    result["base"] = base;
    Array lod_reports;
    if (p_include_lods && primitive == Mesh::PRIMITIVE_TRIANGLES) {
        for (int level = 0; level < p_mesh->get_surface_lod_count(p_surface); ++level) {
            const Vector<int> source_indices = p_mesh->get_surface_lod_indices(p_surface, level);
            std::vector<std::int32_t> lod_indices;
            lod_indices.reserve(source_indices.size());
            for (int j = 0; j < source_indices.size(); ++j) {
                lod_indices.push_back(static_cast<std::int32_t>(source_indices[j]));
            }
            Dictionary entry = audit_prepared(positions, lod_indices, true, true);
            entry["distance"] = p_mesh->get_surface_lod_size(p_surface, level);
            entry["lod_level"] = level;
            lod_reports.push_back(entry);
        }
    }
    result["lods"] = lod_reports;
    return result;
}

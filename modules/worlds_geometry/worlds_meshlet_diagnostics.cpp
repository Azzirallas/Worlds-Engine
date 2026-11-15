// Read-only meshlet reports for imported/runtime Godot surfaces and existing LODs.
#include "worlds_mesh_topology.h"
#include "meshlet_builder.h"
#include "mesh_surface_source.h"

#include "scene/resources/3d/importer_mesh.h"
#include "scene/resources/mesh.h"

namespace {
// Decode supported array types without mutating the source resource.
bool extract_source(const Array &arrays, std::vector<worlds_geometry::Point> &positions,
                    std::vector<std::int32_t> &indices) {
    if (arrays.size() != Mesh::ARRAY_MAX ||
            arrays[Mesh::ARRAY_VERTEX].get_type() != Variant::PACKED_VECTOR3_ARRAY) {
        return false;
    }
    const Variant &raw = arrays[Mesh::ARRAY_INDEX];
    if (raw.get_type() != Variant::NIL && raw.get_type() != Variant::PACKED_INT32_ARRAY) {
        return false;
    }
    const PackedVector3Array verts = arrays[Mesh::ARRAY_VERTEX];
    positions.reserve(verts.size());
    for (int i = 0; i < verts.size(); ++i) {
        const Vector3 v = verts[i];
        positions.push_back({double(v.x), double(v.y), double(v.z)});
    }
    if (raw.get_type() == Variant::PACKED_INT32_ARRAY) {
        const PackedInt32Array list = raw;
        indices.reserve(list.size());
        for (int i = 0; i < list.size(); ++i) {
            indices.push_back(list[i]);
        }
    }
    return true;
}

// Only disclose outputs after the independent triangle coverage check passes.
Dictionary report_build(const std::vector<worlds_geometry::Point> &positions,
                        const std::vector<std::int32_t> &indices, bool indexed,
                        int max_vertices, int max_triangles) {
    Dictionary result;
    if (max_vertices < 3 || max_vertices > 256 || max_triangles < 1 || max_triangles > 512) {
        result["status"] = "INVALID_LIMITS";
        return result;
    }
    if (positions.size() > 750000 || indices.size() > 750000) {
        result["status"] = "DIAGNOSTIC_CAP";
        return result;
    }
    const worlds_geometry::PreparedSurface prepared = worlds_geometry::prepare_triangle_surface(
            positions.size(), true, indexed, indices);
    if (prepared.status != worlds_geometry::SurfaceStatus::OK) {
        result["status"] = worlds_geometry::surface_status_string(prepared.status);
        return result;
    }
    const worlds_geometry::MeshletBuild built = worlds_geometry::build_offline_meshlets(
            positions, prepared.indices, std::uint32_t(max_vertices), std::uint32_t(max_triangles));
    result["status"] = built.status;
    result["verified"] = built.valid && built.coverage.valid;
    result["meshlet_count"] = static_cast<int64_t>(built.meshlets.size());
    result["triangle_count"] = static_cast<int64_t>(built.coverage.output_triangles);
    result["source_triangle_count"] = static_cast<int64_t>(built.coverage.source_triangles);
    result["vertex_references"] = static_cast<int64_t>(built.coverage.vertex_references);
    result["generated_indices"] = prepared.generated_indices;
    if (!built.valid) {
        return result;
    }
    Array meshlets;
    for (const worlds_geometry::MeshletInfo &m : built.meshlets) {
        Dictionary entry;
        entry["vertex_offset"] = static_cast<int64_t>(m.range.vertex_offset);
        entry["triangle_offset"] = static_cast<int64_t>(m.range.triangle_offset);
        entry["vertex_count"] = static_cast<int64_t>(m.range.vertex_count);
        entry["triangle_count"] = static_cast<int64_t>(m.range.triangle_count);
        entry["center"] = Vector3(m.center[0], m.center[1], m.center[2]);
        entry["radius"] = m.radius;
        entry["cone_axis"] = Vector3(m.cone_axis[0], m.cone_axis[1], m.cone_axis[2]);
        entry["cone_cutoff"] = m.cone_cutoff;
        meshlets.push_back(entry);
    }
    result["meshlets"] = meshlets;
    return result;
}

// Convert importer LOD's Godot Vector<int> to the same audited index type.
std::vector<std::int32_t> importer_indices(const Vector<int> &indices) {
    std::vector<std::int32_t> result;
    result.reserve(indices.size());
    for (int i = 0; i < indices.size(); ++i) {
        result.push_back(indices[i]);
    }
    return result;
}
} // namespace

Dictionary WorldsMeshTopology::build_meshlets_mesh_surface(const Ref<Mesh> &p_mesh, int p_surface,
        int p_lod, int p_max_vertices, int p_max_triangles) const {
    Dictionary result;
    result["source"] = "Mesh";
    result["surface"] = p_surface;
    result["lod_level"] = p_lod;
    if (p_mesh.is_null()) {
        result["status"] = "NULL_MESH";
        return result;
    }
    if (p_surface < 0 || p_surface >= p_mesh->get_surface_count()) {
        result["status"] = "INVALID_SURFACE";
        return result;
    }
    if (p_mesh->surface_get_primitive_type(p_surface) != Mesh::PRIMITIVE_TRIANGLES) {
        result["status"] = "UNSUPPORTED_PRIMITIVE";
        return result;
    }
    std::vector<worlds_geometry::Point> positions;
    std::vector<std::int32_t> indices;
    if (!extract_source(p_mesh->surface_get_arrays(p_surface), positions, indices)) {
        result["status"] = "INVALID_ARRAYS";
        return result;
    }
    bool indexed = p_mesh->surface_get_format(p_surface).has_flag(Mesh::ARRAY_FORMAT_INDEX);
    if (p_lod != -1) {
        const Dictionary lods = p_mesh->surface_get_lods(p_surface);
        Array distances = lods.keys();
        distances.sort();
        if (p_lod < 0 || p_lod >= distances.size()) {
            result["status"] = "INVALID_LOD";
            return result;
        }
        const Variant distance = distances[p_lod];
        const Variant raw = lods[distance];
        if (raw.get_type() != Variant::PACKED_INT32_ARRAY) {
            result["status"] = "INVALID_LOD_ARRAY";
            return result;
        }
        const PackedInt32Array lod_indices = raw;
        indices.clear();
        indices.reserve(lod_indices.size());
        for (int i = 0; i < lod_indices.size(); ++i) {
            indices.push_back(lod_indices[i]);
        }
        indexed = true;
        result["distance"] = distance;
    }
    Dictionary report = report_build(positions, indices, indexed, p_max_vertices, p_max_triangles);
    report.merge(result, true);
    return report;
}

Dictionary WorldsMeshTopology::build_meshlets_importer_surface(const Ref<ImporterMesh> &p_mesh,
        int p_surface, int p_lod, int p_max_vertices, int p_max_triangles) const {
    Dictionary result;
    result["source"] = "ImporterMesh";
    result["surface"] = p_surface;
    result["lod_level"] = p_lod;
    if (p_mesh.is_null()) {
        result["status"] = "NULL_MESH";
        return result;
    }
    if (p_surface < 0 || p_surface >= p_mesh->get_surface_count()) {
        result["status"] = "INVALID_SURFACE";
        return result;
    }
    if (p_mesh->get_surface_primitive_type(p_surface) != Mesh::PRIMITIVE_TRIANGLES) {
        result["status"] = "UNSUPPORTED_PRIMITIVE";
        return result;
    }
    std::vector<worlds_geometry::Point> positions;
    std::vector<std::int32_t> indices;
    if (!extract_source(p_mesh->get_surface_arrays(p_surface), positions, indices)) {
        result["status"] = "INVALID_ARRAYS";
        return result;
    }
    bool indexed = !indices.empty();
    if (p_lod != -1) {
        if (p_lod < 0 || p_lod >= p_mesh->get_surface_lod_count(p_surface)) {
            result["status"] = "INVALID_LOD";
            return result;
        }
        indices = importer_indices(p_mesh->get_surface_lod_indices(p_surface, p_lod));
        indexed = true;
        result["distance"] = p_mesh->get_surface_lod_size(p_surface, p_lod);
    }
    result["name"] = p_mesh->get_surface_name(p_surface);
    Dictionary report = report_build(positions, indices, indexed, p_max_vertices, p_max_triangles);
    report.merge(result, true);
    return report;
}

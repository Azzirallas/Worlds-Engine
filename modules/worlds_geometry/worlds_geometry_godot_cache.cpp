// Opt-in, read-only Godot surface-to-WGC1 bridge; ordinary mesh rendering stays authoritative.
#include "worlds_mesh_topology.h"
#include "geometry_import_pipeline.h"
#include "geometry_cache_uri.h"

#include "core/config/project_settings.h"
#include "scene/resources/3d/importer_mesh.h"
#include "scene/resources/mesh.h"

#include <cstdint>
#include <filesystem>
#include <utility>
#include <vector>

namespace {
using worlds_geometry::GeometryPipelineInput;
using worlds_geometry::GeometryPipelineResult;
using worlds_geometry::GeometryPipelineStatus;
using worlds_geometry::Point;

// Preserve source data and reject unsupported Variant layouts before copying.
bool read_surface(const Array &arrays, GeometryPipelineInput &input) {
    if (arrays.size() != Mesh::ARRAY_MAX ||
            arrays[Mesh::ARRAY_VERTEX].get_type() != Variant::PACKED_VECTOR3_ARRAY) {
        return false;
    }
    const Variant &raw = arrays[Mesh::ARRAY_INDEX];
    if (raw.get_type() != Variant::NIL && raw.get_type() != Variant::PACKED_INT32_ARRAY) {
        return false;
    }
    const PackedVector3Array vertices = arrays[Mesh::ARRAY_VERTEX];
    if (vertices.size() > 750000) {
        return false;
    }
    input.positions.reserve(vertices.size());
    for (int i = 0; i < vertices.size(); ++i) {
        const Vector3 v = vertices[i];
        input.positions.push_back({double(v.x), double(v.y), double(v.z)});
    }
    if (raw.get_type() == Variant::PACKED_INT32_ARRAY) {
        const PackedInt32Array indices = raw;
        if (indices.size() > 750000) {
            return false;
        }
        input.indices.reserve(indices.size());
        for (int i = 0; i < indices.size(); ++i) {
            input.indices.push_back(indices[i]);
        }
    }
    return true;
}

// Restrict the experimental output to a dedicated user-data cache directory.
bool resolve_cache_path(const String &uri, std::filesystem::path &path) {
    const CharString encoded_uri = uri.utf8();
    if (!worlds_geometry::valid_geometry_cache_uri(encoded_uri.get_data())) {
        return false;
    }
    const String native = ProjectSettings::get_singleton()->globalize_path(uri);
    const CharString encoded = native.utf8();
    path = std::filesystem::u8path(encoded.get_data());
    return !path.empty();
}

// Godot PackedByteArray values are copied into the cache's immutable input vectors.
std::vector<std::uint8_t> bytes(const PackedByteArray &data) {
    std::vector<std::uint8_t> result;
    result.reserve(data.size());
    for (int i = 0; i < data.size(); ++i) {
        result.push_back(data[i]);
    }
    return result;
}

// A ready offline cache is never treated as permission to use experimental GPU draws.
Dictionary prepare(GeometryPipelineInput &&input, const String &cache_uri,
                   const PackedByteArray &source_identity,
                   const PackedByteArray &settings_identity) {
    Dictionary report;
    report["requires_standard_renderer"] = true;
    report["verified"] = false;
    report["meshlet_count"] = 0;
    report["status"] = "INVALID_CACHE_PATH";
    std::filesystem::path cache_path;
    if (!resolve_cache_path(cache_uri, cache_path)) {
        return report;
    }
    input.cache_path = std::move(cache_path);
    input.asset_identity = bytes(source_identity);
    input.import_settings = bytes(settings_identity);
    const GeometryPipelineResult result = worlds_geometry::prepare_offline_geometry(input);
    report["status"] = worlds_geometry::geometry_pipeline_status_string(result.status);
    report["surface_status"] = worlds_geometry::surface_status_string(result.surface_status);
    report["generated_indices"] = result.generated_indices;
    report["boundaries_analyzed"] = result.boundaries_analyzed;
    report["boundary_status"] = result.boundaries_analyzed ?
            worlds_geometry::boundary_status_string(result.boundaries.status) : "NOT_REQUESTED";
    report["boundary_edges"] = static_cast<int64_t>(result.boundaries.boundary_edges);
    report["boundary_chain_count"] = static_cast<int64_t>(result.boundaries.chains.size());
    const bool ready = result.status == GeometryPipelineStatus::READY_CACHED ||
            result.status == GeometryPipelineStatus::READY_STORED ||
            result.status == GeometryPipelineStatus::READY_MEMORY_ONLY;
    report["verified"] = ready && result.build.valid && result.build.coverage.valid;
    report["meshlet_count"] = static_cast<int64_t>(result.build.meshlets.size());
    report["source_triangle_count"] = static_cast<int64_t>(result.build.coverage.source_triangles);
    report["output_triangle_count"] = static_cast<int64_t>(result.build.coverage.output_triangles);
    return report;
}
} // namespace

// Read runtime Mesh/ArrayMesh surface or sorted stored LOD without modifying it.
Dictionary WorldsMeshTopology::prepare_mesh_surface_cache(const Ref<Mesh> &p_mesh, int p_surface,
        const PackedByteArray &p_asset_identity, const PackedByteArray &p_import_settings,
        const String &p_cache_path, int p_lod, int p_max_vertices, int p_max_triangles) const {
    Dictionary report;
    report["source"] = "Mesh";
    report["surface"] = p_surface;
    report["lod_level"] = p_lod;
    report["requires_standard_renderer"] = true;
    if (p_mesh.is_null()) { report["status"] = "NULL_MESH"; return report; }
    if (p_surface < 0 || p_surface >= p_mesh->get_surface_count()) {
        report["status"] = "INVALID_SURFACE"; return report;
    }
    if (p_mesh->surface_get_primitive_type(p_surface) != Mesh::PRIMITIVE_TRIANGLES) {
        report["status"] = "UNSUPPORTED_PRIMITIVE"; return report;
    }
    GeometryPipelineInput input;
    if (!read_surface(p_mesh->surface_get_arrays(p_surface), input)) {
        report["status"] = "INVALID_ARRAYS"; return report;
    }
    input.is_indexed = p_mesh->surface_get_format(p_surface).has_flag(Mesh::ARRAY_FORMAT_INDEX);
    if (p_lod < -1) { report["status"] = "INVALID_LOD"; return report; }
    if (p_lod >= 0) {
        const Dictionary lods = p_mesh->surface_get_lods(p_surface);
        Array distances = lods.keys();
        distances.sort();
        if (p_lod >= distances.size()) { report["status"] = "INVALID_LOD"; return report; }
        const Variant distance = distances[p_lod];
        const Variant raw = lods[distance];
        if (raw.get_type() != Variant::PACKED_INT32_ARRAY) {
            report["status"] = "INVALID_LOD_ARRAY"; return report;
        }
        const PackedInt32Array indices = raw;
        if (indices.size() > 750000) { report["status"] = "DIAGNOSTIC_CAP"; return report; }
        input.indices.clear();
        input.indices.reserve(indices.size());
        for (int i = 0; i < indices.size(); ++i) { input.indices.push_back(indices[i]); }
        input.is_indexed = true;
        report["distance"] = distance;
    }
    input.surface = static_cast<std::uint32_t>(p_surface);
    input.lod = p_lod;
    input.max_vertices = static_cast<std::uint32_t>(p_max_vertices);
    input.max_triangles = static_cast<std::uint32_t>(p_max_triangles);
    Dictionary output = prepare(std::move(input), p_cache_path, p_asset_identity, p_import_settings);
    output.merge(report, true);
    return output;
}

// Read original importer-side vertex/index streams and native importer LODs.
Dictionary WorldsMeshTopology::prepare_importer_surface_cache(const Ref<ImporterMesh> &p_mesh, int p_surface,
        const PackedByteArray &p_asset_identity, const PackedByteArray &p_import_settings,
        const String &p_cache_path, int p_lod, int p_max_vertices, int p_max_triangles) const {
    Dictionary report;
    report["source"] = "ImporterMesh";
    report["surface"] = p_surface;
    report["lod_level"] = p_lod;
    report["requires_standard_renderer"] = true;
    if (p_mesh.is_null()) { report["status"] = "NULL_MESH"; return report; }
    if (p_surface < 0 || p_surface >= p_mesh->get_surface_count()) {
        report["status"] = "INVALID_SURFACE"; return report;
    }
    if (p_mesh->get_surface_primitive_type(p_surface) != Mesh::PRIMITIVE_TRIANGLES) {
        report["status"] = "UNSUPPORTED_PRIMITIVE"; return report;
    }
    GeometryPipelineInput input;
    if (!read_surface(p_mesh->get_surface_arrays(p_surface), input)) {
        report["status"] = "INVALID_ARRAYS"; return report;
    }
    input.is_indexed = !input.indices.empty();
    if (p_lod < -1 || (p_lod >= 0 && p_lod >= p_mesh->get_surface_lod_count(p_surface))) {
        report["status"] = "INVALID_LOD"; return report;
    }
    if (p_lod >= 0) {
        const Vector<int> indices = p_mesh->get_surface_lod_indices(p_surface, p_lod);
        if (indices.size() > 750000) { report["status"] = "DIAGNOSTIC_CAP"; return report; }
        input.indices.clear();
        input.indices.reserve(indices.size());
        for (int i = 0; i < indices.size(); ++i) { input.indices.push_back(indices[i]); }
        input.is_indexed = true;
        report["distance"] = p_mesh->get_surface_lod_size(p_surface, p_lod);
    }
    input.surface = static_cast<std::uint32_t>(p_surface);
    input.lod = p_lod;
    input.max_vertices = static_cast<std::uint32_t>(p_max_vertices);
    input.max_triangles = static_cast<std::uint32_t>(p_max_triangles);
    report["name"] = p_mesh->get_surface_name(p_surface);
    Dictionary output = prepare(std::move(input), p_cache_path, p_asset_identity, p_import_settings);
    output.merge(report, true);
    return output;
}

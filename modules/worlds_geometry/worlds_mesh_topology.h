// Opt-in, read-only Godot API for indexed and position-aware mesh checks.
#pragma once

#include "core/object/ref_counted.h"
#include "core/variant/variant.h"

class Mesh;
class ImporterMesh;

class WorldsMeshTopology : public RefCounted {
    GDCLASS(WorldsMeshTopology, RefCounted);

protected:
    static void _bind_methods();

public:
    // Index connectivity; no geometric welding or mesh mutation.
    Dictionary analyze_indexed_surface(const PackedVector3Array &p_vertices,
                                       const PackedInt32Array &p_indices) const;
    // Compare index connectivity with exact-position-welded connectivity.
    Dictionary analyze_position_surface(const PackedVector3Array &p_vertices,
                                        const PackedInt32Array &p_indices) const;
    // Inspect runtime Mesh/ArrayMesh triangle surfaces and their stored LODs.
    Dictionary analyze_mesh_surface(const Ref<Mesh> &p_mesh, int p_surface, bool p_include_lods = true) const;
    // Inspect importer-stage surfaces without calling get_mesh() or changing the resource.
    Dictionary analyze_importer_mesh_surface(const Ref<ImporterMesh> &p_mesh, int p_surface, bool p_include_lods = true) const;
    // Offline meshlets from one runtime surface or stored LOD; never alters Mesh.
    Dictionary build_meshlets_mesh_surface(const Ref<Mesh> &p_mesh, int p_surface,
                                           int p_lod = -1, int p_max_vertices = 64,
                                           int p_max_triangles = 124) const;
    // Offline meshlets from one import-stage surface or stored LOD, read only.
    Dictionary build_meshlets_importer_surface(const Ref<ImporterMesh> &p_mesh, int p_surface,
                                               int p_lod = -1, int p_max_vertices = 64,
                                               int p_max_triangles = 124) const;
    // Conservative oriented shared-edge samples with an explicit distance tolerance.
    Dictionary compare_border_samples(const PackedVector3Array &p_border_a,
                                      const PackedVector3Array &p_border_b,
                                      double p_tolerance = 0.0) const;
};

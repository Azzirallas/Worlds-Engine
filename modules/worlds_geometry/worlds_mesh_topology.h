// Optional, read-only Godot API for native indexed triangle topology checks.
#pragma once

#include "core/object/ref_counted.h"
#include "core/variant/variant.h"

class WorldsMeshTopology : public RefCounted {
    GDCLASS(WorldsMeshTopology, RefCounted);

protected:
    static void _bind_methods();

public:
    // Returns index-topology diagnostics; does not modify the supplied mesh.
    Dictionary analyze_indexed_surface(const PackedVector3Array &p_vertices,
                                       const PackedInt32Array &p_indices) const;
};

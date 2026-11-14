// Opt-in, read-only Godot API for indexed and position-aware mesh checks.
#pragma once

#include "core/object/ref_counted.h"
#include "core/variant/variant.h"

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
    // Conservative oriented shared-edge samples with an explicit distance tolerance.
    Dictionary compare_border_samples(const PackedVector3Array &p_border_a,
                                      const PackedVector3Array &p_border_b,
                                      double p_tolerance = 0.0) const;
};

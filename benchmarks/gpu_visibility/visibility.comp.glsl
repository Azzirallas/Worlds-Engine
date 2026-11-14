#[compute]
#version 450

// Standalone experiment: conservatively select candidate spheres by frustum/layers.
// No main renderer modifications, indirect draws, HZB, or temporal reuse.
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer SphereBuffer {
    vec4 spheres[]; // xyz = center, w = radius; one record per slot
};
layout(set = 0, binding = 1, std430) readonly buffer MetadataBuffer {
    uvec2 metadata[]; // x = layer mask (zero when disabled), y = slot generation
};
layout(set = 0, binding = 2, std430) readonly buffer CandidateBuffer {
    uint candidate_slots[];
};
layout(set = 0, binding = 3, std430) readonly buffer FrustumBuffer {
    vec4 planes[]; // xyz = inward normal, w = half-space offset
};
layout(set = 0, binding = 4, std430) writeonly buffer OutputBuffer {
    uvec2 visible_handles[]; // slot, generation; atomic append order is arbitrary
};
layout(set = 0, binding = 5, std430) buffer CounterBuffer {
    uint visible_count;
    uint overflow_flags; // bit 0: output overflow; bit 1: invalid candidate slot
};

layout(push_constant, std430) uniform Settings {
    uint candidate_count;
    uint plane_count;
    uint view_layer_mask;
    uint output_capacity;
    uint slot_count;
    // Pad to a 32-byte push-constant block for stricter driver/engine ABI rules.
    uint reserved0;
    uint reserved1;
    uint reserved2;
} settings;

void main() {
    uint candidate_index = gl_GlobalInvocationID.x;
    if (candidate_index >= settings.candidate_count) {
        return;
    }

    uint slot = candidate_slots[candidate_index];
    if (slot >= settings.slot_count) {
        atomicOr(overflow_flags, 2u);
        return;
    }

    uvec2 entry = metadata[slot];
    if ((entry.x & settings.view_layer_mask) == 0u) {
        return;
    }

    vec4 sphere = spheres[slot];
    if (sphere.w < 0.0 || any(isnan(sphere)) || any(isinf(sphere))) {
        // Malformed source data is an explicit caller/asset validation failure.
        atomicOr(overflow_flags, 2u);
        return;
    }

    for (uint i = 0u; i < settings.plane_count; ++i) {
        vec3 n = planes[i].xyz;
        float nlen = length(n);
        float signed_distance = dot(n, sphere.xyz) + planes[i].w;
        // Matches the CPU fixture. Bias conservatively covers fp32 boundary error.
        if (signed_distance < -(sphere.w + 0.0001) * nlen) {
            return;
        }
    }

    uint output_index = atomicAdd(visible_count, 1u);
    if (output_index < settings.output_capacity) {
        visible_handles[output_index] = uvec2(slot, entry.y);
    } else {
        // Never silently accept a truncated visible draw list.
        atomicOr(overflow_flags, 1u);
    }
}

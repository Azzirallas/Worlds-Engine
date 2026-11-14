#[compute]
#version 450

// GPU-only safety gate: convert culling results to a non-indexed indirect draw.
// On ANY visibility fault, emit a zero-instance command (never draw partial data).
layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Counters {
    uint visible_count;
    uint overflow_flags; // Nonzero: overflow, invalid candidate or stale generation.
};

layout(set = 0, binding = 1, std430) writeonly buffer IndirectCommand {
    uint vertex_count;
    uint instance_count;
    uint first_vertex;
    uint first_instance;
};

layout(push_constant, std430) uniform DrawLimits {
    uint output_capacity;
    uint mesh_vertex_count;
    uint max_draw_instances;
    uint reserved;
} limits;

void main() {
    // Also reject a count that exceeds capacity, even if a producer forgot to set flags.
    bool safe = (overflow_flags == 0u)
        && (visible_count <= limits.output_capacity)
        && (visible_count <= limits.max_draw_instances)
        && (limits.mesh_vertex_count > 0u);

    vertex_count = limits.mesh_vertex_count;
    instance_count = safe ? visible_count : 0u;
    first_vertex = 0u;
    first_instance = 0u;
}

#[vertex]
#version 450

// Tiny offscreen probe. Each visible instance invokes one procedural triangle.
// Do not confuse this with a complete Godot mesh/material implementation.
layout(set = 0, binding = 0, std430) readonly buffer VisibleHandles {
    uvec2 visible_handles[];
};
layout(set = 0, binding = 1, std430) readonly buffer Spheres {
    vec4 spheres[];
};

layout(location = 0) out vec4 vertex_color;

void main() {
    uint slot = visible_handles[gl_InstanceIndex].x;
    vec4 sphere = spheres[slot];
    vec2 vertices[3] = vec2[3](
        vec2(-0.8, -0.8), vec2(0.8, -0.8), vec2(0.0, 0.8));
    gl_Position = vec4(vertices[gl_VertexIndex], 0.0, 1.0);
    vertex_color = sphere.w >= 0.0 ? vec4(0.0, 1.0, 0.0, 1.0) : vec4(1.0, 0.0, 0.0, 1.0);
}

#[fragment]
#version 450

layout(location = 0) in vec4 vertex_color;
layout(location = 0) out vec4 output_color;

void main() {
    output_color = vertex_color;
}

// API-boundary tests with a MOCK builder; real vendor linking remains pending.
#include "meshlet_builder.h"
#include <cassert>
#include <cmath>
#include <limits>
using worlds_geometry::Point;
using worlds_geometry::build_offline_meshlets;
extern int meshopt_test_mode;
int main() {
    const std::vector<Point> square{{0,0,0},{1,0,0},{1,1,0},{0,1,0}};
    {
        auto r = build_offline_meshlets(square, {0,1,2,0,2,3}, 64,124);
        assert(r.valid && r.meshlets.size()==2 && r.coverage.valid);
        assert(r.coverage.output_triangles==2 && r.coverage.source_triangles==2);
        assert(r.meshlets[0].radius >= 0);
    }
    {
        auto r = build_offline_meshlets({{0,0,0},{1,0,0},{0,1,0}}, {}, 64, 124);
        assert(r.valid && r.coverage.output_triangles==1);
    }
    {
        meshopt_test_mode = 1;
        assert(!build_offline_meshlets(square,{0,1,2},64,124).valid);
        meshopt_test_mode = 2;
        assert(!build_offline_meshlets(square,{0,1,2},64,124).valid);
        meshopt_test_mode = 0;
    }
    assert(!build_offline_meshlets(square,{0,1,2},2,64).valid);
    assert(!build_offline_meshlets(square,{0,1,2},257,64).valid);
    assert(!build_offline_meshlets(square,{0,1,2},64,0).valid);
    assert(!build_offline_meshlets(square,{0,1,2},64,513).valid);
    assert(!build_offline_meshlets(square,{0,1},64,124).valid);
    assert(!build_offline_meshlets(square,{0,1,4},64,124).valid);
    assert(!build_offline_meshlets(square,{0,0,2},64,124).valid);
    assert(!build_offline_meshlets({{0,0,0},{1,0,0},{2,0,0}}, {0,1,2},64,124).valid); // Collinear.
    {
        auto pts = square; pts[0].x = std::numeric_limits<double>::infinity();
        assert(!build_offline_meshlets(pts,{0,1,2}).valid);
    }
    {
        auto pts = square; pts[0].x = std::numeric_limits<double>::max();
        assert(!build_offline_meshlets(pts,{0,1,2}).valid);
    }
    {
        auto pts = square; pts[2] = {1e-80, 1e-80, 0};
        assert(!build_offline_meshlets(pts,{0,1,2}).valid);
    }
    return 0;
}

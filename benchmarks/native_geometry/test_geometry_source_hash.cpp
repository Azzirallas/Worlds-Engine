// Known SHA-256 vectors plus stable canonical geometry/settings hashing.
#include "worlds_geometry/geometry_source_hash.h"
#include <cassert>
#include <cmath>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <vector>
using namespace worlds_geometry;
std::string hex(const std::array<std::uint8_t,32>& digest) {
    std::ostringstream out;
    for (auto b:digest) {out<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);}
    return out.str();
}
GeometryCacheSource base() {
    GeometryCacheSource s;
    s.positions={{0,0,0},{1,0,0},{0,1,0}};
    s.source_triangles={0,1,2};
    s.generator_version=1;
    return s;
}
int main() {
    const std::string empty;
    assert(hex(geometry_sha256(reinterpret_cast<const std::uint8_t*>(empty.data()),0)) ==
           "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    const std::string abc="abc";
    assert(hex(geometry_sha256(reinterpret_cast<const std::uint8_t*>(abc.data()),3)) ==
           "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    const std::string million(1000000,'a');
    assert(hex(geometry_sha256(reinterpret_cast<const std::uint8_t*>(million.data()),million.size())) ==
           "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
    auto s=base();
    const std::vector<std::uint8_t> asset={1,2,3}, settings={4,5,6};
    assert(stamp_geometry_cache_source(s,asset,settings));
    assert(verify_geometry_cache_source(s,asset,settings));
    auto old=s;
    old.positions[0].x=0.1;
    assert(!verify_geometry_cache_source(old,asset,settings));
    old=s;old.source_triangles={2,1,0};
    assert(!verify_geometry_cache_source(old,asset,settings));
    old=s;old.surface=1;
    assert(!verify_geometry_cache_source(old,asset,settings));
    old=s;old.lod=1;
    assert(!verify_geometry_cache_source(old,asset,settings));
    old=s;old.generator_version=2;
    assert(!verify_geometry_cache_source(old,asset,settings));
    old=s;old.max_vertices=32;
    assert(!verify_geometry_cache_source(old,asset,settings));
    assert(!verify_geometry_cache_source(s,{1,2,4},settings));
    assert(!verify_geometry_cache_source(s,asset,{4,5,7}));
    old=s;old.positions[0].x=-0.0;
    assert(verify_geometry_cache_source(old,asset,settings));
    old=s;old.positions[1].x=std::numeric_limits<double>::infinity();
    assert(!stamp_geometry_cache_source(old,asset,settings));
    old=s;old.source_triangles[0]=4;
    assert(!stamp_geometry_cache_source(old,asset,settings));
    assert(hex(s.source_sha256) != hex(s.settings_sha256));
}

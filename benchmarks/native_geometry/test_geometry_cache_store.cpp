// Disk persistence, cache reuse, mutation invalidation and corruption recovery.
#include "worlds_geometry/geometry_cache_store.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
using namespace worlds_geometry;
namespace fs=std::filesystem;
namespace worlds_geometry {
// Test double for the independently tested WGC1 codec. This fixture tests the IO lifecycle.
GeometryCacheBytes encode_geometry_cache(const GeometryCacheSource &s,const MeshletBuild &b) {
    GeometryCacheBytes r;
    if (!b.valid) { r.status=GeometryCacheStatus::INVALID_MESHLETS;return r; }
    r.bytes.insert(r.bytes.end(),s.source_sha256.begin(),s.source_sha256.end());
    r.bytes.insert(r.bytes.end(),s.settings_sha256.begin(),s.settings_sha256.end());
    r.bytes.push_back(42);
    r.status=GeometryCacheStatus::OK;return r;
}
GeometryCacheDecoded decode_geometry_cache(const GeometryCacheSource &s,const std::vector<std::uint8_t>& v) {
    GeometryCacheDecoded r;
    if (v.size()!=65||v[64]!=42 || !std::equal(s.source_sha256.begin(),s.source_sha256.end(),v.begin()) ||
         !std::equal(s.settings_sha256.begin(),s.settings_sha256.end(),v.begin()+32)) {return r;}
    r.status=GeometryCacheStatus::OK;r.build.valid=true;return r;
}
} // namespace worlds_geometry
int main() {
    const fs::path dir=fs::temp_directory_path()/("worlds-cache-test-"+std::to_string(12345689));
    fs::remove_all(dir);
    fs::create_directories(dir);
    const auto path=dir/"cache"/"artifact.wgc";
    GeometryCacheSource s;
    s.positions={{0,0,0},{1,0,0},{0,1,0}};
    s.source_triangles={0,1,2};s.generator_version=1;
    int builds=0;
    const auto builder=[&](){++builds;MeshletBuild b;b.valid=true;return b;};
    auto r=load_or_build_geometry_cache(path,s,{1,2,3},{4,5,6},builder);
    assert(r.status==GeometryStoreStatus::BUILT_STORED&&builds==1);
    r=load_or_build_geometry_cache(path,s,{1,2,3},{4,5,6},builder);
    assert(r.status==GeometryStoreStatus::HIT&&builds==1);
    r=load_or_build_geometry_cache(path,s,{1,2,4},{4,5,6},builder);
    assert(r.status==GeometryStoreStatus::BUILT_STORED&&builds==2);
    r=load_or_build_geometry_cache(path,s,{1,2,4},{4,5,6},builder);
    assert(r.status==GeometryStoreStatus::HIT&&builds==2);
    r=load_or_build_geometry_cache(path,s,{1,2,4},{4,5,7},builder);
    assert(r.status==GeometryStoreStatus::BUILT_STORED&&builds==3);
    auto modified=s; modified.positions[1].x=1.125;
    r=load_or_build_geometry_cache(path,modified,{1,2,4},{4,5,7},builder);
    assert(r.status==GeometryStoreStatus::BUILT_STORED&&builds==4);
    r=load_or_build_geometry_cache(path,modified,{1,2,4},{4,5,7},{});
    assert(r.status==GeometryStoreStatus::HIT&&builds==4);
    {std::ofstream out(path,std::ios::binary|std::ios::trunc);out<<"bad";}
    r=load_or_build_geometry_cache(path,modified,{1,2,4},{4,5,7},builder);
    assert(r.status==GeometryStoreStatus::BUILT_STORED&&builds==5);
    fs::remove(path);
    {std::ofstream out(path,std::ios::binary|std::ios::trunc);out.seekp(24*1024*1024);out.put('X');}
    r=load_or_build_geometry_cache(path,modified,{1,2,4},{4,5,7},builder);
    assert(r.status==GeometryStoreStatus::BUILT_STORED&&builds==6);
    const auto badbuilder=[&](){++builds;return MeshletBuild{};};
    r=load_or_build_geometry_cache(dir/"bad.wgc",s,{1,2,4},{4,5,6},badbuilder);
    assert(r.status==GeometryStoreStatus::BUILD_FAILED&&!fs::exists(dir/"bad.wgc"));
    fs::create_directories(dir/"directory.wgc");
    r=load_or_build_geometry_cache(dir/"directory.wgc",s,{1,2,4},{4,5,6},builder);
    assert(r.status==GeometryStoreStatus::BUILT_UNSTORED&&r.build.valid);
    fs::remove_all(dir);
}

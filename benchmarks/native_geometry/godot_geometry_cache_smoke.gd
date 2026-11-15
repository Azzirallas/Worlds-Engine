# Headless native acceptance gate for opt-in Godot Mesh/ImporterMesh WGC1 preparation.
# Requires a Godot editor build with module_worlds_geometry_enabled=yes; not GPU-dependent.
extends SceneTree

func _initialize() -> void:
    var checker := WorldsMeshTopology.new()
    var arrays: Array = []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([
        Vector3(0, 0, 0), Vector3(2, 0, 0),
        Vector3(2, 2, 0), Vector3(0, 2, 0),
    ])
    arrays[Mesh.ARRAY_INDEX] = PackedInt32Array([0, 1, 2, 0, 2, 3])
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var identity := "godot-smoke-quad".to_utf8_buffer()
    var settings := "import-v1".to_utf8_buffer()
    var cache := "user://worlds_geometry_cache/runtime_%d.wgc1" % Time.get_ticks_usec()

    var report: Dictionary = checker.prepare_mesh_surface_cache(mesh, 0, identity, settings, cache)
    if report.get("status") != "READY_STORED" or not report.get("verified", false) or not report.get("requires_standard_renderer", false):
        push_error("Runtime cache first build failed: " + str(report))
        quit(1)
        return
    if report.get("source_triangle_count") != 2 or report.get("meshlet_count", 0) < 1:
        push_error("Runtime meshlet coverage invalid: " + str(report))
        quit(2)
        return

    report = checker.prepare_mesh_surface_cache(mesh, 0, identity, settings, cache)
    if report.get("status") != "READY_CACHED" or not report.get("verified", false):
        push_error("Expected verified runtime cache hit: " + str(report))
        quit(3)
        return
    report = checker.prepare_mesh_surface_cache(mesh, 0, identity, "import-v2".to_utf8_buffer(), cache)
    if report.get("status") != "READY_STORED":
        push_error("Changed settings were not invalidated: " + str(report))
        quit(4)
        return

    var importer := ImporterMesh.new()
    var lods: Dictionary = {8.0: PackedInt32Array([0, 1, 2])}
    var shapes: Array[Array] = []
    importer.add_surface(Mesh.PRIMITIVE_TRIANGLES, arrays, shapes, lods)
    var lod_cache := "user://worlds_geometry_cache/importer_%d.wgc1" % Time.get_ticks_usec()
    report = checker.prepare_importer_surface_cache(importer, 0, identity, settings, lod_cache, 0)
    if report.get("status") != "READY_STORED" or report.get("source_triangle_count") != 1 or report.get("distance") != 8.0:
        push_error("Importer LOD cache failed: " + str(report))
        quit(5)
        return
    report = checker.prepare_importer_surface_cache(importer, 0, identity, settings, lod_cache, 0)
    if report.get("status") != "READY_CACHED":
        push_error("Importer LOD cache was not reused: " + str(report))
        quit(6)
        return

    report = checker.prepare_mesh_surface_cache(mesh, 0, identity, settings, "res://wrong.wgc1")
    if report.get("status") != "INVALID_CACHE_PATH":
        push_error("Unsafe cache path not rejected: " + str(report))
        quit(7)
        return
    report = checker.prepare_mesh_surface_cache(mesh, 0, PackedByteArray(), settings, cache)
    if report.get("status") != "INVALID_PROVENANCE":
        push_error("Missing provenance not rejected: " + str(report))
        quit(8)
        return
    report = checker.prepare_importer_surface_cache(importer, 0, identity, settings, lod_cache, 999)
    if report.get("status") != "INVALID_LOD":
        push_error("Invalid importer LOD not rejected: " + str(report))
        quit(9)
        return

    print("WorldsMeshTopology offline WGC1 cache smoke: PASS")
    quit(0)

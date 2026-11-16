# Headless Godot gate: empty importer index data means nonindexed triangles.
# Requires the optional worlds_geometry module; Godot engine execution remains pending.
extends SceneTree

func _initialize() -> void:
    var checker := WorldsMeshTopology.new()
    var vertices := PackedVector3Array([
        Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0),
    ])
    var arrays: Array = []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_INDEX] = PackedInt32Array()
    var importer := ImporterMesh.new()
    var shapes: Array[Array] = []
    var lods: Dictionary = {}
    importer.add_surface(Mesh.PRIMITIVE_TRIANGLES, arrays, shapes, lods)

    var audit: Dictionary = checker.analyze_importer_mesh_surface(importer, 0, false)
    if audit.get("status") != "OK" or not audit["base"].get("generated_indices", false):
        push_error("Empty importer indices must be nonindexed: " + str(audit))
        quit(1)
        return

    var meshlets: Dictionary = checker.build_meshlets_importer_surface(importer, 0)
    if meshlets.get("status") != "OK" or not meshlets.get("verified", false):
        push_error("Meshlet adapter rejected normal empty-index importer mesh: " + str(meshlets))
        quit(2)
        return

    var path := "user://worlds_geometry_cache/empty_index_godot_%d.wgc1" % Time.get_ticks_usec()
    var cache: Dictionary = checker.prepare_importer_surface_cache(
        importer, 0, "asset".to_utf8_buffer(), "settings".to_utf8_buffer(), path)
    if cache.get("status") != "READY_STORED" or not cache.get("verified", false):
        push_error("WGC1 bridge rejected nonindexed importer geometry: " + str(cache))
        quit(3)
        return

    cache = checker.prepare_importer_surface_cache(
        importer, 0, "asset".to_utf8_buffer(), "settings".to_utf8_buffer(), path)
    if cache.get("status") != "READY_CACHED" or not cache.get("verified", false):
        push_error("Nonindexed importer cache hit failed: " + str(cache))
        quit(4)
        return

    print("Worlds importer empty-index nonindexed smoke: PASS")
    quit(0)

# Headless acceptance test; requires Godot built with worlds_geometry enabled.
extends SceneTree

func _initialize() -> void:
    var checker := WorldsMeshTopology.new()
    var arrays: Array = []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([
        Vector3(0, 0, 0), Vector3(1, 0, 0),
        Vector3(1, 1, 0), Vector3(0, 1, 0),
    ])
    arrays[Mesh.ARRAY_INDEX] = PackedInt32Array([0, 1, 2, 0, 2, 3])

    var runtime := ArrayMesh.new()
    runtime.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var report: Dictionary = checker.analyze_mesh_surface(runtime, 0)
    if report.get("status") != "OK" or report["base"]["analysis"]["indexed"]["triangle_count"] != 2:
        push_error("Runtime Mesh triangle audit failed: " + str(report))
        quit(1)
        return

    var importer := ImporterMesh.new()
    var lods: Dictionary = {8.0: PackedInt32Array([0, 1, 2])}
    var shapes: Array[Array] = []
    importer.add_surface(Mesh.PRIMITIVE_TRIANGLES, arrays, shapes, lods)
    report = checker.analyze_importer_mesh_surface(importer, 0)
    if report.get("status") != "OK" or report["lods"].size() != 1 or report["lods"][0]["status"] != "OK":
        push_error("ImporterMesh LOD audit failed: " + str(report))
        quit(2)
        return

    var unindexed: Array = []
    unindexed.resize(Mesh.ARRAY_MAX)
    unindexed[Mesh.ARRAY_VERTEX] = PackedVector3Array([
        Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0),
    ])
    var mesh_unindexed := ArrayMesh.new()
    mesh_unindexed.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, unindexed)
    report = checker.analyze_mesh_surface(mesh_unindexed, 0)
    if report.get("status") != "OK" or not report["base"]["generated_indices"]:
        push_error("Unindexed triangle audit failed: " + str(report))
        quit(3)
        return

    report = checker.analyze_mesh_surface(runtime, 99)
    if report.get("status") != "INVALID_SURFACE":
        push_error("Invalid surface was not rejected")
        quit(4)
        return

    print("WorldsMeshTopology import/runtime mesh smoke: PASS")
    quit(0)

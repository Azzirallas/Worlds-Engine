# Headless smoke gate for real meshoptimizer-backed offline clusters (not CPU mock).
# Run only after compiling Godot with module_worlds_geometry_enabled=yes.
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

    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var report: Dictionary = checker.build_meshlets_mesh_surface(mesh, 0)
    if report.get("status") != "OK" or not report.get("verified", false):
        push_error("Runtime meshlet build failed: " + str(report))
        quit(1)
        return
    if report["triangle_count"] != 2 or report["meshlet_count"] < 1:
        push_error("Runtime meshlet coverage incorrect: " + str(report))
        quit(2)
        return

    var importer := ImporterMesh.new()
    var lods: Dictionary = {8.0: PackedInt32Array([0, 1, 2])}
    var empty_blend_shapes: Array[Array] = []
    importer.add_surface(Mesh.PRIMITIVE_TRIANGLES, arrays, empty_blend_shapes, lods)
    report = checker.build_meshlets_importer_surface(importer, 0, 0)
    if report.get("status") != "OK" or not report.get("verified", false):
        push_error("Importer LOD cluster build failed: " + str(report))
        quit(3)
        return
    if report["source_triangle_count"] != 1 or report["distance"] != 8.0:
        push_error("Importer LOD provenance lost: " + str(report))
        quit(4)
        return

    report = checker.build_meshlets_mesh_surface(mesh, 0, -1, 2, 124)
    if report.get("status") != "INVALID_LIMITS":
        push_error("Unsafe meshlet limit was not rejected: " + str(report))
        quit(5)
        return

    report = checker.build_meshlets_mesh_surface(mesh, 0, 999)
    if report.get("status") != "INVALID_LOD":
        push_error("Unknown LOD was not rejected: " + str(report))
        quit(6)
        return

    print("WorldsMeshTopology real meshoptimizer meshlet smoke: PASS")
    quit(0)

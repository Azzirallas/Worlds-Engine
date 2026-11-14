extends Node
## Isolated GPU visibility smoke test; compares RD compute results with a full CPU scan.
## Uses synchronous readback for testing ONLY. It never modifies Godot's renderer.

const SHADER_PATH := "res://visibility.comp.glsl"
const WORKGROUP_SIZE := 64
const REGION_SIZE := 8.0
const EPSILON := 0.0001

var failed: bool = false
var passed_cases: int = 0


func _ready() -> void:
	# A local RenderingDevice is separate from the main viewport's draw pipeline.
	var rd := RenderingServer.create_local_rendering_device()
	if rd == null:
		push_error("WORLDS_GPU_VISIBILITY_UNAVAILABLE: local RenderingDevice unsupported")
		get_tree().quit(2)
		return

	var file := load(SHADER_PATH) as RDShaderFile
	if file == null:
		push_error("WORLDS_GPU_VISIBILITY_FAIL: compute shader import unavailable")
		get_tree().quit(1)
		return

	var spirv := file.get_spirv()
	if spirv == null:
		push_error("WORLDS_GPU_VISIBILITY_FAIL: missing compiled shader")
		get_tree().quit(1)
		return

	var stage_error := spirv.get_stage_compile_error(RenderingDevice.SHADER_STAGE_COMPUTE)
	if not stage_error.is_empty():
		push_error("WORLDS_GPU_VISIBILITY_FAIL: " + stage_error)
		get_tree().quit(1)
		return

	var shader := rd.shader_create_from_spirv(spirv)
	if not shader.is_valid():
		push_error("WORLDS_GPU_VISIBILITY_FAIL: shader_create_from_spirv")
		get_tree().quit(1)
		return

	var pipeline := rd.compute_pipeline_create(shader)
	if not pipeline.is_valid():
		rd.free_rid(shader)
		push_error("WORLDS_GPU_VISIBILITY_FAIL: compute_pipeline_create")
		get_tree().quit(1)
		return

	for scenario in _test_cases():
		if not _run_case(rd, shader, pipeline, scenario):
			failed = true

	rd.free_rid(pipeline)
	rd.free_rid(shader)
	if failed:
		push_error("WORLDS_GPU_VISIBILITY_FAIL: %d scenarios passed before failure(s)" % passed_cases)
		get_tree().quit(1)
	else:
		print("WORLDS_GPU_VISIBILITY_PASS: %d scenarios; parity, layers, overflow, regions" % passed_cases)
		get_tree().quit(0)


## Generate six inward-facing planes of a cube centered on the origin.
func _box_planes(half_size: float) -> Array[Vector4]:
	return [
		Vector4(1.0, 0.0, 0.0, half_size),
		Vector4(-1.0, 0.0, 0.0, half_size),
		Vector4(0.0, 1.0, 0.0, half_size),
		Vector4(0.0, -1.0, 0.0, half_size),
		Vector4(0.0, 0.0, 1.0, half_size),
		Vector4(0.0, 0.0, -1.0, half_size)
	]


## Describe one slot, including its generation and enabled/layer selection.
func _record(position: Vector3, radius: float, layers: int, generation: int, enabled: bool = true) -> Dictionary:
	return {
		"position": position, "radius": radius, "layers": layers,
		"generation": generation, "enabled": enabled
	}


## Construct independent views, spatial distributions, overflow and stale-slot cases.
func _test_cases() -> Array[Dictionary]:
	var cases: Array[Dictionary] = []
	var empty: Array[Dictionary] = []
	cases.append({"name": "empty", "records": empty, "planes": _box_planes(10.0),
			"layers": 1, "capacity": 1, "regions": true})

	var edge: Array[Dictionary] = [
		_record(Vector3(-10.999, 0, 0), 1.0, 1, 7),
		_record(Vector3(-11.1, 0, 0), 1.0, 1, 8),
		_record(Vector3(10.999, 0, 0), 1.0, 2, 9),
		_record(Vector3(0, 0, 0), 1.0, 1, 15, false),
		_record(Vector3(0, 0, 0), 1.0, 0, 100)]
	cases.append({"name": "boundary_and_disabled", "records": edge, "planes": _box_planes(10.0),
			"layers": 1, "capacity": 8, "regions": true})

	var many: Array[Dictionary] = []
	var rng := RandomNumberGenerator.new()
	rng.seed = 25789
	for i in range(4097):
		var point := Vector3(rng.randf_range(-50, 50),
				rng.randf_range(-25, 25), rng.randf_range(-50, 50))
		many.append(_record(point, rng.randf_range(0.2, 2.0), 1 << (i % 3), i + 101,
				i % 17 != 0))

	cases.append({"name": "many_region_pruned", "records": many, "planes": _box_planes(14.0),
			"layers": 3, "capacity": 4097, "regions": true})
	cases.append({"name": "many_full_candidates", "records": many, "planes": _box_planes(14.0),
			"layers": 3, "capacity": 4097, "regions": false})
	cases.append({"name": "different_camera", "records": many, "planes": _box_planes(25.0),
			"layers": 4, "capacity": 4097, "regions": true})
	cases.append({"name": "nonunit_plane", "records": many,
			"planes": [Vector4(2.0, 1.0, 0.5, 10.0)], "layers": 7,
			"capacity": 4097, "regions": true})

	var overlap: Array[Dictionary] = []
	for i in range(257):
		overlap.append(_record(Vector3(float(i % 9) * 0.01, 0, 0), 1.0, 1, i + 1))
	cases.append({"name": "overflow", "records": overlap, "planes": _box_planes(4.0),
			"layers": 1, "capacity": 13, "regions": true})
	cases.append({"name": "all_visible", "records": overlap, "planes": _box_planes(4.0),
			"layers": 1, "capacity": 257, "regions": true})
	cases.append({"name": "invalid_candidate_diagnostic", "records": edge, "planes": _box_planes(10.0),
			"layers": 1, "capacity": 8, "regions": false, "inject_bad_candidate": true})
	return cases


## Check sphere overlap with the exact conservative predicate used by the shader.
func _sphere_visible(rec: Dictionary, planes: Array) -> bool:
	var pos: Vector3 = rec["position"]
	var radius: float = rec["radius"]
	for plane in planes:
		var normal := Vector3(plane.x, plane.y, plane.z)
		var length_n := normal.length()
		if normal.dot(pos) + plane.w < -(radius + EPSILON) * length_n:
			return false
	return true


## Test spatial AABBs without pruning any sphere crossing a region boundary.
func _bounds_visible(lo: Vector3, hi: Vector3, planes: Array) -> bool:
	for plane in planes:
		var n := Vector3(plane.x, plane.y, plane.z)
		var positive := Vector3(
				hi.x if n.x >= 0.0 else lo.x,
				hi.y if n.y >= 0.0 else lo.y,
				hi.z if n.z >= 0.0 else lo.z)
		if n.dot(positive) + plane.w < -(EPSILON * n.length()):
			return false
	return true


## Build region-pruned candidate slots on CPU, without relying on prior-frame results.
func _candidates(records: Array, planes: Array, spatial: bool) -> Array[int]:
	var ids: Array[int] = []
	if not spatial:
		for i in range(records.size()):
			ids.append(i)
		return ids

	var regions: Dictionary = {}
	for i in range(records.size()):
		var rec: Dictionary = records[i]
		var pos: Vector3 = rec["position"]
		var r: float = rec["radius"]
		var key := Vector3i(floori(pos.x / REGION_SIZE), floori(pos.y / REGION_SIZE),
				floori(pos.z / REGION_SIZE))
		if not regions.has(key):
			regions[key] = {"lo": pos - Vector3.ONE * r,
					"hi": pos + Vector3.ONE * r, "ids": []}
		var region: Dictionary = regions[key]
		region["lo"] = (region["lo"] as Vector3).min(pos - Vector3.ONE * r)
		region["hi"] = (region["hi"] as Vector3).max(pos + Vector3.ONE * r)
		region["ids"].append(i)

	for region in regions.values():
		if _bounds_visible(region["lo"], region["hi"], planes):
			for id in region["ids"]:
				ids.append(id)
	return ids


## Return the full-scan truth independently of spatial candidate selection.
func _expected(records: Array, planes: Array, mask: int) -> Array[int]:
	var result: Array[int] = []
	for i in range(records.size()):
		var rec: Dictionary = records[i]
		if rec["enabled"] and (int(rec["layers"]) & mask) != 0 and _sphere_visible(rec, planes):
			result.append(i)
	return result


## Wrap a storage buffer at a fixed binding, with zero-initialized short buffers.
func _make_buffer(rd: RenderingDevice, bytes: PackedByteArray, minimum_size: int) -> RID:
	var padded := bytes.duplicate()
	if padded.size() < minimum_size:
		padded.resize(minimum_size)
	return rd.storage_buffer_create(padded.size(), padded)


## Produce one GDScript RDUniform storage-buffer descriptor.
func _storage_uniform(binding_index: int, buffer: RID) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	uniform.binding = binding_index
	uniform.add_id(buffer)
	return uniform


## Dispatch once, read back only for test verification, then release all buffers.
func _run_case(rd: RenderingDevice, shader: RID, pipeline: RID, scenario: Dictionary) -> bool:
	var name: String = scenario["name"]
	var records: Array = scenario["records"]
	var planes: Array = scenario["planes"]
	var view_mask: int = scenario["layers"]
	var capacity: int = scenario["capacity"]
	var candidates := _candidates(records, planes, scenario["regions"])
	var expected := _expected(records, planes, view_mask)
	for slot in expected:
		if not candidates.has(slot):
			push_error(name + ": CPU region pruning lost visible slot %d" % slot)
			return false
	if scenario.get("inject_bad_candidate", false):
		candidates.append(records.size() + 10)

	var sphere_data := PackedFloat32Array()
	var meta_data := PackedInt32Array()
	for rec in records:
		var position: Vector3 = rec["position"]
		sphere_data.append_array(PackedFloat32Array([position.x, position.y, position.z,
				rec["radius"]]))
		meta_data.append_array(PackedInt32Array([
				int(rec["layers"]) if rec["enabled"] else 0, rec["generation"]]))
	var plane_data := PackedFloat32Array()
	for plane in planes:
		plane_data.append_array(PackedFloat32Array([plane.x, plane.y, plane.z, plane.w]))
	var candidate_data := PackedInt32Array()
	for slot in candidates:
		candidate_data.append(slot)

	var buffers: Array[RID] = [
		_make_buffer(rd, sphere_data.to_byte_array(), 16),
		_make_buffer(rd, meta_data.to_byte_array(), 8),
		_make_buffer(rd, candidate_data.to_byte_array(), 4),
		_make_buffer(rd, plane_data.to_byte_array(), 16),
		_make_buffer(rd, PackedByteArray(), maxi(1, capacity) * 8),
		_make_buffer(rd, PackedInt32Array([0, 0]).to_byte_array(), 8)
	]
	var valid := true
	for buf in buffers:
		if not buf.is_valid():
			valid = false
	if not valid:
		push_error(name + ": storage allocation failed")
		for buf in buffers:
			if buf.is_valid():
				rd.free_rid(buf)
		return false

	var uniforms: Array[RDUniform] = []
	for i in range(buffers.size()):
		uniforms.append(_storage_uniform(i, buffers[i]))
	var uniform_set := rd.uniform_set_create(uniforms, shader, 0)
	if not uniform_set.is_valid():
		push_error(name + ": uniform set failed")
		for buf in buffers:
			rd.free_rid(buf)
		return false

	var commands := rd.compute_list_begin()
	rd.compute_list_bind_compute_pipeline(commands, pipeline)
	rd.compute_list_bind_uniform_set(commands, uniform_set, 0)
	var push_data := PackedInt32Array([candidates.size(), planes.size(), view_mask,
			capacity, records.size(), 0, 0, 0]).to_byte_array()
	rd.compute_list_set_push_constant(commands, push_data, push_data.size())
	rd.compute_list_dispatch(commands, maxi(1, ceili(float(candidates.size()) / WORKGROUP_SIZE)), 1, 1)
	rd.compute_list_end()
	rd.submit()
	rd.sync()

	var count_data := rd.buffer_get_data(buffers[5])
	var result_data := rd.buffer_get_data(buffers[4])
	var actual_count := int(count_data.decode_u32(0))
	var flags := int(count_data.decode_u32(4))
	var expected_flags := (1 if expected.size() > capacity else 0)
	if scenario.get("inject_bad_candidate", false):
		expected_flags |= 2

	var actual: Array[int] = []
	for i in range(mini(actual_count, capacity)):
		var slot := int(result_data.decode_u32(i * 8))
		var generation := int(result_data.decode_u32(i * 8 + 4))
		if slot < 0 or slot >= records.size() or generation != int(records[slot]["generation"]):
			valid = false
			break
		actual.append(slot)
	actual.sort()
	expected.sort()

	if actual_count != expected.size() or flags != expected_flags:
		valid = false
	if actual.size() != mini(expected.size(), capacity):
		valid = false
	if expected_flags & 1:
		# Atomic output order is undefined when the buffer deliberately overflows.
		for slot in actual:
			if not expected.has(slot):
				valid = false
	else:
		if actual != expected:
			valid = false

	rd.free_rid(uniform_set)
	for buf in buffers:
		rd.free_rid(buf)
	if not valid:
		push_error("GPU visibility mismatch [%s]: expected=%d actual=%d flags=%d/%d" %
				[name, expected.size(), actual_count, flags, expected_flags])
		return false
	passed_cases += 1
	print("WORLDS_GPU_CASE_PASS %s candidates=%d visible=%d flags=%d" %
			[name, candidates.size(), expected.size(), flags])
	return true

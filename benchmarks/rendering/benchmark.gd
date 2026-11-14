extends Node3D
## Generates deterministic 3D scene variants and samples built-in renderer counters.
## This is a baseline test tool, not an engine implementation or a GPU profiler.

const VALID_MODES := ["nodes", "one_multimesh", "regional_multimesh"]

var mode: String = "regional_multimesh"
var count: int = 10000
var region_size: float = 16.0
var world_span: float = 200.0
var bounds_mode: String = "computed"
var warmup_frames: int = 120
var sample_frames: int = 360
var disable_vsync: bool = false
var camera_path: String = "orbit"
var move_percent: int = 0

var camera: Camera3D
var viewport_rid: RID
var frame_index: int = 0
var startup_usec: int = 0

var frame_ms: Array[float] = []
var cpu_render_ms: Array[float] = []
var gpu_render_ms: Array[float] = []
var draw_calls: Array[float] = []
var rendered_objects: Array[float] = []
var build_milliseconds: float = 0.0
var actual_group_count: int = 0
var motion_nodes: Array[MeshInstance3D] = []
var motion_node_origins: Array[Vector3] = []
var motion_multimeshes: Array[MultiMesh] = []
var motion_multimesh_slots: Array[int] = []
var motion_multimesh_origins: Array[Vector3] = []
var valid_gpu_samples: int = 0


func _ready() -> void:
	_read_arguments()
	if not VALID_MODES.has(mode):
		push_error("Unknown --mode=" + mode)
		get_tree().quit(1)
		return

	if disable_vsync:
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)

	viewport_rid = get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(viewport_rid, true)
	_create_camera_and_light()

	startup_usec = Time.get_ticks_usec()
	_build_scene()
	build_milliseconds = float(Time.get_ticks_usec() - startup_usec) / 1000.0
	print("Worlds rendering baseline | mode=", mode, " | count=", count,
			" | groups=", actual_group_count, " | region_size=", region_size,
			" | bounds=", bounds_mode, " | build_ms=", build_milliseconds,
			" | warmup=", warmup_frames, " | frames=", sample_frames,
			" | camera=", camera_path, " | move_pct=", move_percent)


## Read reproducible configuration from arguments after Godot's '--' separator.
func _read_arguments() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--mode="):
			mode = arg.trim_prefix("--mode=")
		elif arg.begins_with("--count="):
			count = maxi(0, int(arg.trim_prefix("--count=")))
		elif arg.begins_with("--region="):
			region_size = maxf(1.0, float(arg.trim_prefix("--region=")))
		elif arg.begins_with("--span="):
			world_span = maxf(10.0, float(arg.trim_prefix("--span=")))
		elif arg.begins_with("--bounds="):
			bounds_mode = arg.trim_prefix("--bounds=")
		elif arg.begins_with("--warmup="):
			warmup_frames = maxi(2, int(arg.trim_prefix("--warmup=")))
		elif arg.begins_with("--frames="):
			sample_frames = maxi(10, int(arg.trim_prefix("--frames=")))
		elif arg.begins_with("--camera="):
			camera_path = arg.trim_prefix("--camera=")
		elif arg.begins_with("--move="):
			move_percent = clampi(int(arg.trim_prefix("--move=")), 0, 100)
		elif arg == "--vsync=off":
			disable_vsync = true

	if camera_path != "orbit" and camera_path != "fixed" and camera_path != "cut":
		push_warning("Invalid --camera; using orbit.")
		camera_path = "orbit"
	if bounds_mode != "computed" and bounds_mode != "custom":
		push_warning("Invalid --bounds; using computed.")
		bounds_mode = "computed"


## Use a common simple light and orbiting camera across every representation.
func _create_camera_and_light() -> void:
	camera = Camera3D.new()
	camera.fov = 70.0
	camera.far = 1000.0
	camera.current = true
	add_child(camera)

	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-55.0, -35.0, 0.0)
	light.shadow_enabled = false
	add_child(light)


## Create the same deterministic placement and mesh for every comparison mode.
func _build_scene() -> void:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.8, 1.5, 0.8)

	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.65, 0.75, 0.9)
	mesh.material = material

	if mode == "nodes":
		for index in range(count):
			var instance := MeshInstance3D.new()
			instance.mesh = mesh
			instance.position = _position_for(index)
			add_child(instance)
			if _is_moving(index):
				motion_nodes.append(instance)
				motion_node_origins.append(instance.position)
		actual_group_count = count
	elif mode == "one_multimesh":
		var positions: Array[Vector3] = []
		var indices: Array[int] = []
		positions.resize(count)
		for index in range(count):
			positions[index] = _position_for(index)
			indices.append(index)
		_create_multimesh(mesh, positions, indices)
		actual_group_count = 0 if count == 0 else 1
	else:
		var regions: Dictionary = {}
		for index in range(count):
			var pos := _position_for(index)
			var region := Vector2i(floori((pos.x + world_span * 0.5) / region_size),
					floori((pos.z + world_span * 0.5) / region_size))
			if not regions.has(region):
				regions[region] = []
			regions[region].append({"position": pos, "index": index})
		for region in regions:
			var positions: Array[Vector3] = []
			var indices: Array[int] = []
			for item in regions[region]:
				positions.append(item["position"])
				indices.append(item["index"])
			_create_multimesh(mesh, positions, indices)
		actual_group_count = regions.size()


## Compute stable placements inside the same world footprint at every count.
func _position_for(index: int) -> Vector3:
	var columns := maxi(1, ceili(sqrt(float(count))))
	var step := world_span / float(maxi(columns - 1, 1))
	var x := float(index % columns) * step - world_span * 0.5
	var z := float(index / columns) * step - world_span * 0.5
	return Vector3(x, 0.0, z)


## Build one Godot MultiMesh group; optionally set conservative fixed bounds.
func _create_multimesh(mesh: Mesh, positions: Array[Vector3], indices: Array[int]) -> void:
	if positions.is_empty():
		return
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = mesh
	multimesh.instance_count = positions.size()
	for index in range(positions.size()):
		multimesh.set_instance_transform(index, Transform3D(Basis(), positions[index]))
		if _is_moving(indices[index]):
			motion_multimeshes.append(multimesh)
			motion_multimesh_slots.append(index)
			motion_multimesh_origins.append(positions[index])

	if bounds_mode == "custom":
		var min_x := positions[0].x
		var max_x := positions[0].x
		var min_z := positions[0].z
		var max_z := positions[0].z
		for position in positions:
			min_x = minf(min_x, position.x)
			max_x = maxf(max_x, position.x)
			min_z = minf(min_z, position.z)
			max_z = maxf(max_z, position.z)
		multimesh.custom_aabb = AABB(Vector3(min_x - 1.0, -1.0, min_z - 1.0),
				Vector3(max_x - min_x + 2.0, 3.5, max_z - min_z + 2.0))

	var instance := MultiMeshInstance3D.new()
	instance.multimesh = multimesh
	add_child(instance)


## Mark deterministic, uniformly distributed objects for movement.
func _is_moving(index: int) -> bool:
	return move_percent > 0 and (index * 73) % 100 < move_percent


## Update only the selected instance transforms; leave static controls untouched.
func _update_motion() -> void:
	if move_percent == 0:
		return
	var offset := Vector3(0.0, sin(float(frame_index) * 0.075) * 0.5, 0.0)
	for index in range(motion_nodes.size()):
		motion_nodes[index].position = motion_node_origins[index] + offset
	for index in range(motion_multimeshes.size()):
		motion_multimeshes[index].set_instance_transform(motion_multimesh_slots[index],
				Transform3D(Basis(), motion_multimesh_origins[index] + offset))


## Drive deterministic orbit/fixed/cut cameras and sample per-frame metrics.
func _process(delta: float) -> void:
	if camera_path == "orbit":
		var phase := float(frame_index % 720) * TAU / 720.0
		camera.position = Vector3(cos(phase) * 150.0, 50.0, sin(phase) * 150.0)
	elif camera_path == "cut":
		camera.position = Vector3(150.0 if int(frame_index / 120) % 2 == 0 else -150.0, 50.0, 0.0)
	else:
		camera.position = Vector3(150.0, 50.0, 0.0)
	camera.look_at(Vector3.ZERO, Vector3.UP)
	_update_motion()

	if frame_index >= warmup_frames and frame_index < warmup_frames + sample_frames:
		frame_ms.append(delta * 1000.0)
		cpu_render_ms.append(RenderingServer.viewport_get_measured_render_time_cpu(viewport_rid))
		var gpu_time := RenderingServer.viewport_get_measured_render_time_gpu(viewport_rid)
		gpu_render_ms.append(gpu_time if gpu_time > 0.0 else -1.0)
		if gpu_time > 0.0:
			valid_gpu_samples += 1
		draw_calls.append(float(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)))
		rendered_objects.append(float(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)))

	frame_index += 1
	if frame_index >= warmup_frames + sample_frames:
		get_tree().quit(0 if _write_report() else 1)


## Return a percentile from sampled values, without implying a GPU synchronization.
func _percentile(samples: Array[float], p: float) -> float:
	if samples.is_empty():
		return -1.0
	var sorted: Array[float] = samples.duplicate()
	sorted.sort()
	var at := clampi(ceili(float(sorted.size() - 1) * p), 0, sorted.size() - 1)
	return sorted[at]


## Discard zero/unavailable timings rather than presenting them as genuine measurements.
func _timing_percentile(samples: Array[float], p: float) -> float:
	var valid: Array[float] = []
	for value in samples:
		if value > 0.0:
			valid.append(value)
	return _percentile(valid, p)


## Write both summary and every raw sample for independent analysis.
func _write_report() -> bool:
	var stem := "render_baseline_%s_%d_%s_%d" % [
			mode, count, bounds_mode, Time.get_ticks_usec()]
	var path := "user://" + stem + ".csv"
	var raw_path := "user://" + stem + "_samples.csv"
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("Could not write " + path)
		return false
	file.store_line("mode,count,groups,region_size,world_span,bounds,warmup_frames,sample_frames,build_ms,frame_p50_ms,frame_p95_ms,frame_p99_ms,render_cpu_p50_ms,render_cpu_p95_ms,render_gpu_p50_ms,render_gpu_p95_ms,draw_calls_p50,draw_calls_p95,objects_p50,camera_path,move_percent,moving_count,valid_gpu_samples")
	file.store_line("%s,%d,%d,%.2f,%.2f,%s,%d,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.1f,%.1f,%.1f,%s,%d,%d,%d" % [
			mode, count, actual_group_count, region_size, world_span, bounds_mode,
			warmup_frames, sample_frames, build_milliseconds,
			_percentile(frame_ms, 0.50), _percentile(frame_ms, 0.95),
			_percentile(frame_ms, 0.99), _timing_percentile(cpu_render_ms, 0.50),
			_timing_percentile(cpu_render_ms, 0.95), _timing_percentile(gpu_render_ms, 0.50),
			_timing_percentile(gpu_render_ms, 0.95), _percentile(draw_calls, 0.50),
			_percentile(draw_calls, 0.95), _percentile(rendered_objects, 0.50),
			camera_path, move_percent, motion_nodes.size() + motion_multimeshes.size(), valid_gpu_samples])
	file.close()
	var raw := FileAccess.open(raw_path, FileAccess.WRITE)
	if raw == null:
		push_error("Could not write " + raw_path)
		return false
	raw.store_line("frame,frame_delta_ms,render_cpu_ms,render_gpu_ms,draw_calls,objects")
	for index in range(frame_ms.size()):
		raw.store_line("%d,%.6f,%.6f,%.6f,%.0f,%.0f" % [
				index, frame_ms[index], cpu_render_ms[index], gpu_render_ms[index],
				draw_calls[index], rendered_objects[index]])
	raw.close()
	print("WORLDS_BENCHMARK_COMPLETE ", ProjectSettings.globalize_path(path))
	print("WORLDS_BENCHMARK_SAMPLES ", ProjectSettings.globalize_path(raw_path))
	print("Frame P50/P95/P99 (ms): ", _percentile(frame_ms, 0.5), " / ",
			_percentile(frame_ms, 0.95), " / ", _percentile(frame_ms, 0.99))
	print("Viewport GPU P50 (ms): ", _timing_percentile(gpu_render_ms, 0.5),
			" | draw calls P50: ", _percentile(draw_calls, 0.5))
	return true

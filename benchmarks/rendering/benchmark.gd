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
			" | warmup=", warmup_frames, " | frames=", sample_frames)


## Read reproducible configuration from arguments after Godot's '--' separator.
func _read_arguments() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--mode="):
			mode = arg.trim_prefix("--mode=")
		elif arg.begins_with("--count="):
			count = maxi(1, int(arg.trim_prefix("--count=")))
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
		elif arg == "--vsync=off":
			disable_vsync = true

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
		actual_group_count = count
	elif mode == "one_multimesh":
		var positions: Array[Vector3] = []
		positions.resize(count)
		for index in range(count):
			positions[index] = _position_for(index)
		_create_multimesh(mesh, positions)
		actual_group_count = 1
	else:
		var regions: Dictionary = {}
		for index in range(count):
			var pos := _position_for(index)
			var region := Vector2i(floori((pos.x + world_span * 0.5) / region_size),
					floori((pos.z + world_span * 0.5) / region_size))
			if not regions.has(region):
				regions[region] = []
			regions[region].append(pos)
		for region in regions:
			var positions: Array[Vector3] = []
			for pos in regions[region]:
				positions.append(pos)
			_create_multimesh(mesh, positions)
		actual_group_count = regions.size()


## Compute stable placements inside the same world footprint at every count.
func _position_for(index: int) -> Vector3:
	var columns := maxi(1, ceili(sqrt(float(count))))
	var step := world_span / float(maxi(columns - 1, 1))
	var x := float(index % columns) * step - world_span * 0.5
	var z := float(index / columns) * step - world_span * 0.5
	return Vector3(x, 0.0, z)


## Build one Godot MultiMesh group; optionally set conservative fixed bounds.
func _create_multimesh(mesh: Mesh, positions: Array[Vector3]) -> void:
	if positions.is_empty():
		return
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = mesh
	multimesh.instance_count = positions.size()
	for index in range(positions.size()):
		multimesh.set_instance_transform(index, Transform3D(Basis(), positions[index]))

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


## Drive a fixed per-frame camera orbit and record wall, CPU, GPU and draw metrics.
func _process(delta: float) -> void:
	var phase := float(frame_index % 720) * TAU / 720.0
	camera.position = Vector3(cos(phase) * 150.0, 50.0, sin(phase) * 150.0)
	camera.look_at(Vector3.ZERO, Vector3.UP)

	if frame_index >= warmup_frames and frame_index < warmup_frames + sample_frames:
		frame_ms.append(delta * 1000.0)
		cpu_render_ms.append(RenderingServer.viewport_get_measured_render_time_cpu(viewport_rid))
		gpu_render_ms.append(RenderingServer.viewport_get_measured_render_time_gpu(viewport_rid))
		draw_calls.append(float(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)))
		rendered_objects.append(float(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)))

	frame_index += 1
	if frame_index >= warmup_frames + sample_frames:
		_write_report()
		get_tree().quit()


## Return a percentile from sampled values, without implying a GPU synchronization.
func _percentile(samples: Array[float], p: float) -> float:
	if samples.is_empty():
		return -1.0
	var sorted: Array[float] = samples.duplicate()
	sorted.sort()
	var at := clampi(ceili(float(sorted.size() - 1) * p), 0, sorted.size() - 1)
	return sorted[at]


## Store a CSV summary under user:// and print its physical path for collection.
func _write_report() -> void:
	var path := "user://render_baseline_%s_%d_%s_%d.csv" % [
			mode, count, bounds_mode, Time.get_unix_time_from_system()]
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("Could not write " + path)
		return
	file.store_line("mode,count,groups,region_size,world_span,bounds,warmup_frames,sample_frames,build_ms,frame_p50_ms,frame_p95_ms,frame_p99_ms,render_cpu_p50_ms,render_cpu_p95_ms,render_gpu_p50_ms,render_gpu_p95_ms,draw_calls_p50,draw_calls_p95,objects_p50")
	file.store_line("%s,%d,%d,%.2f,%.2f,%s,%d,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.1f,%.1f,%.1f" % [
			mode, count, actual_group_count, region_size, world_span, bounds_mode,
			warmup_frames, sample_frames, build_milliseconds,
			_percentile(frame_ms, 0.50), _percentile(frame_ms, 0.95),
			_percentile(frame_ms, 0.99), _percentile(cpu_render_ms, 0.50),
			_percentile(cpu_render_ms, 0.95), _percentile(gpu_render_ms, 0.50),
			_percentile(gpu_render_ms, 0.95), _percentile(draw_calls, 0.50),
			_percentile(draw_calls, 0.95), _percentile(rendered_objects, 0.50)])
	file.close()
	print("WORLDS_BENCHMARK_COMPLETE ", ProjectSettings.globalize_path(path))
	print("Frame P50/P95/P99 (ms): ", _percentile(frame_ms, 0.5), " / ",
			_percentile(frame_ms, 0.95), " / ", _percentile(frame_ms, 0.99))
	print("Viewport GPU P50 (ms): ", _percentile(gpu_render_ms, 0.5),
			" | draw calls P50: ", _percentile(draw_calls, 0.5))

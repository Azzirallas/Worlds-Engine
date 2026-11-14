extends "res://runner.gd"
## Optional local-RD raster experiment: visibility compute → guarded indirect draw → pixel check.
## It never replaces or modifies normal RenderingServer scene rendering.

const PROBE_SHADER_PATH := "res://indirect_probe.glsl"


func _ready() -> void:
	var rd := RenderingServer.create_local_rendering_device()
	if rd == null:
		push_error("WORLDS_OFFSCREEN_UNAVAILABLE: no local RenderingDevice")
		get_tree().quit(2)
		return

	var visibility := _load_kernel(rd, SHADER_PATH)
	if visibility.is_empty():
		get_tree().quit(1)
		return
	var guard := _load_kernel(rd, GUARD_SHADER_PATH)
	if guard.is_empty():
		rd.free_rid(visibility["pipeline"])
		rd.free_rid(visibility["shader"])
		get_tree().quit(1)
		return
	var probe := _create_probe(rd)
	if probe.is_empty():
		rd.free_rid(guard["pipeline"])
		rd.free_rid(guard["shader"])
		rd.free_rid(visibility["pipeline"])
		rd.free_rid(visibility["shader"])
		get_tree().quit(1)
		return

	for scenario in _test_cases():
		if not _run_case(rd, visibility["shader"], visibility["pipeline"],
				guard["shader"], guard["pipeline"], scenario, probe):
			failed = true

	rd.free_rid(probe["pipeline"])
	rd.free_rid(probe["framebuffer"])
	rd.free_rid(probe["texture"])
	rd.free_rid(probe["shader"])
	rd.free_rid(guard["pipeline"])
	rd.free_rid(guard["shader"])
	rd.free_rid(visibility["pipeline"])
	rd.free_rid(visibility["shader"])

	if failed:
		push_error("WORLDS_OFFSCREEN_FAIL: %d cases passed before failure(s)" % passed_cases)
		get_tree().quit(1)
	else:
		print("WORLDS_OFFSCREEN_PASS: %d cases matched visibility, indirect count and pixels" % passed_cases)
		get_tree().quit(0)


## Create a tiny RGBA8 framebuffer and a shader requiring no vertex buffers.
func _create_probe(rd: RenderingDevice) -> Dictionary:
	var file := load(PROBE_SHADER_PATH) as RDShaderFile
	if file == null:
		push_error("WORLDS_OFFSCREEN_FAIL: raster shader import unavailable")
		return {}
	var spirv := file.get_spirv()
	if spirv == null:
		push_error("WORLDS_OFFSCREEN_FAIL: missing raster SPIR-V")
		return {}
	for stage in [RenderingDevice.SHADER_STAGE_VERTEX, RenderingDevice.SHADER_STAGE_FRAGMENT]:
		var error := spirv.get_stage_compile_error(stage)
		if not error.is_empty():
			push_error("WORLDS_OFFSCREEN_FAIL: raster shader compilation: " + error)
			return {}

	var shader := rd.shader_create_from_spirv(spirv)
	if not shader.is_valid():
		push_error("WORLDS_OFFSCREEN_FAIL: shader_create_from_spirv")
		return {}

	var texture_format := RDTextureFormat.new()
	texture_format.width = 32
	texture_format.height = 32
	texture_format.format = RenderingDevice.DATA_FORMAT_R8G8B8A8_UNORM
	texture_format.usage_bits = (RenderingDevice.TEXTURE_USAGE_COLOR_ATTACHMENT_BIT
			| RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT)
	if not rd.texture_is_format_supported_for_usage(texture_format.format, texture_format.usage_bits):
		rd.free_rid(shader)
		push_error("WORLDS_OFFSCREEN_UNAVAILABLE: RGBA8 framebuffer usage unsupported")
		return {}

	var texture := rd.texture_create(texture_format, RDTextureView.new())
	if not texture.is_valid():
		rd.free_rid(shader)
		push_error("WORLDS_OFFSCREEN_FAIL: color texture creation")
		return {}
	var framebuffer := rd.framebuffer_create([texture])
	if not framebuffer.is_valid():
		rd.free_rid(texture)
		rd.free_rid(shader)
		push_error("WORLDS_OFFSCREEN_FAIL: framebuffer creation")
		return {}

	var blend := RDPipelineColorBlendState.new()
	blend.attachments = [RDPipelineColorBlendStateAttachment.new()]
	var pipeline := rd.render_pipeline_create(shader, rd.framebuffer_get_format(framebuffer),
			-1, RenderingDevice.RENDER_PRIMITIVE_TRIANGLES,
			RDPipelineRasterizationState.new(), RDPipelineMultisampleState.new(),
			RDPipelineDepthStencilState.new(), blend)
	if not pipeline.is_valid():
		rd.free_rid(framebuffer)
		rd.free_rid(texture)
		rd.free_rid(shader)
		push_error("WORLDS_OFFSCREEN_FAIL: render_pipeline_create")
		return {}
	return {"shader": shader, "pipeline": pipeline,
			"framebuffer": framebuffer, "texture": texture}

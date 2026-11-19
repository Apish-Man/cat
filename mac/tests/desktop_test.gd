extends SceneTree
## Run on macOS using the real renderer. Captures only the application's viewport.
const Main = preload("res://app/main.tscn")
const StandIn = preload("res://characters/prototype/stand_in.tscn")
var failures := 0

func check(condition: bool, label: String) -> void:
	if not condition:
		push_error(label)
		failures += 1

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	var temporary := DirAccess.create_temp("catmate-window-test")
	if temporary == null:
		quit(1)
		return
	var runtime = Main.instantiate()
	runtime.prefs.path = temporary.get_current_dir().path_join("prefs.cfg")
	root.add_child(runtime)
	await create_timer(0.65).timeout
	check(runtime.outline.size() > 5, "character supplied an interactive body outline")
	var image := root.get_texture().get_image()
	check(image.get_pixel(0, 0).a < 0.01, "viewport corner is transparent")
	check(image.get_pixel(image.get_width()/2, image.get_height()/2).a > 0.8, "cat opaque")
	if OS.get_cmdline_user_args().size() == 1:
		check(image.save_png(OS.get_cmdline_user_args()[0]) == OK, "preview image saved")
	runtime.set_process(false)
	var character: Node3D = runtime.get_node("Character")
	var frames_checked := 0
	for scale_value in [0.6, 1.0, 1.5]:
		runtime.prefs.scale_value = scale_value
		runtime._resize()
		for facing in [1, -1, 1]:
			character.basis = Basis.from_scale(Vector3(facing, 1, 1))
			runtime.last_facing = facing
			runtime.outline_dirty = true
			runtime._refresh_outline()
			for action in [&"walk", &"held", &"petted", &"idle"]:
				for sample in range(4):
					character.pose(action, 1.0, 0.1)
					await RenderingServer.frame_post_draw
					var frame := root.get_texture().get_image()
					check(check_outline(frame, runtime.outline), "%s scale=%s facing=%s sample=%s" % [action, scale_value, facing, sample])
					frames_checked += 1
				check(character.playback.get_current_node() == action, "animation transition " + str(action))
	runtime.prefs.scale_value = 1.0
	runtime._resize()
	var old_size: Vector2i = root.size
	runtime._menu_action(2)
	check(root.size.x > old_size.x, "size action changes OS window")
	runtime._menu_action(3)
	check(runtime.prefs.eco, "power preference")
	runtime._menu_action(0)
	check(runtime.motion.position.is_equal_approx(runtime.motion.bounds.get_center()), "locate")
	var registered: bool = NativeMenu.has_feature(NativeMenu.FEATURE_POPUP_MENU) and runtime.indicator.get_rect().size.x > 0
	check(registered, "native menu bar item registered")
	# The development scene uses the same desktop input and motion owner.
	runtime.remove_child(character)
	character.free()
	character = StandIn.instantiate()
	character.name = "Character"
	runtime.add_child(character)
	runtime.outline_dirty = true
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	check(check_outline(root.get_texture().get_image(), runtime.outline), "stand-in hit outline")
	print("desktop test: animation frames=", frames_checked, " native menu=", registered, " failures=", failures)
	runtime.queue_free()
	await process_frame
	quit(1 if failures else 0)

func check_outline(frame: Image, polygon: PackedVector2Array) -> bool:
	var hits := 0
	for y in range(0, frame.get_height(), 4):
		for x in range(0, frame.get_width(), 4):
			if Geometry2D.is_point_in_polygon(Vector2(x, y), polygon):
				hits += 1
				if frame.get_pixel(x, y).a < 0.05:
					print("Transparent hit at ", Vector2i(x, y))
					return false
	return hits > 60

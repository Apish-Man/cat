extends SceneTree
## Run on macOS using the real renderer. Captures only the application's viewport.
const Main = preload("res://app/main.tscn")
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
	check(runtime.outline.size() > 5, "silhouette read from rendered alpha")
	var image := root.get_texture().get_image()
	check(image.get_pixel(0, 0).a < 0.01, "viewport corner is transparent")
	check(image.get_pixel(image.get_width()/2, image.get_height()/2).a > 0.8, "cat opaque")
	var samples := 0
	var false_hits := 0
	for y in range(0, image.get_height(), 3):
		for x in range(0, image.get_width(), 3):
			if Geometry2D.is_point_in_polygon(Vector2(x,y), runtime.outline):
				samples += 1
				if image.get_pixel(x,y).a < 0.05:
					if false_hits == 0:
						print("Unexpected transparent hit at ", Vector2i(x, y))
					false_hits += 1
	check(samples > 60 and false_hits == 0, "silhouette outside visible cat")
	if OS.get_cmdline_user_args().size() == 1:
		check(image.save_png(OS.get_cmdline_user_args()[0]) == OK, "preview image saved")
	var old_size: Vector2i = root.size
	runtime._menu_action(2)
	check(root.size.x > old_size.x, "size action changes OS window")
	runtime._menu_action(3)
	check(runtime.prefs.eco, "power preference")
	runtime._menu_action(0)
	check(runtime.motion.position.is_equal_approx(runtime.motion.bounds.get_center()), "locate")
	var registered: bool = NativeMenu.has_feature(NativeMenu.FEATURE_POPUP_MENU) and runtime.indicator.get_rect().size.x > 0
	check(registered, "native menu bar item registered")
	print("desktop test: drawn=", samples, " false_hits=", false_hits, " native menu=", registered, " failures=", failures)
	runtime.queue_free()
	await process_frame
	quit(1 if failures else 0)

extends Node
## Test-only startup scene used by tools/measure_macos.py.
## The app renders and moves normally. Only autonomous destination selection is pinned.
func _ready() -> void:
	run.call_deferred()

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 3 or args[0] not in ["idle", "walk"] or args[1].to_float() <= 0:
		printerr("expected -- idle|walk duration_seconds result_path")
		get_tree().quit(2)
		return
	var temporary := DirAccess.create_temp("catmate-bench")
	if temporary == null:
		get_tree().quit(1)
		return
	var runtime = load("res://app/main.tscn").instantiate()
	runtime.prefs.path = temporary.get_current_dir().path_join("settings.cfg")
	add_child(runtime)
	var motion = runtime.motion
	var left: Vector2 = motion.bounds.position + motion.bounds.size * Vector2(0.63, 0.84)
	var right: Vector2 = motion.bounds.position + motion.bounds.size * Vector2(0.88, 0.84)
	motion.position = left
	var destination := right
	var intervals := PackedFloat64Array()
	var start := Time.get_ticks_usec()
	var previous := start
	while Time.get_ticks_usec() - start < args[1].to_float() * 1e6:
		if args[0] == "idle":
			motion._remaining = 4.5
		elif motion.state != motion.State.WALK:
			motion.move_to(destination)
			destination = left if destination == right else right
		await get_tree().process_frame
		var now := Time.get_ticks_usec()
		intervals.append((now - previous) / 1000.0)
		previous = now
	intervals.sort()
	var result := JSON.stringify({"mode": args[0], "seconds": (previous - start) / 1e6,
		"frames": intervals.size(), "p50_ms": intervals[intervals.size()/2],
		"p95_ms": intervals[int(intervals.size()*0.95)], "distance_pt": motion.distance_walked})
	var file := FileAccess.open(args[2], FileAccess.WRITE)
	if file == null:
		get_tree().quit(1)
		return
	file.store_line(result)
	file.close()
	runtime.free()
	get_tree().quit(0)

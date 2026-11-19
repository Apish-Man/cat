extends Node3D

const Motion = preload("res://core/companion_motion.gd")
const Desktop = preload("res://desktop/desktop_space.gd")
const Preferences = preload("res://settings/preferences.gd")
const BASE_SIZE := 224.0
const FOOT := Vector2(0.5, 0.855)

var motion := Motion.new()
var desktop := Desktop.new()
var prefs := Preferences.new()
var screen_index := 0
var logical_size := Vector2.ONE * BASE_SIZE
var outline := PackedVector2Array()
var outline_dirty := true
var menu := PopupMenu.new()
var indicator := StatusIndicator.new()
var since_layout := 0.0
var current_layout: Array = []
var last_facing := 1
var entered_head := false
var ready_for_input := false

func _ready() -> void:
	get_viewport().transparent_bg = true
	if DisplayServer.get_name() == "headless":
		set_process(false)
		return
	prefs.read()
	screen_index = DisplayServer.get_primary_screen()
	for i in DisplayServer.get_screen_count():
		if desktop.screen_key(i) == prefs.screen:
			screen_index = i
			break
	_resize()
	var allowed := _bounds()
	motion.setup(allowed.position + allowed.size * prefs.relative, allowed, Time.get_ticks_msec())
	_place()
	_install_menu()
	get_window().focus_exited.connect(_cancel_capture)
	current_layout = _layout()
	ready_for_input = true
	RenderingServer.frame_post_draw.connect(_refresh_outline)

func _resize() -> void:
	var extent := minf(BASE_SIZE * prefs.scale_value, minf(desktop.usable(screen_index).size.x, desktop.usable(screen_index).size.y))
	logical_size = Vector2.ONE * maxf(1.0, extent)
	get_window().size = Vector2i((logical_size * desktop.scale_factor()).round())
	outline_dirty = true

func _bounds() -> Rect2:
	return desktop.foot_bounds(screen_index, logical_size, logical_size * FOOT)

func _place() -> void:
	var desired := desktop.pixel(motion.position - logical_size * FOOT)
	if get_window().position != desired:
		get_window().position = desired

func _install_menu() -> void:
	menu.name = "Menu"
	indicator.add_child(menu)
	indicator.menu = NodePath("Menu")
	indicator.tooltip = "猫在 · CatMate"
	indicator.icon = preload("res://desktop/menu_icon.svg")
	add_child(indicator)
	menu.add_item("找回小猫", 0)
	menu.add_item("缩小", 1)
	menu.add_item("放大", 2)
	menu.add_check_item("省电模式", 3)
	menu.set_item_checked(menu.get_item_index(3), prefs.eco)
	menu.add_separator()
	menu.add_item("退出猫在", 4)
	menu.id_pressed.connect(_menu_action)

func _menu_action(id: int) -> void:
	match id:
		0:
			screen_index = DisplayServer.get_primary_screen()
			_resize()
			motion.set_bounds(_bounds())
			motion.position = motion.bounds.get_center()
			_cancel_capture()
		1, 2:
			prefs.scale_value = clampf(prefs.scale_value + (-0.15 if id == 1 else 0.15), 0.6, 1.5)
			_resize()
			motion.set_bounds(_bounds())
		3:
			prefs.eco = not prefs.eco
			menu.set_item_checked(menu.get_item_index(3), prefs.eco)
		4:
			get_tree().quit()
	_place()
	_save()

func _process(dt: float) -> void:
	since_layout += dt
	if since_layout >= 1.0:
		since_layout = 0.0
		var layout := _layout()
		if layout != current_layout:
			current_layout = layout
			_cancel_capture()
			screen_index = desktop.screen_at(motion.position)
			_resize()
			motion.set_bounds(_bounds())
	motion.advance(dt)
	if motion.facing != last_facing:
		last_facing = motion.facing
		$Character.scale.x = last_facing
		outline_dirty = true
	_place()
	var walking := motion.state == Motion.State.WALK or motion.pressed
	Engine.max_fps = (30 if prefs.eco else 60) if walking else (6 if prefs.eco else 12)

func _layout() -> Array:
	var result: Array = [desktop.scale_factor(), desktop.origin()]
	for i in DisplayServer.get_screen_count():
		result.append(desktop.usable(i))
	return result

func _refresh_outline() -> void:
	if not outline_dirty or motion.pressed:
		return
	var image := get_viewport().get_texture().get_image()
	if not image or image.is_empty():
		return
	var mask := BitMap.new()
	mask.create_from_image_alpha(image, 0.22)
	# Keep antialiased silhouette fringes available to the application underneath.
	mask.grow_mask(-3, Rect2i(Vector2i.ZERO, image.get_size()))
	var shapes := mask.opaque_to_polygons(Rect2i(Vector2i.ZERO, image.get_size()), 0.5)
	var biggest := PackedVector2Array()
	var largest := 0.0
	for shape in shapes:
		var area := 0.0
		for i in shape.size():
			area += shape[i].cross(shape[(i + 1) % shape.size()])
		if absf(area) > largest:
			largest = absf(area)
			biggest = shape
	if biggest.size() >= 3:
		# Contours use grid corners. Place vertices between integer pointer positions.
		for i in biggest.size():
			biggest[i] += Vector2(0.5, 0.5)
		outline = biggest
		get_window().mouse_passthrough_polygon = outline
		outline_dirty = false

func _head_at(local: Vector2) -> bool:
	var size_px := Vector2(get_window().size)
	return local.y < size_px.y * 0.48

func _input(event: InputEvent) -> void:
	if not ready_for_input:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			motion.press(desktop.pointer(), _head_at(event.position))
			# Maintain native capture when the pointer leaves the silhouette.
			get_window().mouse_passthrough_polygon = PackedVector2Array()
		elif motion.pressed:
			motion.release(desktop.pointer())
			get_window().mouse_passthrough_polygon = outline
			_feedback()
			_save()
	elif event is InputEventMouseMotion:
		if motion.pressed:
			var p := desktop.pointer()
			var next_screen := desktop.screen_at(p)
			if next_screen != screen_index:
				screen_index = next_screen
				motion.set_bounds(_bounds())
			motion.drag(p)
			_place()
		else:
			var over_head := _head_at(event.position) and Geometry2D.is_point_in_polygon(event.position, outline)
			if over_head and not entered_head:
				motion.pet()
				_feedback()
			entered_head = over_head
	elif event.is_action_pressed("ui_cancel"):
		if motion.pressed:
			_cancel_capture()
		else:
			get_tree().quit()

func _feedback() -> void:
	if motion.state == Motion.State.PETTED:
		var tween := create_tween()
		tween.tween_property($Fill, "light_energy", 1.25, 0.12)
		tween.tween_property($Fill, "light_energy", 0.55, 0.17)

func _cancel_capture() -> void:
	motion.cancel_input()
	get_window().mouse_passthrough_polygon = outline

func _save() -> void:
	var allowed := _bounds()
	prefs.screen = desktop.screen_key(screen_index)
	prefs.relative = (motion.position - allowed.position) / allowed.size.max(Vector2.ONE)
	if prefs.write() != OK:
		push_warning("无法保存桌宠偏好")

func _exit_tree() -> void:
	if ready_for_input:
		RenderingServer.frame_post_draw.disconnect(_refresh_outline)
		_save()

extends SceneTree

const Space = preload("res://desktop/desktop_space.gd")
const Motion = preload("res://core/companion_motion.gd")

class Displays extends Space:
	var backing_scale := 2.0
	var primary_origin := Vector2(2560, 400)

	func scale_factor() -> float:
		return backing_scale

	func origin() -> Vector2:
		return primary_origin

	func usable(index: int) -> Rect2:
		return Rect2(-1280, -200, 1280, 780) if index == 1 else Rect2(0, 32, 1440, 820)

var failures := 0

func check(condition: bool, label: String) -> void:
	if not condition:
		push_error(label)
		failures += 1

func _initialize() -> void:
	var displays := Displays.new()
	var negative := Vector2(-120, 250)
	for scale_value in [1.0, 2.0]:
		displays.backing_scale = scale_value
		var px: Vector2i = displays.pixel(negative)
		check(Vector2(px) == displays.primary_origin + negative * scale_value, "primary origin + backing scale")
		check(displays.point(px) == negative, "negative coordinate round trip")
	var motion := Motion.new()
	var size_pt := Vector2(224, 224)
	var foot := Vector2(112, 192)
	var allowed := displays.foot_bounds(1, size_pt, foot)
	motion.setup(allowed.get_center(), allowed, 14)
	var before := motion.position
	motion.set_bounds(displays.foot_bounds(1, size_pt * 1.5, foot * 1.5))
	check(motion.position == before, "resizing anchors foot")
	motion.press(before, false)
	motion.drag(before + Vector2(50, 10))
	motion.cancel_input()
	motion.set_bounds(displays.foot_bounds(0, size_pt, foot))
	var window := Rect2(motion.position - foot, size_pt)
	check(not motion.pressed and displays.usable(0).encloses(window), "removed display returns whole window to primary")
	print("desktop geometry test failures: ", failures)
	quit(1 if failures else 0)

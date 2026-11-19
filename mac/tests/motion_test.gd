extends SceneTree

const Motion = preload("res://core/companion_motion.gd")
var failures := 0

func check(condition: bool, label: String) -> void:
	if not condition:
		push_error(label)
		failures += 1

func scenario() -> RefCounted:
	var motion := Motion.new()
	motion.setup(Vector2(-90, 200), Rect2(-900, 0, 1800, 850), 42)
	return motion

func _initialize() -> void:
	var expected: Array[Vector2] = []
	for hz in [30, 60, 120]:
		var m = scenario()
		m.move_to(Vector2(240, 200))
		for second in range(12):
			for frame in range(hz):
				m.advance(1.0 / hz)
			if hz == 30:
				expected.append(m.position)
			else:
				check(m.position.distance_to(expected[second]) <= 1, "replay at %s Hz" % hz)
		var before: Vector2 = m.position
		m.advance(600.0)
		check(m.position == before, "wake must not teleport")
	var m = scenario()
	m.move_to(Vector2(40, 200))
	m.press(m.position, true)
	m.drag(Vector2(-2000, -100))
	check(m.position == Vector2(-900, 0) and m.state == Motion.State.HELD, "clamped drag")
	m.release(Vector2(-2000, -100))
	check(not m.pressed and m.state == Motion.State.IDLE and m.target == m.position, "drop cancels walk")
	m.press(m.position, true)
	m.release(m.position)
	check(m.state == Motion.State.PETTED, "short head tap")
	m.press(m.position, true)
	m.cancel_input()
	check(not m.pressed and m.state == Motion.State.IDLE, "focus loss releases input")
	m.set_bounds(Rect2(10, 10, 580, 380))
	check(m.position == Vector2(10, 10), "removed display")
	print("motion test failures: ", failures)
	quit(1 if failures else 0)

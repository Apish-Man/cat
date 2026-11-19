extends RefCounted
## Desktop positions are logical points. The host supplies time and all input.

enum State { IDLE, WALK, PETTED, HELD }
const STEP := 1.0 / 120.0
const SPEED := 94.0
const ACCELERATION := 290.0
const DRAG_THRESHOLD := 4.0

var state := State.IDLE
var position := Vector2.ZERO
var facing := 1
var speed := 0.0
var bounds := Rect2()
var target := Vector2.ZERO
var distance_walked := 0.0
var pressed := false
var _press_point := Vector2.ZERO
var _grab_offset := Vector2.ZERO
var _pressed_head := false
var _remaining := 1.0
var _carry := 0.0
var _rng := RandomNumberGenerator.new()

func setup(start: Vector2, allowed: Rect2, seed_value: int) -> void:
	_rng.seed = seed_value
	position = start
	set_bounds(allowed)
	_rest()

func set_bounds(allowed: Rect2) -> void:
	bounds = allowed
	position = position.clamp(bounds.position, bounds.end)
	target = target.clamp(bounds.position, bounds.end)

func _rest() -> void:
	state = State.IDLE
	speed = 0.0
	target = position
	_remaining = _rng.randf_range(1.5, 4.5)

func move_to(destination: Vector2) -> void:
	target = destination.clamp(bounds.position, bounds.end)
	state = State.WALK
	speed = 0.0

func press(pointer: Vector2, head: bool) -> void:
	pressed = true
	_press_point = pointer
	_grab_offset = position - pointer
	_pressed_head = head

func drag(pointer: Vector2) -> void:
	if not pressed:
		return
	if state != State.HELD and pointer.distance_to(_press_point) < DRAG_THRESHOLD:
		return
	state = State.HELD
	speed = 0.0
	position = (pointer + _grab_offset).clamp(bounds.position, bounds.end)

func release(pointer: Vector2) -> void:
	if not pressed:
		return
	drag(pointer)
	var tap := state != State.HELD and _pressed_head
	cancel_input()
	if tap:
		pet()

func cancel_input() -> void:
	pressed = false
	_carry = 0.0
	_rest()

func pet() -> void:
	if pressed or state == State.PETTED:
		return
	state = State.PETTED
	speed = 0.0
	target = position
	_remaining = 1.0

func advance(elapsed: float) -> void:
	if pressed or elapsed <= 0.0 or elapsed > 0.25:
		_carry = 0.0
		return
	_carry += elapsed
	while _carry + 0.000000001 >= STEP:
		_carry -= STEP
		_tick()

func _tick() -> void:
	if state != State.WALK:
		_remaining -= STEP
		if _remaining > 0.0:
			return
		if state == State.PETTED:
			_rest()
		else:
			move_to(position + Vector2(_rng.randf_range(-210, 210), _rng.randf_range(-45, 45)))
		return
	var remaining := position.distance_to(target)
	var brake_speed := sqrt(2.0 * ACCELERATION * remaining)
	speed = move_toward(speed, minf(SPEED, brake_speed), ACCELERATION * STEP)
	var previous := position
	position = position.move_toward(target, speed * STEP)
	distance_walked += previous.distance_to(position)
	if absf(target.x - previous.x) > 1.0:
		facing = 1 if target.x > previous.x else -1
	if position.is_equal_approx(target):
		_rest()

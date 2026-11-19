extends Node3D

@onready var tree: AnimationTree = $Tree
@onready var playback: AnimationNodeStateMachinePlayback = tree.get("parameters/playback")
var action := &"idle"

func _ready() -> void:
	tree.active = true
	playback.start(action)
	tree.advance(0.0)

func pose(next: StringName, speed_fraction: float, elapsed: float) -> void:
	if next != action:
		action = next
		playback.travel(action)
	var rate := clampf(speed_fraction, 0.2, 1.8) if action == &"walk" else 1.0
	tree.advance(minf(elapsed, 0.1) * rate)

# Interior of the head and torso shared by all four clips, in the 448 px reference view.
# Animated whiskers, tail and paws remain click-through along their moving edges.
const HIT_POINTS := [Vector2(111, 271), Vector2(127, 243), Vector2(162, 228),
	Vector2(211, 224), Vector2(223, 214), Vector2(224, 188), Vector2(240, 164),
	Vector2(264, 154), Vector2(292, 157), Vector2(311, 172), Vector2(324, 197),
	Vector2(322, 222), Vector2(311, 235), Vector2(316, 263), Vector2(313, 293),
	Vector2(292, 319), Vector2(259, 329), Vector2(207, 338), Vector2(165, 331),
	Vector2(130, 316), Vector2(113, 297)]

func hit_outline(extent: Vector2, facing: int) -> PackedVector2Array:
	var points := PackedVector2Array()
	for point: Vector2 in HIT_POINTS:
		if facing < 0:
			point.x = 448.0 - point.x
		points.append((point * extent / 448.0).floor() + Vector2(0.5, 0.5))
	return points

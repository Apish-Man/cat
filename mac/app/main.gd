extends Node3D

func _ready() -> void:
	get_viewport().transparent_bg = true
	Engine.max_fps = 30

func _unhandled_key_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		get_tree().quit()

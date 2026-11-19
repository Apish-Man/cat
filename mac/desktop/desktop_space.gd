extends RefCounted
## Godot macOS screen/window coordinates share a maximum backing scale.
## The core uses logical points relative to the top-left of the primary screen.

func scale_factor() -> float:
	return maxf(1.0, DisplayServer.screen_get_max_scale())

func origin() -> Vector2:
	return Vector2(DisplayServer.screen_get_position(DisplayServer.get_primary_screen()))

func point(pixel: Vector2) -> Vector2:
	return (pixel - origin()) / scale_factor()

func pixel(point_value: Vector2) -> Vector2i:
	return Vector2i((origin() + point_value * scale_factor()).round())

func pointer() -> Vector2:
	return point(DisplayServer.mouse_get_position())

func screen_at(location: Vector2) -> int:
	var index := DisplayServer.get_screen_from_rect(Rect2i(pixel(location), Vector2i.ONE))
	return index if index >= 0 else DisplayServer.get_primary_screen()

func usable(index: int) -> Rect2:
	var frame := DisplayServer.screen_get_usable_rect(index)
	return Rect2(point(frame.position), Vector2(frame.size) / scale_factor())

func foot_bounds(index: int, extent: Vector2, anchor: Vector2) -> Rect2:
	var area := usable(index)
	return Rect2(area.position + anchor, (area.size - extent).max(Vector2.ZERO))

func screen_key(index: int) -> String:
	# Geometry fingerprint; when a layout changes, resolve on the primary display.
	var rect := usable(index)
	return "%d,%d,%d,%d" % [roundi(rect.position.x), roundi(rect.position.y),
			roundi(rect.size.x), roundi(rect.size.y)]

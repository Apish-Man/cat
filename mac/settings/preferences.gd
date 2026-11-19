extends RefCounted

var path := "user://preview-preferences.cfg"
var writable := true
var scale_value := 1.0
var eco := false
var screen := ""
var relative := Vector2(0.75, 0.75)

func read() -> void:
	var config := ConfigFile.new()
	if not FileAccess.file_exists(path):
		return
	if config.load(path) != OK:
		var backup := "%s.broken-%d" % [path, Time.get_ticks_usec()]
		writable = DirAccess.rename_absolute(path, backup) == OK
		return
	if config.get_value("preview", "version", 0) != 1:
		writable = false
		return
	var size_value = config.get_value("preview", "scale", 1.0)
	if (size_value is float or size_value is int) and is_finite(float(size_value)):
		scale_value = clampf(float(size_value), 0.6, 1.5)
	var energy = config.get_value("preview", "eco", false)
	if energy is bool:
		eco = energy
	var saved_screen = config.get_value("preview", "screen", "")
	if saved_screen is String:
		screen = saved_screen
	var saved_position = config.get_value("preview", "position", relative)
	if saved_position is Vector2 and saved_position.is_finite():
		relative = saved_position.clamp(Vector2.ZERO, Vector2.ONE)

func write() -> Error:
	if not writable:
		return OK
	var config := ConfigFile.new()
	config.set_value("preview", "version", 1)
	config.set_value("preview", "scale", scale_value)
	config.set_value("preview", "eco", eco)
	config.set_value("preview", "screen", screen)
	config.set_value("preview", "position", relative)
	var temporary := "%s.%d.tmp" % [path, OS.get_process_id()]
	var err := config.save(temporary)
	return DirAccess.rename_absolute(temporary, path) if err == OK else err

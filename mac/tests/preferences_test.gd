extends SceneTree

const Prefs = preload("res://settings/preferences.gd")
var failures := 0

func check(condition: bool, label: String) -> void:
	if not condition:
		push_error(label)
		failures += 1

func _initialize() -> void:
	var folder := DirAccess.create_temp("catmate-prefs")
	if folder == null:
		push_error("Could not create test directory")
		quit(1)
		return
	var prefs := Prefs.new()
	prefs.path = folder.get_current_dir().path_join("prefs.cfg")
	prefs.eco = true
	prefs.relative = Vector2(0.85, 0.16)
	check(prefs.write() == OK, "atomic save")
	var loaded := Prefs.new()
	loaded.path = prefs.path
	loaded.read()
	check(loaded.eco and loaded.relative.is_equal_approx(prefs.relative), "restart round trip")
	var cfg := ConfigFile.new()
	cfg.set_value("preview", "version", 1)
	cfg.set_value("preview", "scale", 30)
	cfg.set_value("preview", "position", Vector2(-2, 5))
	cfg.save(prefs.path)
	loaded.read()
	check(loaded.scale_value == 1.5 and loaded.relative == Vector2(0, 1), "invalid ranges")
	cfg.set_value("preview", "version", 9)
	cfg.save(prefs.path)
	var original := FileAccess.get_file_as_bytes(prefs.path)
	loaded.read()
	loaded.write()
	check(FileAccess.get_file_as_bytes(prefs.path) == original, "preserve future schema")
	var broken := FileAccess.open(prefs.path, FileAccess.WRITE)
	broken.store_string("[invalid")
	broken.close()
	var recovered := Prefs.new()
	recovered.path = prefs.path
	recovered.read()
	check(recovered.writable and recovered.scale_value == 1.0, "recover corrupt file")
	check(not FileAccess.file_exists(prefs.path) and folder.get_files().size() == 1, "backup kept")
	print("preferences test failures: ", failures)
	quit(1 if failures else 0)

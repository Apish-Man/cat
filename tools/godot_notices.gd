extends SceneTree
## Extract the actual engine build's license and compiled-in third-party notices.
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		quit(1)
		return
	var file := FileAccess.open(args[0], FileAccess.WRITE)
	if file == null:
		quit(1)
		return
	file.store_string(Engine.get_license_text() + "\n\n")
	for component in Engine.get_copyright_info():
		file.store_line(component.name)
		for part in component.parts:
			for notice in part.copyright:
				file.store_line("  " + notice)
			file.store_line("  License: " + str(part.license))
	file.store_line("")
	var licenses := Engine.get_license_info()
	for key in licenses:
		file.store_line(key)
		file.store_line(licenses[key])
	file.close()
	quit()

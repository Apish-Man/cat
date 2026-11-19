# CatMate macOS 3D 预览

开发工具使用 Godot 4.7.2 标准版及同版本导出模板。以下命令在仓库根目录运行。`godot` 指向编辑器的可执行文件。

```sh
tools/build_macos.sh
file dist/mac/CatMate.app/Contents/MacOS/*
open dist/mac/CatMate.app
```

构建脚本从官方 universal 模板提取 arm64 架构，导出后核验应用签名。可通过 GODOT_BIN 指定编辑器路径，GODOT_MAC_TEMPLATE 指定官方 macos.zip。当前为本地 ad-hoc 签名。

点击小猫头部可触发反馈，按住身体拖动。菜单栏的猫图标提供找回、缩放、省电和退出。按 Esc 也可以退出。

运动与偏好测试可用 Godot 的 --headless --path mac --script 分别运行 res://tests/motion_test.gd 和 res://tests/preferences_test.gd。res://tests/desktop_test.gd 需要真实图形窗口，使用临时偏好目录。

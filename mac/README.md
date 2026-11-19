# CatMate macOS 3D 预览

开发工具使用 Godot 4.7.2 标准版及同版本导出模板。以下命令在仓库根目录运行。`godot` 指向编辑器的可执行文件。

```sh
mkdir -p dist/mac
godot --headless --path mac --import
godot --headless --path mac --export-release "macOS arm64" ../dist/mac/CatMate.app
file dist/mac/CatMate.app/Contents/MacOS/*
open dist/mac/CatMate.app
```

原型用正交相机显示有朝向的三维简模。点击窗口后按 Esc 退出。

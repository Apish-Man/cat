# CatMate macOS 3D 预览

开发工具使用 Godot 4.7.2 标准版及同版本导出模板。以下命令在仓库根目录运行。`godot` 指向编辑器的可执行文件。

```sh
tools/build_macos.sh
file dist/mac/CatMate.app/Contents/MacOS/*
open dist/mac/CatMate.app
```

构建脚本从官方 universal 模板提取 arm64 架构，导出后核验应用签名。可通过 GODOT_BIN 指定编辑器路径，GODOT_MAC_TEMPLATE 指定官方 macos.zip。当前为本地 ad-hoc 签名。

点击小猫头部可触发反馈，按住身体拖动。菜单栏的猫图标提供找回、缩放、省电和退出。按 Esc 也可以退出。

运动与偏好测试可用 Godot 的 --headless --path mac --script 分别运行 res://tests/motion_test.gd、res://tests/preferences_test.gd 和 res://tests/desktop_space_test.gd。res://tests/desktop_test.gd 需要真实图形窗口，使用临时偏好目录。

发布构建固定使用 Godot 4.7.2.stable.official.ed1daf0bf。维护者可核对官方发布包摘要后，将模板归档中的 `templates/macos.zip` 放在上述路径。

| 文件 | SHA-256 |
| --- | --- |
| Godot 编辑器 macOS universal ZIP | `c58a24e31d720be9d62f60cb5627c4e695fb72f21b0cfe1bc9ccaa9a3b3ba63e` |
| 同版本完整 export_templates.tpz | `f298490b8d44d934be425a5a65a51bf15f422428b229a06a6e11d9ffea248011` |

模型和动作的可编辑源文件见[内置橘猫](characters/golden/README.md)。构建脚本将引擎和依赖许可打入应用的 Contents/Resources/Godot-LICENSE.txt，再完成本地签名。

性能复测在开发机上执行 `GODOT_BIN=/path/to/Godot python3 tools/measure_macos.py`。它复制已导出的应用，使用相同的 release 二进制和角色资源，替换测试入口以固定待机或持续散步。空桌面、待机、散步各采样十分钟，原始 top 记录、进程能量和唤醒计数、帧间隔摘要保存至 build/macos-qa/performance。使用 `python3 tools/summarize_macos.py build/macos-qa/performance` 汇总。验收详情见[开发机验证记录](../docs/validation/macos-v1.3.0-alpha.1.md)。

在指定版本的干净检出中构建后，可在仓库根目录打包并核验 ZIP（终端使用 Bash 或 zsh）。

```sh
cd dist/mac
ditto -c -k --keepParent CatMate.app CatMate-v1.3.0-alpha.1-macos-arm64.zip
shasum -a 256 CatMate-v1.3.0-alpha.1-macos-arm64.zip > CatMate-v1.3.0-alpha.1-macos-arm64.zip.sha256
shasum -a 256 -c CatMate-v1.3.0-alpha.1-macos-arm64.zip.sha256
```

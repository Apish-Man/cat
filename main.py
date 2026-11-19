"""Source and packaged entry point, with a useful startup failure log."""
import os
import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    try:
        from catmate.app import main
        raise SystemExit(main())
    except Exception:
        detail = traceback.format_exc()
        directory = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CatMate"
        if "--data-dir" in sys.argv:
            index = sys.argv.index("--data-dir")
            if index + 1 < len(sys.argv):
                directory = Path(sys.argv[index + 1])
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "startup-error.log"
        path.write_text(detail, encoding="utf-8")
        if sys.stderr:
            sys.stderr.write(detail)
        if "--smoke-test" not in sys.argv and sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, f"小猫暂时没能启动。详细原因保存在：\n{path}", "猫在 · 启动失败", 0x10)
        raise SystemExit(1)

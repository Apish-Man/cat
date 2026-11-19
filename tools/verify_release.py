"""Exercise the packaged binary without Python/Qt on its PATH, in an isolated save."""
import json
import argparse
import os
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "CatMate" / "CatMate.exe"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=EXE)
    args = parser.parse_args()
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PATH"] = str(Path(env.get("WINDIR", r"C:\Windows")) / "System32")
    with tempfile.TemporaryDirectory() as directory:
        command = [str(args.exe), "--data-dir", directory]
        result = subprocess.run(command + ["--smoke-test"], env=env, timeout=30)
        error = Path(directory) / "startup-error.log"
        assert result.returncode == 0, error.read_text(encoding="utf-8") if error.exists() else result.returncode
        save = Path(directory) / "save.json"
        assert save.exists()
        data = json.loads(save.read_text(encoding="utf-8"))
        assert data["coins"] == 200
        log = Path(directory) / "catmate.log"
        assert not log.read_text(encoding="utf-8"), log.read_text(encoding="utf-8")
        # The new action costumes are runtime resources, not merely preview art.
        import hashlib
        resources = args.exe.parent / "_internal" / "assets"
        for excluded in ("cv2", "numpy", "PIL"):
            assert not (args.exe.parent/"_internal"/excluded).exists(), f"Offline tool leaked into runtime: {excluded}"
        for relative in [Path("pounces-atlas.png"), *[Path("dressed") / f"{name}.png" for name in
                          ("birthday", "blue", "daisy", "christmas", "newyear", "pig")],
                          *[Path("walk")/f"{name}.png" for name in ("bare", "birthday", "blue", "daisy", "christmas", "newyear", "pig")]]:
            assert hashlib.sha256((resources/relative).read_bytes()).digest() == hashlib.sha256((ROOT/"assets"/relative).read_bytes()).digest(), relative
        data["outfit"] = "blue"
        data["inventory"]["blue"] = 1
        data["settings"]["cursor_chase"] = True  # exercise dressed walking on the quiet boot.
        save.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        process = subprocess.Popen(command + ["--quiet"], env=env)
        try:
            deadline = time.monotonic() + 15
            initial_modified = save.stat().st_mtime_ns
            while save.stat().st_mtime_ns == initial_modified and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError("Packaged instance exited early")
                time.sleep(0.1)
            assert save.stat().st_mtime_ns != initial_modified
            # A second launch must signal the first, then exit without another pet.
            second = subprocess.run(command, env=env, timeout=10)
            assert second.returncode == 0
            assert process.poll() is None
            stop = subprocess.run(command + ["--quit"], env=env, timeout=10)
            assert stop.returncode == 0
            assert process.wait(timeout=10) == 0
            assert not log.read_text(encoding="utf-8")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
    print("PASS: standalone boot, clean log, save, clothed boot, bundled action resources, single instance, IPC quit, no Python/Qt on PATH")

if __name__ == "__main__":
    main()

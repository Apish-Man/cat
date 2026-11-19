"""Collect 10 minutes per phase on macOS. Requires a built dist/mac/CatMate.app.

The measurement copy uses the release binary and assets. A test-only main scene
holds the chosen activity and records frame intervals. Original app is untouched.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
GODOT = os.getenv("GODOT_BIN", "godot")
REPORT = ROOT / "build" / "macos-qa" / "performance"
SECONDS = 600


def run_benchmark():
    REPORT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="catmate-measure-") as folder:
        work = Path(folder)
        project = work / "mac"
        shutil.copytree(ROOT / "mac", project, ignore=shutil.ignore_patterns(".godot", ".DS_Store"))
        config = project / "project.godot"
        config.write_text(config.read_text().replace('run/main_scene="res://app/main.tscn"',
                                                    'run/main_scene="res://tests/residency_bench.tscn"'))
        preset = project / "export_presets.cfg"
        preset.write_text(preset.read_text().replace('exclude_filter="tests/*,characters/prototype/*"', 'exclude_filter=""'))
        app = work / "CatMate.app"
        subprocess.run(["ditto", ROOT / "dist/mac/CatMate.app", app], check=True)
        pack, = (app / "Contents/Resources").glob("*.pck")
        subprocess.run([GODOT, "--headless", "--path", project, "--import"], check=True)
        subprocess.run([GODOT, "--headless", "--path", project, "--export-pack", "macOS arm64", pack], check=True)
        subprocess.run(["codesign", "--force", "--sign", "-", app], check=True)
        binary, = (app / "Contents/MacOS").iterdir()
        smoke = work / "smoke.json"
        subprocess.run([binary, "--", "walk", "3", smoke], check=True, timeout=15)
        if json.loads(smoke.read_text())["distance_pt"] <= 0:
            raise RuntimeError("Release runtime did not walk")
        print("baseline", flush=True)
        with (REPORT / "baseline.top").open("w") as log:
            subprocess.run(["top", "-l", "61", "-s", "10", "-n", "0"], stdout=log, check=True)
        for mode in ("idle", "walk"):
            result = REPORT / (mode + ".json")
            print(mode, flush=True)
            with subprocess.Popen([binary, "--", mode, str(SECONDS + 5), result]) as pet:
                try:
                    time.sleep(1)
                    with (REPORT / (mode + ".top")).open("w") as log:
                        subprocess.run(["top", "-l", "61", "-s", "10", "-pid", str(pet.pid),
                                        "-stats", "pid,cpu,mem,power,idlew"], stdout=log, check=True)
                    if pet.wait(timeout=30) or json.loads(result.read_text())["mode"] != mode:
                        raise RuntimeError("Incomplete benchmark: " + mode)
                finally:
                    if pet.poll() is None:
                        pet.terminate()


if __name__ == "__main__":
    run_benchmark()

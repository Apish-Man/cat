"""Bounded real Qt event-loop measurements, always with an isolated save.

CPU is process time / wall time (100% = one logical CPU). Includes timer,
painting and mask work; memory uses Windows GetProcessMemoryInfo when present.
"""
import argparse
import ctypes
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def memory_mib():
    if os.name != "nt":
        return {}
    from ctypes import wintypes
    class COUNTERS(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
              "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]
    kernel = ctypes.WinDLL("kernel32")
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    counter = COUNTERS()
    counter.cb = ctypes.sizeof(counter)
    if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counter), counter.cb):
        return {"working_set_mib": round(counter.WorkingSetSize / 2**20, 2),
                "private_mib": round(counter.PrivateUsage / 2**20, 2)}
    return {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--include-eco", action="store_true")
    parser.add_argument("--actions-only", action="store_true")
    parser.add_argument("--walk-only", action="store_true")
    args = parser.parse_args()
    if not args.native:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QEventLoop, QPointF, QTimer
    from PySide6.QtWidgets import QApplication
    from catmate.app import Application
    from catmate.model import Store
    from catmate.pet import PetWindow, ToyWindow
    counts = {"pet_paints": 0, "toy_paints": 0, "ticks": 0, "mask_rebuilds": 0, "panel_refreshes": 0}
    paint_times = []
    def instrument(cls, name, counter, only_rebuild=False):
        original = getattr(cls, name)
        def wrapped(self, *a, **kw):
            if counter == "pet_paints":
                paint_times.append(time.perf_counter())
            before = getattr(self, "_mask_key", None)
            result = original(self, *a, **kw)
            if not only_rebuild or before != getattr(self, "_mask_key", None):
                counts[counter] += 1
            return result
        setattr(cls, name, wrapped)
    instrument(PetWindow, "paintEvent", "pet_paints")
    instrument(ToyWindow, "paintEvent", "toy_paints")
    instrument(PetWindow, "tick", "ticks")
    instrument(PetWindow, "update_mask", "mask_rebuilds", True)
    from catmate.ui import ControlCenter
    instrument(ControlCenter, "refresh", "panel_refreshes")
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    failures = []
    sys.excepthook = lambda kind, value, tb: failures.append(str(value))
    results = {"platform": app.platformName(), "cpu_basis": "one logical core", "logical_cpus": os.cpu_count(), "seconds_per_scenario": args.seconds, "scenarios": {}}
    with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
        runtime = Application(app, Store(directory), quiet=True)
        pet = runtime.pet
        runtime.model.d["settings"]["perch"] = False
        runtime.model.d["settings"]["cursor_chase"] = False
        pet.bubble = ""
        def settle(ms):
            loop = QEventLoop()
            QTimer.singleShot(ms, loop.quit)
            loop.exec()
        def sample(name, setup):
            setup()
            settle(300)
            for key in counts:
                counts[key] = 0
            paint_times.clear()
            cpu, wall = time.process_time(), time.perf_counter()
            settle(round(args.seconds * 1000))
            elapsed = time.perf_counter() - wall
            results["scenarios"][name] = {"wall_seconds": round(elapsed, 3),
                "cpu_percent_one_core": round((time.process_time() - cpu) / elapsed * 100, 3),
                **memory_mib(), **counts}
            gaps = sorted((b-a)*1000 for a, b in zip(paint_times, paint_times[1:]))
            if gaps:
                results["scenarios"][name].update({"paint_interval_p50_ms": round(gaps[len(gaps)//2], 3),
                    "paint_interval_p95_ms": round(gaps[int((len(gaps)-1)*.95)], 3),
                    "paint_interval_max_ms": round(max(gaps), 3)})
        def sleeping():
            pet.stop_play(silent=True)
            pet.paused = True
            pet.set_state("sleep", 600)
            if runtime._panel is not None:
                runtime._panel.hide()
        def walking():
            pet.paused = False
            pet.set_state("walk", 600)
            area = pet.available()
            pet.move_clamped(area.topLeft())
            pet.target = QPointF(area.right() - pet.width(), area.bottom() - pet.height())
            pet.speed = 55
        def laser():
            runtime.model.d["inventory"]["laser"] = 1
            pet.start_play("laser")
        def panel():
            pet.stop_play(silent=True)
            pet.paused = True
            pet.set_state("idle", 600)
            runtime.panel.show()
        if args.walk_only:
            sample("walking_hidden_panel", walking)
        elif args.actions_only:
            from unittest.mock import patch
            from types import SimpleNamespace
            from PySide6.QtCore import QPoint
            runtime.model.d["inventory"]["blue"] = 1
            runtime.model.equip("blue")
            sample("clothed_walking", walking)
            def wand():
                runtime.model.d["inventory"]["wand"] = 1
                pet.start_play("wand")
            cursor = SimpleNamespace(pos=lambda: QPoint(pet.x()+pet.width()//2+70, pet.y()+pet.height()-32))
            with patch("catmate.pet.QCursor", cursor):
                sample("clothed_wand_leaps", wand)
        else:
            sample("sleep_hidden_panel", sleeping)
            sample("walking_hidden_panel", walking)
            sample("laser_interaction", laser)
            sample("panel_visible", panel)
        if args.include_eco:
            runtime.model.d["settings"]["eco"] = True
            sample("eco_sleep_hidden_panel", sleeping)
            sample("eco_walking_hidden_panel", walking)
        results["errors"] = failures
        runtime.cleanup()
        runtime.pet.hide()
        if runtime._panel is not None:
            runtime._panel.hide()
        app.processEvents()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))
    assert not failures, failures

if __name__ == "__main__":
    main()

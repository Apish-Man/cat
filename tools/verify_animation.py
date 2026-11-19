"""Behavior, cache and rendering checks using an isolated Qt companion."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox
from catmate.app import Application
from catmate.art import animation_sample, blend_pixmaps
from catmate.catalog import ITEMS
from catmate.model import Store

def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    errors = []
    sys.excepthook = lambda kind, value, tb: errors.append(str(value))
    with tempfile.TemporaryDirectory() as directory:
        runtime = Application(app, Store(directory), quiet=True)
        assert runtime._panel is None
        runtime.pet.set_pet_size(168)
        runtime.pet.set_eco(True)
        runtime.locate_pet()
        assert runtime._panel is None, "Right-click settings/locate must not create the control center"
        runtime.pet.set_eco(False)
        runtime.pet.set_pet_size(240)
        pet, panel, model = runtime.pet, runtime.panel, runtime.model
        runtime.clock.stop()
        runtime.autosave.stop()
        pet.timer.stop()
        # Hidden and minimized control windows do not keep updating inventories.
        assert not panel.refresh_timer.isActive()
        panel.show()
        app.processEvents()
        assert panel.refresh_timer.isActive()
        panel.hide()
        assert not panel.refresh_timer.isActive()
        # Size presets are exposed where the user actually interacts with the cat.
        for percent in (50, 100, 175):
            pet.set_pet_size(round(percent*240/100))
            assert pet.width() == round(percent*240/100)+32
            assert panel.size_label.text() == f"{percent}%"
        pet.set_pet_size(240)
        model.d["apps"] = [{"name": "Test App", "path": r"E:\Some Folder\Example.exe"}]
        menu = pet.create_context_menu()
        shortcut = next(a.menu() for a in menu.actions() if a.text() == "快捷启动")
        with patch("catmate.pet.launch_app") as launch:
            next(a for a in shortcut.actions() if a.text() == "Test App").trigger()
            launch.assert_called_once_with(r"E:\Some Folder\Example.exe")
        size_menu = next(a.menu() for a in menu.actions() if a.text().startswith("猫咪大小"))
        next(a for a in size_menu.actions() if a.text() == "70%").trigger()
        assert model.d["settings"]["size"] == 168
        next(a for a in menu.actions() if a.text() == "省电模式").setChecked(True)
        assert model.d["settings"]["eco"]
        assert panel.findChild(QCheckBox, "setting_eco").isChecked()
        pet.set_eco(False)
        pet.set_pet_size(240)
        pet.paused = False
        for key in ("yarn", "wand", "laser"):
            model.d["inventory"][key] = 1
        area = pet.available()
        pet.move_clamped(QPoint(area.left()+50, area.bottom()-pet.height()))
        now = time.monotonic()
        cursor = SimpleNamespace(pos=lambda: QPoint(pet.x()+pet.width()//2+80, area.bottom()-32))
        # Wand: committed leaps have a real raised apex, landing and anticipation.
        traces, heights = set(), []
        with patch("catmate.pet.QCursor", cursor):
            pet.start_play("wand")
            for i in range(240):
                pet._tick_wand(1/60, now+i/60)
                traces.add(pet.state)
                heights.append(pet.y())
        assert {"crouch", "pounce", "land"} <= traces, traces
        assert max(heights)-min(heights) > 25
        assert pet.carry_ball_until == 0
        pet.stop_play()
        # Laser: stalk/tap/search, never retrieval or the wand's jumping routine.
        traces = set()
        cursor = SimpleNamespace(pos=lambda: QPoint(pet.x()+pet.width()//2, pet.y()+pet.height()-32))
        with patch("catmate.pet.QCursor", cursor):
            pet.start_play("laser")
            for i in range(160):
                pet._tick_laser(1/60, now+i/60)
                traces.add(pet.state)
        assert {"bat", "search"} <= traces, traces
        assert "pounce" not in traces and pet._jump is None
        assert pet.carry_ball_until == 0
        pet.stop_play()
        # Yarn alone can be picked up, and it chooses an escape destination.
        pet.start_play("yarn")
        pet.target = QPointF(pet.x(), pet.y())
        pet.motion.reset()
        with patch("catmate.pet.random.random", return_value=.1):
            pet.move_towards(1/60)
        assert pet.carry_ball_until > 0 and pet.target is not None
        pet.stop_play()
        assert animation_sample("play", 0, gait_phase=0) != animation_sample("play", .2, gait_phase=0)
        # A pose change briefly blends, then releases its snapshot and drops FPS.
        pet.set_state("sleep", 90)
        assert pet._transition_from is not None
        pet._transition_started -= 1
        pet.paused = True
        pet.tick()
        assert pet._transition_from is None and pet.timer.interval() == 125
        model.d["settings"]["eco"] = True
        pet._set_rate()
        assert pet.timer.interval() == 500
        model.d["settings"]["eco"] = False
        # Native mouse mask stays stable across walking frames, not 60 rebuilds/s.
        pet.bubble = ""
        pet.hovered = False
        pet.set_state("walk", 90)
        pet._transition_from = None
        pet._transition_region = type(pet._transition_region)()
        pet.update_mask(0)
        key, mask = pet._mask_key, pet.mask()
        for elapsed in (.1, .2, .35, .6):
            pet.update_mask(elapsed)
            assert pet._mask_key == key and pet.mask() == mask
        assert not mask.contains(QPoint(0, 0))
        # Premultiplied blends must preserve opaque fur, rather than fading body.
        a, b = QPixmap(8, 8), QPixmap(8, 8)
        a.fill(QColor("#e8ae72")); b.fill(QColor("#d99c61"))
        # Integer premultiplication can round by one alpha level, but overlapping
        # fur must never fade to 75% as an ordinary SourceOver dissolve does.
        assert blend_pixmaps(a, b, .5).toImage().pixelColor(4, 4).alpha() >= 254
        # Inspect every dressed action sheet, not just the front thumbnails.
        outfits = [k for k, value in ITEMS.items() if value["kind"] == "outfit"]
        poses = ["idle", "walk", "sleep", "stretch", "groom", "carried", "eat"]
        contact = QPixmap(1260, 1200)
        contact.fill(QColor("#d5ded5"))
        p = QPainter(contact)
        for row, outfit in enumerate(outfits):
            for col, state in enumerate(poses):
                rect = QRectF(col*180+10, row*200+16, 160, 160)
                runtime.art.draw(p, rect, state, 0, outfit=outfit)
                p.setPen(QColor("#475145"))
                p.drawText(QRectF(col*180, row*200+177, 180, 22), Qt.AlignmentFlag.AlignCenter, f"{outfit} / {state}")
            # All sixteen source poses must exist and decode with nonempty alpha.
            cells = runtime.art._cells(outfit)
            assert len(cells) == 16 and all(not pix.mask().isNull() for pix in cells)
        p.end()
        output = ROOT/"docs"/"previews"
        output.mkdir(exist_ok=True, parents=True)
        contact.save(str(output/"costume-actions.png"))
        # Size/outfit churn cannot create an ever-growing texture/mask cache.
        for side in (140, 240, 420):
            for index in range(16):
                runtime.art._pose(index, "blue", side)
                assert runtime.art.cache_bytes <= runtime.art.CACHE_LIMIT
        runtime.cleanup()
        pet.hide()
        panel.hide()
        assert not errors, errors
    print(json.dumps({"result": "PASS", "checks": ["hidden panel timer", "size presets", "right-click launch", "wand leap/landing", "laser tap/search", "yarn retrieval", "transition/eco FPS", "stable input mask", "opaque blends", "96 clothed poses", "bounded cache"]}))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.__excepthook__(*sys.exc_info())
        raise SystemExit(1)

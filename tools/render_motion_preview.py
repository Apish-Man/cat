"""Render a short deterministic preview from the real movement/game renderer."""
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication
from catmate.art import Art, load_system_fonts
from catmate.model import Companion, Store
from catmate.motion import Locomotion
from catmate.pet import PetWindow

def main():
    app = QApplication([])
    load_system_fonts()
    art = Art()
    output = ROOT/"build"/"motion-preview-frames"
    output.mkdir(parents=True, exist_ok=True)
    move = Locomotion()
    x, gait = 35.0, 0.0
    with tempfile.TemporaryDirectory(dir=ROOT/"build") as directory:
        model = Companion(Store(directory))
        model.d["inventory"]["wand"] = 1
        pet = PetWindow(model, art)
        pet.timer.stop()
        area = pet.available()
        pet.move_clamped(QPoint(area.left()+30, area.bottom()-pet.height()))
        cursor = SimpleNamespace(pos=lambda: QPoint(area.left()+360, area.bottom()-32))
        start = time.monotonic()
        with patch("catmate.pet.QCursor", cursor):
            pet.start_play("wand")
            for frame in range(150):
                t = frame/30
                step = move.advance(x, 0, 450, 0, 130, 1/30, (0, 0, 520, 0))
                x = step.x
                gait += step.distance/58
                pet._tick_wand(1/30, start+t)
                scene = QPixmap(700, 440)
                scene.fill(QColor("#f3eee4"))
                p = QPainter(scene)
                p.setPen(QColor("#6b7459"))
                p.drawText(20, 25, "距离驱动步态 · 平滑起步 / 停靠")
                art.draw(p, QRectF(x, 40, 150, 150), "idle" if step.arrived else "walk", t,
                         outfit="blue", gait_phase=gait)
                p.drawText(20, 240, "逗猫棒 · 蹲伏 / 扑跳 / 落地缓冲")
                position_x = 30 + (pet.x()-area.left())*.7
                position_y = 270 + (pet.y()-(area.bottom()-pet.height()))*.7
                art.draw(p, QRectF(position_x, position_y, 150, 150), pet.state,
                         t % .6, gait_phase=pet.gait_phase)
                p.end()
                scene.save(str(output/f"{frame:03d}.png"))
        pet.toy.hide()
    print(output)

if __name__ == "__main__":
    main()

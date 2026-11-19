"""Regression for walking double exposure; render phase samples for review."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication
from catmate.animation import Art, animation_sample, load_system_fonts
from catmate.model import Store, Companion
from catmate.pet import PetWindow

def main():
    app = QApplication([])
    load_system_fonts()
    art = Art()
    image = QPixmap(1440, 600)
    image.fill(QColor("#d5ded5"))
    p = QPainter(image)
    for outfit in ("", "blue"):
        for step in range(6):
            phase = step/24
            a, b, weight = animation_sample("walk", 0, phase)
            assert a == b and weight == 0
            with patch("catmate.animation.blend_pixmaps", side_effect=AssertionError("Walking must not blend photographs")):
                art.draw(p, QRectF(step*240+10, 30 if not outfit else 330, 220, 220),
                         "walk", 0, outfit=outfit, gait_phase=phase)
            p.setPen(QColor("#40513d"))
            p.drawText(QRectF(step*240, 265 if not outfit else 565, 240, 22), Qt.AlignmentFlag.AlignCenter, f"{outfit or 'bare'}  frame {step}")
    p.end()
    image.save(str(ROOT/"docs"/"previews"/"walk-clear-phases.png"))
    with tempfile.TemporaryDirectory() as directory:
        pet = PetWindow(Companion(Store(directory)), art)
        pet.show()
        pet.timer.stop()
        pet.set_state("walk", 60)
        assert pet._transition_from is None
        pet._set_facing(-1)
        assert pet._transition_from is None
        # Even a manually stale snapshot may never be used when walking.
        pet._begin_transition()
        assert pet._transition_from is None
        for i in range(48):
            pet.gait_phase = i/48
            pix = QPixmap(pet.size())
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            with patch("catmate.pet.blend_pixmaps", side_effect=AssertionError("Walking may not leave a silhouette snapshot")):
                pet._render_sprite(painter, pet.state_start+i/60)
            painter.end()
        pet.set_state("idle", 10)
        assert pet._transition_from is None
        pet.timer.stop()
        pet.hide()
    assert art.cache_bytes <= art.CACHE_LIMIT
    for outfit in ("", "birthday", "blue", "daisy", "christmas", "newyear", "pig"):
        art._pose(17, outfit, 180)
        assert art._walk_outfit == (outfit or "bare")
        assert len(art._walk_frames) == 24
    assert "cv2" not in sys.modules and "numpy" not in sys.modules, "Flow computation must stay out of the desktop runtime"
    print("PASS: every walking phase is one complete frame; no photo blend, no turn/start/stop snapshot; bounded cache")

if __name__ == "__main__":
    main()

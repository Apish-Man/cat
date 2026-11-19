"""Integration checks against Qt widgets and render previews; uses a separate save."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtTest import QTest
from catmate.app import Application
from catmate.model import Store

def main():
    qt = QApplication([])
    qt.setQuitOnLastWindowClosed(False)
    errors = []
    sys.excepthook = lambda kind, value, tb: errors.append(str(value))
    temp = tempfile.TemporaryDirectory()
    runtime = Application(qt, Store(temp.name))
    p, m, pet = runtime.panel, runtime.model, runtime.pet
    runtime.clock.stop()
    runtime.autosave.stop()
    pet.timer.stop()
    p.refresh_timer.stop()
    qt.processEvents()
    output = ROOT / "docs" / "previews"
    output.mkdir(parents=True, exist_ok=True)
    def click(name):
        widget = p.findChild(QPushButton, name)
        assert widget is not None, name
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
        qt.processEvents()
    p.grab().save(str(output / "home.png"))
    click("nav1")
    click("use_fish")
    assert m.d["inventory"]["fish"] == 2
    assert pet.state == "eat"
    click("buy_fish")
    assert m.d["coins"] == 188
    assert m.d["inventory"]["fish"] == 3
    click("nav3")
    click("buy_blue")
    click("use_blue")
    assert m.d["outfit"] == "blue"
    assert m.d["coins"] == 88
    p.grab().save(str(output / "wardrobe.png"))
    click("nav4")
    click("startWork")
    for _ in range(60):
        m.tick(1)
    p.refresh()
    assert m.d["coins"] == 90
    click("startFocus")
    assert pet.paused and pet.state == "sleep"
    click("startFocus")
    assert m.focus_paused
    click("cancelFocus")
    assert not m.focus_remaining and not pet.paused
    p.grab().save(str(output / "work.png"))
    click("nav2")
    click("use_yarn")
    assert pet.mode == "yarn"
    assert pet.toy.isVisible()
    pet.throw_ball(pet.pos() + QPoint(200, 100))
    for _ in range(120):
        pet.update_toy(1/30, 0)
    assert pet.ball.y() <= pet.ball_ground
    pet.stop_play()
    assert not pet.toy.isVisible()
    # A target at the monitor edge must remain reachable after window clamping.
    from PySide6.QtCore import QPointF
    from unittest.mock import patch
    pet.start_play("yarn")
    area = pet.available()
    pet.ball = QPointF(area.right() - 18, area.bottom() - 18)
    pet.ball_velocity = QPointF(0, 0)
    pet.ball_ground = area.bottom() - 18
    pet.until = 0
    with patch("catmate.pet.IS_WINDOWS", False):
        pet.tick()
    assert pet.target.x() <= area.right() - pet.width() + 1
    assert pet.target.y() <= area.bottom() - pet.height() + 1
    # The cat must sometimes take the ball away instead of returning it.
    pet.move_clamped(QPoint(round(pet.target.x()), round(pet.target.y())))
    with patch("catmate.pet.random.random", return_value=0.1):
        pet.move_towards(0.033)
    assert pet.carry_ball_until > 0
    pet.stop_play()
    p.show()
    for page in range(7):
        p.navigate(page)
        qt.processEvents()
        assert p.stack.currentIndex() == page
    # Real alpha limits mouse interception to the animal and visible bubble.
    pet.hovered = False
    pet.bubble = ""
    pet.set_state("idle", 10)
    pet.update_mask(0)
    assert not pet.mask().contains(QPoint(0, 0))
    assert pet.mask().contains(QPoint(pet.width() // 2, int(pet.height() * 0.6)))
    # Side-by-side state atlas on a neutral desktop-colored backdrop for visual QA.
    canvas = QPixmap(1000, 700)
    canvas.fill(QColor("#d5ded5"))
    from PySide6.QtCore import QRectF
    painter = QPainter(canvas)
    states = ["idle", "walk", "sleep", "groom", "stretch", "carried", "pet", "crouch"]
    for i, state in enumerate(states):
        x, y = (i % 4) * 250, (i // 4) * 350
        runtime.art.draw(painter, QRectF(x + 10, y + 30, 230, 270), state, 0)
        painter.setPen(QColor("#4d554a"))
        painter.drawText(QRectF(x, y + 310, 250, 30), Qt.AlignmentFlag.AlignCenter, state)
    painter.end()
    canvas.save(str(output / "states.png"))
    runtime.persist()
    reloaded = Store(temp.name)
    assert reloaded.data["coins"] == 90
    assert reloaded.data["outfit"] == "blue"
    assert reloaded.data["inventory"]["fish"] == 3
    assert not errors, errors
    runtime.cleanup()
    runtime.pet.hide()
    runtime.panel.hide()
    runtime.tray.hide()
    print(json.dumps({"result": "PASS", "checks": ["navigation", "feeding", "purchase", "outfit", "work rewards", "focus pause/cancel", "toy physics", "hit mask", "save/reload"], "previews": str(output)}, ensure_ascii=False))
    temp.cleanup()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

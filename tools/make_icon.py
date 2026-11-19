import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from PySide6.QtWidgets import QApplication
from catmate.art import Art
app = QApplication([])
art = Art()
if not art.thumbnail(size=256).save(str(root / "assets" / "catmate.ico"), "ICO"):
    raise RuntimeError("ICO writer not available")
print("assets/catmate.ico ready")

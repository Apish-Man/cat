# Build with: .venv\Scripts\python -m PyInstaller --noconfirm CatMate.spec
from pathlib import Path
root = Path(SPECPATH)
a = Analysis(
    [str(root / 'main.py')], pathex=[str(root)], binaries=[],
    datas=[(str(root / 'assets'), 'assets')], hiddenimports=[], hookspath=[], hooksconfig={},
    excludes=['PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtWebEngineCore', 'tkinter', 'unittest', 'cv2', 'numpy', 'PIL'],
    noarchive=False,
)
# Qt 6.12 on Windows imports the OS ICU API with unversioned exports. An
# unrelated ICU 78 library on this machine's PATH has versioned exports;
# PyInstaller's resolver can mistakenly collect it under the same DLL name.
# Let Windows resolve its own ICU implementation instead of shipping that DLL.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {'icuuc.dll', 'icudt78.dll'}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CatMate',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / 'assets' / 'catmate.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CatMate')

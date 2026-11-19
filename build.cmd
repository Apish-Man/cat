@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tools\make_icon.py
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm CatMate.spec
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tools\package_release.py
if errorlevel 1 exit /b 1
echo Built: dist\CatMate\CatMate.exe

@echo off
cd /d "%~dp0"
if exist "dist\CatMate\CatMate.exe" (
    start "" "dist\CatMate\CatMate.exe"
    exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "main.py"
    exit /b
)
echo Please run setup.cmd first.
pause

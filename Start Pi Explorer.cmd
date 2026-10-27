@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run Setup Pi Explorer.cmd first. Python 3.12 is required.
  pause
  exit /b 1
)
start "Pi Explorer" /b "%~dp0.venv\Scripts\pythonw.exe" "%~dp0server.py"

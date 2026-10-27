@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe benchmarks\scan_speed.py --quick
pause

@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 goto path_error
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\source_launcher.ps1" -Action setup
set "launcher_result=%errorlevel%"
popd
if not "%launcher_result%"=="0" echo Pi Explorer failed. Read the error above.
pause
exit /b %launcher_result%
:path_error
echo Cannot open the app folder. Extract the complete ZIP to a writable folder first.
pause
exit /b 1

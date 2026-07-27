@echo off
REM Double-click or run from cmd: build Clarence for Windows
cd /d "%~dp0\.."
powershell -ExecutionPolicy Bypass -File "%~dp0build_standalone_app_windows.ps1"
if errorlevel 1 pause

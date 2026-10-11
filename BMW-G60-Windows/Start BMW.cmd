@echo off
cd /d "%~dp0"
"runtime\python\python.exe" -u "app\scripts\portable_server.py"
if errorlevel 1 pause

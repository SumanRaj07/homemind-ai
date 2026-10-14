@echo off
REM Start the HomeMind AI backend (loopback only).
cd /d "%~dp0\.."
python -m homemind.api.app

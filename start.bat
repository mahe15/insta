@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m cliper bot %*
) else (
    python -m cliper bot %*
)

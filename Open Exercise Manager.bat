@echo off
setlocal
set "APP_DIR=%~dp0"
set "PYW=%APP_DIR%myenv\Scripts\pythonw.exe"
set "APP=%APP_DIR%exercise_manager.py"

if not exist "%PYW%" (
    echo Could not find virtual environment launcher:
    echo %PYW%
    echo Recreate your venv, then try again.
    pause
    exit /b 1
)

start "Exercise Manager" "%PYW%" "%APP%"
exit /b 0

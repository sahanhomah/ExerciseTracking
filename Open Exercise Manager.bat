@echo off
setlocal
set "APP_DIR=%~dp0"
set "VENV_DIR=%APP_DIR%.venv"
set "PYW=%VENV_DIR%\Scripts\pythonw.exe"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "APP=%APP_DIR%exercise_manager.py"

if not exist "%PYW%" (
    if exist "%PY%" (
        set "PYW=%PY%"
    )
)

if not exist "%PYW%" (
    echo Could not find virtual environment launcher:
    echo %PYW%
    echo Recreate your venv, then try again.
    pause
    exit /b 1
)

start "Exercise Manager" "%PYW%" "%APP%"
exit /b 0

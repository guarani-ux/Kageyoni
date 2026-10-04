@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "PYTHONPATH=%SCRIPT_DIR%"
chcp 65001 >nul

set "PYTHON_EXE=python"
if exist "C:\Users\flowe\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=C:\Users\flowe\AppData\Local\Programs\Python\Python313\python.exe"
)

if "%~1"=="" (
    "%PYTHON_EXE%" "%SCRIPT_DIR%\constellation_emergence_cli.py" --run --auto
) else (
    "%PYTHON_EXE%" "%SCRIPT_DIR%\constellation_emergence_cli.py" %*
)

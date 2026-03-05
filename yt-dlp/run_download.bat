@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_download.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  PowerShell exited with error code %ERRORLEVEL%
    pause
)

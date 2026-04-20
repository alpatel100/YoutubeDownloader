@echo off
:: ============================================================
::  YouTube Clip Downloader - UI Launcher
::  Put a shortcut to this file on your Desktop.
::  Double-click to open the popup UI — no console window.
:: ============================================================

cd /d "%~dp0"

:: ── try pythonw first (no console window) ───────────────────
where pythonw >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" pythonw "%~dp0downloader_ui.pyw"
    exit /b 0
)

:: ── fall back to python if pythonw is missing ────────────────
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" python "%~dp0downloader_ui.pyw"
    exit /b 0
)

:: ── neither found ────────────────────────────────────────────
echo.
echo  ERROR: Python not found.
echo  Install Python from https://www.python.org and make sure
echo  "Add Python to PATH" is checked during installation.
echo.
pause

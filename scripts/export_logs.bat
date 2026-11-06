@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
    echo [XX] Windows PowerShell not found on this machine.
    pause
    exit /b 1
)

echo Exporting logs, please wait...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0export_logs.ps1" %*
echo.
pause
@echo off
setlocal
cd /d "%~dp0"
title RiG++ PixelLab - Verified GitHub Publisher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PUBLISH_TO_GITHUB.ps1"
if errorlevel 1 (
  echo.
  echo Upload stopped. See the error above.
  pause
  exit /b 1
)
echo.
echo Published. Press any key to close.
pause

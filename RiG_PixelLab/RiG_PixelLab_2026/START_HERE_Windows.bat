@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title RiG++ PixelLab Windows Starter

echo =============================================
echo  RiG++ PIXEL LAB - Windows
 echo =============================================
 echo.
set "PYTHON_BIN="
if exist "%USERPROFILE%\anaconda3\python.exe" set "PYTHON_BIN=%USERPROFILE%\anaconda3\python.exe"
if not defined PYTHON_BIN if exist "%USERPROFILE%\miniconda3\python.exe" set "PYTHON_BIN=%USERPROFILE%\miniconda3\python.exe"
if not defined PYTHON_BIN for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYTHON_BIN set "PYTHON_BIN=%%P"
if not defined PYTHON_BIN (
 echo Python was not found.
 echo Please install Python and run this file again.
 goto :failed
)

echo [1/3] Using existing Python:
"%PYTHON_BIN%" --version
if errorlevel 1 goto :failed

if not exist ".venv\Scripts\python.exe" (
 echo [2/3] Creating a project-only environment...
 "%PYTHON_BIN%" -m venv ".venv"
 if errorlevel 1 goto :failed
) else (
 echo [2/3] Reusing project-only environment.
)

".venv\Scripts\python.exe" -c "import PIL" >nul 2>&1
if errorlevel 1 (
 echo [3/3] Installing image package and optional drag and drop...
 ".venv\Scripts\python.exe" -m pip install -r requirements.txt
 if errorlevel 1 (
  echo Optional drag-and-drop install may have failed. Trying Pillow alone...
  ".venv\Scripts\python.exe" -m pip install "Pillow>=11,<14"
  if errorlevel 1 goto :failed
 )
) else (
 echo [3/3] Pillow is installed.
 ".venv\Scripts\python.exe" -c "import tkinterdnd2" >nul 2>&1
 if errorlevel 1 (
  echo Installing optional drag-and-drop support...
  ".venv\Scripts\python.exe" -m pip install "tkinterdnd2>=0.6,<1.0"
 )
)

echo.
echo Opening GUI...
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo ERROR: Startup failed. Please copy or screenshot the error above.
pause
exit /b 1

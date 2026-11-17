@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem Builds ND_Launcher.exe on your computer.
rem Requires regular Python 3.10+ from python.org (not the ComfyUI python_embeded).
rem Build dependencies are installed in .build_venv and do not modify system Python.

set "SYS_PY="
where py >nul 2>nul && set "SYS_PY=py -3"
if not defined SYS_PY where python >nul 2>nul && set "SYS_PY=python"
if not defined SYS_PY goto no_python
%SYS_PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto no_python

if not exist ".build_venv\Scripts\python.exe" (
    echo [ND] Creating the .build_venv build environment...
    %SYS_PY% -m venv .build_venv
    if errorlevel 1 goto fail
)

set "PY=.build_venv\Scripts\python.exe"
echo [ND] Installing dependencies from requirements.txt (the first run may take a few minutes)...
"%PY%" -m pip install --disable-pip-version-check -q --upgrade -r requirements.txt
if errorlevel 1 goto fail

if not exist "brand\links.json" echo [ND] brand\links.json is missing; custom links will not be embedded.
if not exist "brand\example.png" echo [ND] brand\example.png is missing; replacement of input\example.png will not work.

echo [ND] Downloading link icons...
"%PY%" nd_launcher.py --fetch-icons
"%PY%" tools\make_version_info.py

echo [ND] Building the EXE...
"%PY%" -m PyInstaller --noconfirm --clean --log-level WARN --onefile --windowed --name ND_Launcher --icon nd_icon.ico --version-file version_info.txt --noupx --add-data "brand;brand" --hidden-import nd_i18n nd_launcher.py
if errorlevel 1 goto fail

echo.
echo [ND] Done: %~dp0dist\ND_Launcher.exe
echo [ND] Place ND_Launcher.exe in the root of your portable ComfyUI installation, next to python_embeded and ComfyUI.
explorer "%~dp0dist"
pause
exit /b 0

:no_python
echo [ND] Python 3.10 or newer was not found.
echo [ND] Install Python from https://www.python.org/downloads/windows/
echo [ND] Enable "Add python.exe to PATH" in the installer, then run this file again.
pause
exit /b 1

:fail
echo.
echo [ND] Build failed. Check the messages above. Internet access is required to install packages.
pause
exit /b 1

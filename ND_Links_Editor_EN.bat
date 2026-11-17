@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Link editor for build authors. Edits brand\links.json, which build_exe.bat bundles into the EXE.
where py >nul 2>nul
if %errorlevel%==0 (set "SYS_PY=py -3") else (set "SYS_PY=python")
%SYS_PY% -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo [ND] Installing PySide6...
    %SYS_PY% -m pip install PySide6-Essentials
    if errorlevel 1 (
        echo [ND] Python 3.10+ from python.org must be installed.
        pause
        exit /b 1
    )
)
%SYS_PY% nd_launcher.py --edit-links

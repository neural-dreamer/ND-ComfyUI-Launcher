@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Редактор ссылок для автора сборки. Правит brand\links.json, который build_exe.bat зашивает в .exe.

where py >nul 2>nul
if %errorlevel%==0 (set "SYS_PY=py -3") else (set "SYS_PY=python")

%SYS_PY% -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo [ND] Ставлю PySide6...
    %SYS_PY% -m pip install PySide6-Essentials
    if errorlevel 1 (
        echo [ND] Нужен установленный Python 3.10+ с python.org.
        pause
        exit /b 1
    )
)

%SYS_PY% nd_launcher.py --edit-links

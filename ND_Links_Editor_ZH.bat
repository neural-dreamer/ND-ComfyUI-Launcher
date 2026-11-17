@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 供构建作者使用的链接编辑器。修改 brand\links.json，构建时会将其打包进 EXE。
where py >nul 2>nul
if %errorlevel%==0 (set "SYS_PY=py -3") else (set "SYS_PY=python")
%SYS_PY% -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo [ND] 正在安装 PySide6...
    %SYS_PY% -m pip install PySide6-Essentials
    if errorlevel 1 (
        echo [ND] 需要安装来自 python.org 的 Python 3.10 或更高版本。
        pause
        exit /b 1
    )
)
%SYS_PY% nd_launcher.py --edit-links

@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python_embeded\python.exe"

if not exist "%PY%" (
    echo [ND] Не найден python_embeded. Положи лаунчер в корень портативной сборки ComfyUI.
    pause
    exit /b 1
)

"%PY%" -s -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo [ND] Первый запуск: ставлю PySide6 в python_embeded...
    "%PY%" -s -m pip install PySide6-Essentials
    if errorlevel 1 (
        echo [ND] Не удалось установить PySide6. Проверь интернет и попробуй ещё раз.
        pause
        exit /b 1
    )
)

start "" "python_embeded\pythonw.exe" -s "%~dp0nd_launcher.py"

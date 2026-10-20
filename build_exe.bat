@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Собирает ND_Launcher.exe через системный Python 3.10+ (не python_embeded).
rem Папка brand (ссылки, иконки, логотип example.png) зашивается внутрь .exe.

where py >nul 2>nul
if %errorlevel%==0 (set "SYS_PY=py -3") else (set "SYS_PY=python")

%SYS_PY% -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo [ND] Не удалось поставить PyInstaller. Нужен установленный Python с python.org.
    pause
    exit /b 1
)

choice /C YN /M "[ND] Открыть редактор ссылок перед сборкой"
if errorlevel 2 goto build
%SYS_PY% nd_launcher.py --edit-links

:build
if not exist "brand\links.json" (
    echo [ND] Нет brand\links.json — ссылки не будут зашиты.
)
if not exist "brand\example.png" (
    echo [ND] Нет brand\example.png — замена input\example.png работать не будет.
)
echo [ND] Проверяю иконки ссылок...
%SYS_PY% nd_launcher.py --fetch-icons

%SYS_PY% tools\make_version_info.py
%SYS_PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name ND_Launcher --icon nd_icon.ico --version-file version_info.txt --noupx --add-data "brand;brand" --hidden-import nd_i18n nd_launcher.py
if errorlevel 1 (
    echo [ND] Сборка не удалась, смотри лог выше.
    pause
    exit /b 1
)

echo.
echo [ND] Готово: dist\ND_Launcher.exe
echo [ND] Ссылки, иконки и логотип зашиты внутрь. Положи exe в корень сборки рядом с python_embeded и ComfyUI.
pause

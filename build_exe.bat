@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
rem Собирает ND_Launcher.exe на твоём компьютере.
rem Нужен обычный Python 3.10+ с python.org (не python_embeded из ComfyUI).
rem Всё нужное для сборки ставится в отдельную папку .build_venv и не трогает системный Python.

set "SYS_PY="
where py >nul 2>nul && set "SYS_PY=py -3"
if not defined SYS_PY where python >nul 2>nul && set "SYS_PY=python"
if not defined SYS_PY goto no_python

%SYS_PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto no_python

if not exist ".build_venv\Scripts\python.exe" (
    echo [ND] Создаю окружение для сборки .build_venv...
    %SYS_PY% -m venv .build_venv
    if errorlevel 1 goto fail
)
set "PY=.build_venv\Scripts\python.exe"

echo [ND] Ставлю PySide6 и PyInstaller ^(при первой сборке это займёт пару минут^)...
"%PY%" -m pip install --disable-pip-version-check -q --upgrade -r requirements.txt
if errorlevel 1 goto fail

if not exist "brand\links.json" echo [ND] Нет brand\links.json — ссылки не будут зашиты.
if not exist "brand\example.png" echo [ND] Нет brand\example.png — замена input\example.png работать не будет.

echo [ND] Скачиваю иконки ссылок...
"%PY%" nd_launcher.py --fetch-icons
"%PY%" tools\make_version_info.py

echo [ND] Собираю exe...
"%PY%" -m PyInstaller --noconfirm --clean --log-level WARN --onefile --windowed --name ND_Launcher --icon nd_icon.ico --version-file version_info.txt --noupx --add-data "brand;brand" --hidden-import nd_i18n nd_launcher.py
if errorlevel 1 goto fail

echo.
echo [ND] Готово: %~dp0dist\ND_Launcher.exe
echo [ND] Положи ND_Launcher.exe в корень портативной сборки ComfyUI, рядом с папками python_embeded и ComfyUI.
explorer "%~dp0dist"
pause
exit /b 0

:no_python
echo [ND] Не найден Python 3.10 или новее.
echo [ND] Установи его с https://www.python.org/downloads/windows/
echo [ND] и в установщике отметь "Add python.exe to PATH". Потом запусти этот файл снова.
pause
exit /b 1

:fail
echo.
echo [ND] Сборка не удалась, смотри сообщения выше. Нужен интернет для установки пакетов.
pause
exit /b 1

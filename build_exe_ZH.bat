@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem 在本机生成 ND_Launcher.exe。
rem 需要从 python.org 安装 Python 3.10 或更高版本（不能使用 ComfyUI 自带的 python_embeded）。
rem 构建依赖安装在独立的 .build_venv 目录中，不会修改系统 Python。

set "SYS_PY="
where py >nul 2>nul && set "SYS_PY=py -3"
if not defined SYS_PY where python >nul 2>nul && set "SYS_PY=python"
if not defined SYS_PY goto no_python
%SYS_PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto no_python

if not exist ".build_venv\Scripts\python.exe" (
    echo [ND] 正在创建构建环境 .build_venv...
    %SYS_PY% -m venv .build_venv
    if errorlevel 1 goto fail
)

set "PY=.build_venv\Scripts\python.exe"
echo [ND] 正在从 requirements.txt 安装依赖（首次运行可能需要几分钟）...
"%PY%" -m pip install --disable-pip-version-check -q --upgrade -r requirements.txt
if errorlevel 1 goto fail

if not exist "brand\links.json" echo [ND] 缺少 brand\links.json，无法将自定义链接打包进程序。
if not exist "brand\example.png" echo [ND] 缺少 brand\example.png，无法替换 input\example.png。

echo [ND] 正在下载链接图标...
"%PY%" nd_launcher.py --fetch-icons
"%PY%" tools\make_version_info.py

echo [ND] 正在构建 EXE 文件...
"%PY%" -m PyInstaller --noconfirm --clean --log-level WARN --onefile --windowed --name ND_Launcher --icon nd_icon.ico --version-file version_info.txt --noupx --add-data "brand;brand" --hidden-import nd_i18n nd_launcher.py
if errorlevel 1 goto fail

echo.
echo [ND] 构建完成： %~dp0dist\ND_Launcher.exe
echo [ND] 请将 ND_Launcher.exe 放入便携版 ComfyUI 的根目录，与 python_embeded 和 ComfyUI 文件夹同级。
explorer "%~dp0dist"
pause
exit /b 0

:no_python
echo [ND] 未找到 Python 3.10 或更高版本。
echo [ND] 请从 https://www.python.org/downloads/windows/ 安装 Python。
echo [ND] 安装时请勾选 "Add python.exe to PATH"，然后重新运行此文件。
pause
exit /b 1

:fail
echo.
echo [ND] 构建失败，请检查上方错误信息。安装依赖需要网络连接。
pause
exit /b 1

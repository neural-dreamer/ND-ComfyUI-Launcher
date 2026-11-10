# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Neural Dreamer
"""Подготовка окружения другой платформы (NVIDIA/AMD): скачивание архива, распаковка python_embeded, зависимости (без Qt).

Окружение берётся из официального архива ComfyUI (ComfyUI_windows_portable_amd.7z и т. п.) — версию Python и torch
выбирают авторы ComfyUI. Распаковка .7z: установленный 7-Zip (быстрее) или py7zr (ставится pip-ом в python_embeded).
Обе распаковки идут отдельным процессом, чтобы работать одинаково из .py и из exe.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import nd_backend as B

SEVENZIP_URL = "https://www.7-zip.org/download.html"
METHODS = ("auto", "7zip", "py7zr")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class InstallError(Exception):
    pass


class Cancelled(InstallError):
    pass


def archive_url(backend):
    if backend not in B.BACKENDS:
        raise InstallError(f"Неизвестная платформа: {backend}")
    return B.RELEASES_URL + B.BACKENDS[backend]["archive"]


def archive_path(root, backend):
    """Куда качается архив: внутри хранилища окружений (тот же диск, что и сборка)."""
    return B.store_dir(root) / "downloads" / B.BACKENDS[backend]["archive"]


def prepared_env_path(root, backend):
    return B.env_dir(root, backend)


# ---------- 7-Zip ----------

def find_7zip(environ=None, which=shutil.which):
    """Путь к 7z.exe (7-Zip) или None: реестр Windows, Program Files, PATH."""
    environ = os.environ if environ is None else environ
    candidates = []
    if os.name == "nt":
        try:
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for sub in ("SOFTWARE\\7-Zip", "SOFTWARE\\WOW6432Node\\7-Zip"):
                    for view in (0, getattr(winreg, "KEY_WOW64_64KEY", 0)):
                        try:
                            with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | view) as key:
                                for value in ("Path64", "Path"):
                                    try:
                                        candidates.append(Path(winreg.QueryValueEx(key, value)[0]) / "7z.exe")
                                    except OSError:
                                        pass
                        except OSError:
                            pass
        except ImportError:
            pass
    for env_key in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA"):
        base = environ.get(env_key)
        if base:
            candidates.append(Path(base) / "7-Zip" / "7z.exe")
    for name in ("7z", "7zz", "7za"):
        found = which(name)
        if found:
            candidates.append(Path(found))
    for path in candidates:
        try:
            if path.is_file():
                return str(path)
        except OSError:
            pass
    return None


def py7zr_available(python_exe):
    """Есть ли py7zr в указанном Python (запуск отдельным процессом)."""
    try:
        r = subprocess.run([str(python_exe), "-c", "import py7zr"], capture_output=True, timeout=60,
                           creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def py7zr_install_command(python_exe):
    return [str(python_exe), "-m", "pip", "install", "--disable-pip-version-check", "py7zr"]


def choose_method(preference, sevenzip, py7zr_ok):
    """Какой способ распаковки использовать. preference: auto | 7zip | py7zr.
    Возвращает '7zip' | 'py7zr' | None (подходящего способа нет — нужно предложить пользователю выбор)."""
    if preference == "7zip":
        return "7zip" if sevenzip else None
    if preference == "py7zr":
        return "py7zr" if py7zr_ok else None
    if sevenzip:
        return "7zip"
    return "py7zr" if py7zr_ok else None


# ---------- запуск процессов ----------

def run_streaming(cmd, on_line=None, cancel=None, cwd=None, env=None):
    """Запускает процесс, строки вывода (разделители \\n и \\r) отдаёт в on_line. Возвращает код выхода.
    cancel() -> True останавливает процесс и бросает Cancelled."""
    try:
        proc = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env,
                                creationflags=CREATE_NO_WINDOW)
    except OSError as exc:
        raise InstallError(f"Не удалось запустить {cmd[0]}: {exc}") from exc
    buf = b""
    try:
        while True:
            chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            parts = re.split(rb"[\r\n]+", buf)
            buf = parts.pop()
            for part in parts:
                if part.strip() and on_line:
                    on_line(part.decode("utf-8", "replace").rstrip())
            if cancel and cancel():
                proc.kill()
                proc.wait()
                raise Cancelled("Отменено")
        if buf.strip() and on_line:
            on_line(buf.decode("utf-8", "replace").rstrip())
        return proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()


# ---------- скачивание ----------

def download_command(python_exe, script, url, dest, connections=8):
    """Команда запуска общего многопоточного загрузчика лаунчера (FAST_DL_SCRIPT): пауза и докачка через .ndpart.json,
    готовый файл появляется под именем dest только после полной загрузки."""
    return [str(python_exe), "-s", "-c", script, url, str(dest), str(int(connections)), ""]


def download_archive(root, backend, python_exe, script, *, connections=8, on_line=None, cancel=None):
    """Скачивает официальный архив платформы в python_envs/downloads. Уже скачанный архив повторно не качается.
    Возвращает путь к файлу."""
    dest = archive_path(root, backend)
    if dest.is_file():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    code = run_streaming(download_command(python_exe, script, archive_url(backend), dest, connections), on_line, cancel)
    if code == 10 and dest.is_file():  # загрузчик: «файл уже есть»
        return dest
    if code != 0 or not dest.is_file():
        raise InstallError(f"Не удалось скачать архив (код {code})")
    return dest


# ---------- распаковка ----------

# Запускается как `python -c EXTRACT_SCRIPT архив папка`: достаёт из архива только python_embeded и печатает «PROGRESS n total».
EXTRACT_SCRIPT = r"""
import sys, py7zr
archive, dest = sys.argv[1], sys.argv[2]
with py7zr.SevenZipFile(archive, "r") as z:
    names = z.getnames()
    targets = [n for n in names if "python_embeded" in n.replace("\\", "/").split("/")[:2]]
    if not targets:
        print("NO_PYTHON_EMBEDED", flush=True); sys.exit(3)
    total = len(targets)
    class CB(py7zr.callbacks.ExtractCallback):
        n = 0
        def report_start_preparation(self): pass
        def report_start(self, processing_file_path, processing_bytes): pass
        def report_update(self, decompressed_bytes): pass
        def report_end(self, processing_file_path, wrote_bytes):
            CB.n += 1
            if CB.n % 50 == 0 or CB.n == total:
                print("PROGRESS %d %d" % (CB.n, total), flush=True)
        def report_postprocess(self): pass
        def report_warning(self, message): print("WARN", message, flush=True)
    z.extract(path=dest, targets=targets, callback=CB())
print("PROGRESS %d %d" % (total, total), flush=True)
"""


def _find_python_embeded(base):
    """python_embeded в распакованном архиве: прямо в корне или в единственной верхней папке."""
    base = Path(base)
    if (base / "python_embeded" / "python.exe").is_file():
        return base / "python_embeded"
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        if (d / "python_embeded" / "python.exe").is_file():
            return d / "python_embeded"
    return None


def extract_environment(root, backend, archive, method, *, sevenzip=None, python_exe=None, progress=None, log=None, cancel=None):
    """Распаковывает python_embeded из archive в python_envs/<backend>/python_embeded.
    method: '7zip' (нужен sevenzip) или 'py7zr' (нужен python_exe с установленным py7zr). progress(процент 0..100)."""
    root, archive = Path(root), Path(archive)
    if not archive.is_file():
        raise InstallError(f"Архив не найден: {archive}")
    final = prepared_env_path(root, backend)
    if final.exists():
        raise InstallError(f"Окружение уже подготовлено: {final}")
    tmp = B.store_dir(root) / "_extract" / backend
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    tail = []

    def on_line(line):
        tail.append(line)
        del tail[:-5]
        m = re.match(r"PROGRESS (\d+) (\d+)$", line)
        if m and progress and int(m.group(2)):
            progress(min(99, int(m.group(1)) * 100 // int(m.group(2))))
            return
        m = re.search(r"(?<!\d)(\d{1,3})%", line) if method == "7zip" else None
        if m and progress:
            progress(min(99, int(m.group(1))))
            return
        if log and line:
            log(line)

    try:
        if method == "7zip":
            if not sevenzip:
                raise InstallError("7-Zip не найден")
            code = run_streaming([sevenzip, "x", str(archive), "-o" + str(tmp), "-y", "-bsp1", "-bso0"], on_line, cancel)
        elif method == "py7zr":
            if not python_exe:
                raise InstallError("Не указан Python с py7zr")
            code = run_streaming([python_exe, "-c", EXTRACT_SCRIPT, str(archive), str(tmp)], on_line, cancel)
        else:
            raise InstallError(f"Неизвестный способ распаковки: {method}")
        if code != 0:
            detail = " | ".join(t for t in tail if not t.startswith("PROGRESS"))
            raise InstallError(f"Распаковка не удалась (код {code})" + (f": {detail}" if detail else ""))
        found = _find_python_embeded(tmp)
        if not found:
            raise InstallError("В архиве нет python_embeded\\python.exe — это не портативная сборка ComfyUI")
        detected = B.detect_backend(found)
        if detected not in (None, backend):
            raise InstallError(f"В архиве окружение другой платформы ({detected}), ожидалась {backend}")
        final.parent.mkdir(parents=True, exist_ok=True)
        os.rename(found, final)
        B.write_marker(final, detected or backend)
        if progress:
            progress(100)
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return final


# ---------- зависимости ----------

def pip_base(python_exe):
    return [str(python_exe), "-m", "pip", "install", "--disable-pip-version-check"]


def launcher_deps_command(python_exe, requirements):
    """Зависимости самого лаунчера (PySide6 и др.) в новое окружение, чтобы лаунчер мог запуститься из него."""
    return pip_base(python_exe) + ["-r", str(requirements)]


PYSIDE_SPEC = "PySide6-Essentials>=6.7,<7"


def pyside_command(python_exe):
    """Установка PySide6 в новое окружение (только для запуска лаунчера из исходников; exe не нужен)."""
    return pip_base(python_exe) + [PYSIDE_SPEC]


def node_requirements(root):
    """requirements.txt включённых custom-нод: [(имя ноды, путь)]."""
    nodes = Path(root) / "ComfyUI" / "custom_nodes"
    result = []
    if nodes.is_dir():
        for d in sorted(nodes.iterdir(), key=lambda p: p.name.lower()):
            if not d.is_dir() or d.name.startswith((".", "__")) or d.name.endswith(".disabled"):
                continue
            req = d / "requirements.txt"
            if req.is_file():
                result.append((d.name, req))
    return result


def sync_plan(root, python_exe, constraints_file):
    """Шаги синхронизации зависимостей в окружении: [(название, команда pip)].
    Сначала ComfyUI, затем каждая нода; везде -c constraints, чтобы torch-стек не подменился."""
    base = pip_base(python_exe) + ["-c", str(constraints_file)]
    plan = []
    comfy = Path(root) / "ComfyUI" / "requirements.txt"
    if comfy.is_file():
        plan.append(("ComfyUI", base + ["-r", str(comfy)]))
    for name, req in node_requirements(root):
        plan.append((name, base + ["-r", str(req)]))
    return plan


def write_constraints(root, env, backend):
    """Сохраняет constraints torch-стека окружения рядом с ним; возвращает путь."""
    path = B.store_dir(root) / f"constraints-{backend}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(B.torch_constraints(env), encoding="utf-8")
    return path


def sync_dependencies(root, backend, env, python_exe, *, log=None, cancel=None):
    """Выполняет sync_plan. Ошибка отдельной ноды — предупреждение. Возвращает {'ok': [...], 'failed': [(имя, код)]}.
    По завершении сохраняет nodes_hash в маркер окружения."""
    constraints = write_constraints(root, env, backend)
    result = {"ok": [], "failed": []}
    for name, cmd in sync_plan(root, python_exe, constraints):
        if cancel and cancel():
            raise Cancelled("Отменено")
        if log:
            log(f"Зависимости: {name}")
        code = run_streaming(cmd, log, cancel)
        (result["ok"] if code == 0 else result["failed"]).append(name if code == 0 else (name, code))
    B.write_marker(env, backend, nodes_hash=B.nodes_hash(root))
    return result

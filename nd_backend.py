# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Neural Dreamer
"""Платформа сборки (NVIDIA / AMD): окружения python_embeded рядом и переключение между ними (без Qt).

Раскладка в корне портативной сборки:
  <root>/python_embeded                         — активное окружение (его использует лаунчер и ComfyUI);
  <root>/python_envs/<backend>/python_embeded   — неактивные окружения, по одному на backend;
  <root>/python_envs/switch.journal.json        — журнал незавершённого переключения.
Переключение — это переименования папок на одном диске: активное уходит в python_envs/<текущий>/, нужное
встаёт на его место. ComfyUI (код, custom_nodes, models, input, output, user) не затрагивается.
Каждое окружение хранит маркер nd_backend.json (backend, версии Python и torch, хеш списка нод).
Если маркера нет, backend определяется по файлам torch (torch/version.py, dist-info) — Python не запускается.
"""
import json
import os
from pathlib import Path
import re
import shutil
import time

ACTIVE_DIR = "python_embeded"
STORE_DIR = "python_envs"
MARKER = "nd_backend.json"
JOURNAL = "switch.journal.json"

# Описание поддерживаемых платформ. archive — имя файла официальной сборки на GitHub Releases ComfyUI
# (из неё берётся python_embeded целиком: версию Python и torch выбирают авторы ComfyUI, мы их не зашиваем).
BACKENDS = {
    "nvidia": {
        "label": "NVIDIA (CUDA)",
        "experimental": False,
        "archive": "ComfyUI_windows_portable_nvidia.7z",
        "attention_default": None,
    },
    "amd": {
        "label": "AMD (ROCm)",
        "experimental": True,
        "archive": "ComfyUI_windows_portable_amd.7z",
        "attention_default": "--use-pytorch-cross-attention",
    },
}
RELEASES_URL = "https://github.com/Comfy-Org/ComfyUI/releases/latest/download/"

# Пакеты, которые собираются под CUDA и на AMD не работают (имена нормализованы: нижний регистр, «-» → «_»).
NVIDIA_ONLY = (
    "sageattention", "sageattn", "flash_attn", "xformers", "nunchaku", "bitsandbytes", "triton",
    "nvidia_", "cupy", "tensorrt", "onnxruntime_gpu", "apex", "deepspeed", "auto_gptq", "autoawq",
)
# Пакеты, которые лаунчер/ComfyUI сами ставят под конкретный backend — в проверке совместимости не показываем.
TORCH_STACK = ("torch", "torchvision", "torchaudio")


class BackendError(Exception):
    pass


# ---------- раскладка ----------

def active_dir(root):
    return Path(root) / ACTIVE_DIR


def store_dir(root):
    return Path(root) / STORE_DIR


def env_dir(root, backend):
    """Где лежит НЕактивное окружение этого backend."""
    return store_dir(root) / backend / ACTIVE_DIR


def _site_packages(env):
    return Path(env) / "Lib" / "site-packages"


def _norm(name):
    return re.sub(r"[-_.]+", "_", name).lower()


# ---------- определение backend и версий ----------

def python_version(env):
    """'3.13' по файлу pythonXYZ._pth или pythonXYZ.dll; None, если не нашли."""
    env = Path(env)
    for pattern in ("python3*._pth", "python3*.dll"):
        for p in sorted(env.glob(pattern)):
            m = re.fullmatch(r"python3(\d+)(?:\._pth|\.dll)", p.name, re.I)
            if m:
                return "3." + m.group(1)
    return None


def _torch_version_py(site):
    path = site / "torch" / "version.py"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    info = {}
    for key in ("__version__", "cuda", "hip", "xpu"):
        m = re.search(r"^%s(?:\s*:[^=\n]+)?\s*=\s*(.+?)\s*$" % re.escape(key), text, re.M)
        if m:
            raw = m.group(1).strip()
            info[key] = None if raw == "None" else raw.strip("'\"")
    return info


def torch_info(env):
    """{'version', 'cuda', 'hip', 'xpu'} или {} — по torch/version.py, запасной путь — dist-info."""
    site = _site_packages(env)
    info = _torch_version_py(site)
    if info.get("__version__"):
        return {"version": info["__version__"], "cuda": info.get("cuda"), "hip": info.get("hip"), "xpu": info.get("xpu")}
    for d in sorted(site.glob("torch-*.dist-info")):
        version = d.name[len("torch-"):-len(".dist-info")]
        local = version.split("+", 1)[1].lower() if "+" in version else ""
        return {"version": version,
                "cuda": local if local.startswith("cu") else None,
                "hip": local if "rocm" in local or "hip" in local else None,
                "xpu": local if "xpu" in local else None}
    return {}


def detect_backend(env):
    """'nvidia' | 'amd' | 'intel' | 'cpu' | None (torch не найден)."""
    info = torch_info(env)
    if not info:
        return None
    if info.get("hip"):
        return "amd"
    if info.get("cuda"):
        return "nvidia"
    if info.get("xpu"):
        return "intel"
    version = (info.get("version") or "").lower()
    if "rocm" in version:
        return "amd"
    return "cpu"


def read_marker(env):
    try:
        return json.loads((Path(env) / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_marker(env, backend, **extra):
    """Записывает маркер окружения; существующие поля сохраняются, extra их обновляет."""
    data = read_marker(env)
    info = torch_info(env)
    data.update({"backend": backend, "python": python_version(env), "torch": info.get("version")})
    data.update(extra)
    data.setdefault("created", time.strftime("%Y-%m-%dT%H:%M:%S"))
    (Path(env) / MARKER).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def env_backend(env):
    """backend окружения: сначала файлы torch (они не врут), потом маркер."""
    return detect_backend(env) or read_marker(env).get("backend")


def describe(env):
    """Короткое описание для интерфейса: {'backend','python','torch','cuda','hip'}."""
    info = torch_info(env)
    return {"backend": env_backend(env), "python": python_version(env), "torch": info.get("version"),
            "cuda": info.get("cuda"), "hip": info.get("hip")}


def list_envs(root):
    """Неактивные окружения: {backend: путь}. Активное — active_dir(root)."""
    result = {}
    store = store_dir(root)
    if store.is_dir():
        for d in sorted(store.iterdir()):
            env = d / ACTIVE_DIR
            if d.is_dir() and (env / "python.exe").exists():
                result[d.name] = env
    return result


def current_backend(root):
    env = active_dir(root)
    return env_backend(env) if env.is_dir() else None


# ---------- размер, место, пакеты ----------

def dir_size(path):
    total = 0
    for base, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def installed_packages(env):
    """{нормализованное_имя: версия} по dist-info в site-packages."""
    result = {}
    for d in _site_packages(env).glob("*.dist-info"):
        stem = d.name[:-len(".dist-info")]
        name, _, version = stem.partition("-")
        if name:
            result[_norm(name)] = version
    return result


def incompatible_packages(env, backend):
    """Пакеты окружения, бесполезные на целевом backend. Для NVIDIA — пусто."""
    if backend == "nvidia":
        return {}
    found = {}
    for name, version in installed_packages(env).items():
        if name in TORCH_STACK:
            continue
        if any(name == p or (p.endswith("_") and name.startswith(p)) for p in NVIDIA_ONLY):
            found[name] = version
    return found


def torch_constraints(env):
    """Текст constraints-файла: фиксирует torch-стек окружения, чтобы pip не подменил его при установке requirements."""
    packages = installed_packages(env)
    lines = [f"{name}=={packages[name]}" for name in TORCH_STACK if name in packages]
    return "\n".join(lines) + ("\n" if lines else "")


def nodes_hash(root):
    """Хеш состава custom_nodes (имена папок и requirements.txt): меняется, когда нужно пересинхронизировать зависимости."""
    import hashlib
    h = hashlib.sha256()
    nodes = Path(root) / "ComfyUI" / "custom_nodes"
    if nodes.is_dir():
        for d in sorted(nodes.iterdir(), key=lambda p: p.name.lower()):
            if not d.is_dir() or d.name.startswith((".", "__")) or d.name.endswith(".disabled"):
                continue
            h.update(d.name.encode("utf-8"))
            req = d / "requirements.txt"
            if req.is_file():
                try:
                    h.update(req.read_bytes())
                except OSError:
                    pass
    return h.hexdigest()[:16]


def needs_dependency_sync(root, backend):
    """True, если после последней синхронизации этого окружения состав нод изменился."""
    env = env_dir(root, backend) if backend != current_backend(root) else active_dir(root)
    return read_marker(env).get("nodes_hash") != nodes_hash(root)


# ---------- GPU ----------

def classify_gpu(name):
    """(vendor, support) по названию видеокарты. support для AMD: 'supported' | 'uncertain' | 'unsupported' | None.
    Оценка по официальной матрице AMD для Windows (RX 7000 и 9000); RX 6000 и APU — под вопросом; старше — не поддерживаются."""
    n = (name or "").lower()
    if "nvidia" in n or re.search(r"\b(geforce|rtx|gtx|quadro|tesla)\b", n):
        return "nvidia", None
    if "intel" in n:
        return "intel", None
    if not ("amd" in n or "radeon" in n or "ryzen" in n):
        return "unknown", None
    if "r9700" in n:
        return "amd", "supported"
    m = re.search(r"\b(?:rx|w)\s*-?\s*(\d{3,4})", n)
    if not m:
        # Ryzen AI / встроенная графика Radeon 8xxM и т. п.
        return "amd", "uncertain"
    series = m.group(1)
    if len(series) == 3:  # RX 400/500
        return "amd", "unsupported"
    if series[0] == "9":
        return "amd", "supported"
    if series[0] == "7":
        return "amd", "supported" if series[1] in "789" else "uncertain"
    if series[0] == "6":
        return "amd", "uncertain"
    return "amd", "unsupported"


# ---------- переключение ----------

def _journal_path(root):
    return store_dir(root) / JOURNAL


def _write_journal(root, data):
    store_dir(root).mkdir(parents=True, exist_ok=True)
    tmp = _journal_path(root).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _journal_path(root))


def read_journal(root):
    try:
        return json.loads(_journal_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _clear_journal(root):
    try:
        _journal_path(root).unlink()
    except OSError:
        pass


def _move(src, dst):
    """Переименование папки; на Windows падает, если в ней открыты файлы."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(src, dst)
    except OSError as exc:
        raise BackendError(f"Не удалось переименовать {src} → {dst}: {exc}") from exc


def plan_switch(root, target):
    """Проверка перед переключением. Возвращает {'from','to','target_env'} или бросает BackendError."""
    root = Path(root)
    if target not in BACKENDS:
        raise BackendError(f"Неизвестная платформа: {target}")
    active = active_dir(root)
    if not (active / "python.exe").exists():
        raise BackendError("В корне сборки нет python_embeded\\python.exe")
    current = env_backend(active)
    if current is None:
        raise BackendError("Не удалось определить текущую платформу: в python_embeded нет torch")
    if current == target:
        raise BackendError("Эта платформа уже активна")
    if current not in BACKENDS:
        raise BackendError(f"Текущая платформа ({current}) не поддерживается переключением")
    target_env = env_dir(root, target)
    if not (target_env / "python.exe").exists():
        raise BackendError(f"Окружение {target} ещё не подготовлено")
    if env_backend(target_env) not in (None, target):
        raise BackendError(f"Окружение в python_envs\\{target} содержит torch другой платформы ({env_backend(target_env)})")
    if env_dir(root, current).exists():
        raise BackendError(f"python_envs\\{current} уже занято — разберись с папкой вручную")
    return {"from": current, "to": target, "target_env": target_env}


def switch(root, target, verify=None):
    """Переключает активное окружение на target. verify(env_path) -> (ok, сообщение) проверяет новое окружение
    (в лаунчере — запуск python.exe с import torch); при неудаче всё возвращается как было и бросается BackendError.
    Между шагами пишется журнал: при обрыве recover() доведёт откат до конца."""
    root = Path(root)
    plan = plan_switch(root, target)
    current = plan["from"]
    active = active_dir(root)
    # маркер для текущего окружения — чтобы его можно было узнать после переезда
    write_marker(active, current, nodes_hash=nodes_hash(root))
    stash = env_dir(root, current)
    incoming = plan["target_env"]
    journal = {"from": current, "to": target, "state": "start"}
    _write_journal(root, journal)
    try:
        _move(active, stash)
        journal["state"] = "stashed"
        _write_journal(root, journal)
        _move(incoming, active)
        journal["state"] = "done"
        _write_journal(root, journal)
    except BackendError:
        recover(root)
        raise
    if verify is not None:
        ok, message = verify(active)
        if not ok:
            rollback(root)
            raise BackendError(f"Новое окружение не прошло проверку: {message}")
    write_marker(active, target)
    _clear_journal(root)
    return {"from": current, "to": target}


def rollback(root):
    """Возвращает окружения в состояние до переключения. Решает по реальной раскладке папок, а не по состоянию журнала:
    журнал может отставать (переключение мог делать внешний скрипт). True, если журнал был."""
    root = Path(root)
    journal = read_journal(root)
    if not journal:
        return False
    current, target = journal["from"], journal["to"]
    active = active_dir(root)
    stash = env_dir(root, current)
    incoming = env_dir(root, target)
    if active.exists() and stash.exists() and not incoming.exists() and env_backend(active) == target:
        # новое окружение уже стоит на месте активного, старое лежит в хранилище — переключение завершено, откатываем
        _move(active, incoming)
        _move(stash, active)
    elif not active.exists() and stash.exists():
        # старое убрано, новое ещё не встало
        _move(stash, active)
    _clear_journal(root)
    return True


def recover(root):
    """Вызывать при старте лаунчера: если прошлое переключение оборвалось, откатывает его. True, если был откат."""
    journal = read_journal(root)
    if not journal:
        return False
    return rollback(root)


# ---------- переключение внешним скриптом (Windows не даёт переименовать python_embeded, пока из неё работает лаунчер) ----------

RESULT = "switch.result"
HELPER = "switch_helper.cmd"
VERIFY_LOG = "switch.verify.log"
STALE_JOURNAL_SECONDS = 300


def result_path(root):
    return store_dir(root) / RESULT


def begin_switch(root, target):
    """Готовит переключение внешним скриптом: проверка, маркер активного окружения, журнал. Возвращает plan."""
    root = Path(root)
    plan = plan_switch(root, target)
    write_marker(active_dir(root), plan["from"], nodes_hash=nodes_hash(root))
    try:
        result_path(root).unlink()
    except OSError:
        pass
    _write_journal(root, {"from": plan["from"], "to": target, "state": "pending", "started": time.time()})
    return plan


def _bat(text):
    """Значение для .cmd: проценты удваиваем, переводы строк недопустимы."""
    return str(text).replace("%", "%%").replace("\r", " ").replace("\n", " ")


def helper_script(root, plan, pid, restart_cmd):
    """Текст .cmd, который после выхода лаунчера меняет окружения местами, проверяет import torch и откатывает при ошибке.
    restart_cmd — готовая командная строка запуска лаунчера (уже в кавычках, % удвоены не нужно — это сделаем здесь)."""
    values = {"ROOT": _bat(root), "FROM": plan["from"], "TO": plan["to"], "PID": int(pid)}
    head = "".join(f'set "{k}={v}"\r\n' for k, v in values.items())
    return (
        "@echo off\r\nchcp 65001 >nul\r\nsetlocal EnableExtensions DisableDelayedExpansion\r\n"
        + head +
        'set "STORE=%ROOT%\\python_envs"\r\n'
        'set "ACTIVE=%ROOT%\\python_embeded"\r\n'
        'set "STASH=%STORE%\\%FROM%\\python_embeded"\r\n'
        'set "INCOMING=%STORE%\\%TO%\\python_embeded"\r\n'
        f'set "RESULT=%STORE%\\{RESULT}"\r\n'
        f'set "LOG=%STORE%\\{VERIFY_LOG}"\r\n'
        'if exist "%RESULT%" del "%RESULT%"\r\n'
        "set /a TRIES=0\r\n"
        ":wait\r\n"
        'tasklist /FI "PID eq %PID%" /NH 2>nul | find "%PID%" >nul\r\n'
        "if errorlevel 1 goto :go\r\n"
        "set /a TRIES+=1\r\n"
        "if %TRIES% GEQ 90 goto :timeout\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        "goto :wait\r\n"
        ":go\r\n"
        'if not exist "%STORE%\\%FROM%" mkdir "%STORE%\\%FROM%"\r\n'
        'call :mv "%ACTIVE%" "%STASH%" || goto :fail1\r\n'
        'call :mv "%INCOMING%" "%ACTIVE%" || goto :fail2\r\n'
        '"%ACTIVE%\\python.exe" -s -c "import torch" >"%LOG%" 2>&1\r\n'
        "if errorlevel 1 goto :verify_failed\r\n"
        '> "%RESULT%" echo done\r\n'
        "goto :restart\r\n"
        ":fail1\r\n"
        '> "%RESULT%" echo failed\r\n'
        '>> "%RESULT%" echo Could not rename python_embeded. Close programs that use it and try again.\r\n'
        "goto :restart\r\n"
        ":fail2\r\n"
        'call :mv "%STASH%" "%ACTIVE%"\r\n'
        '> "%RESULT%" echo failed\r\n'
        '>> "%RESULT%" echo Could not put the new environment in place; the previous one was restored.\r\n'
        "goto :restart\r\n"
        ":verify_failed\r\n"
        'call :mv "%ACTIVE%" "%INCOMING%"\r\n'
        'call :mv "%STASH%" "%ACTIVE%"\r\n'
        '> "%RESULT%" echo failed\r\n'
        '>> "%RESULT%" echo The new environment did not pass the torch check; the previous one was restored.\r\n'
        'type "%LOG%" >> "%RESULT%"\r\n'
        "goto :restart\r\n"
        ":timeout\r\n"
        '> "%RESULT%" echo failed\r\n'
        '>> "%RESULT%" echo The launcher did not close in time; nothing was changed.\r\n'
        "endlocal\r\nexit /b 1\r\n"
        ":restart\r\n"
        # onefile-exe (PyInstaller): родительский загрузчик ещё удаляет свою временную папку, а переменные окружения
        # старого запуска заставили бы новый exe искать python313.dll в ней. Ждём и просим начать «с нуля».
        "timeout /t 3 /nobreak >nul\r\n"
        'set "PYINSTALLER_RESET_ENVIRONMENT=1"\r\n'
        'set "_MEIPASS2="\r\n'
        f"start \"\" {_bat(restart_cmd)}\r\n"
        "endlocal\r\nexit /b 0\r\n"
        ":mv\r\n"
        "set /a T=0\r\n"
        ":mv_try\r\n"
        'move "%~1" "%~2" >nul 2>nul\r\n'
        "if not errorlevel 1 exit /b 0\r\n"
        "set /a T+=1\r\n"
        "if %T% GEQ 10 exit /b 1\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        "goto :mv_try\r\n"
    )


def write_helper(root, plan, pid, restart_cmd):
    path = store_dir(root) / HELPER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(helper_script(root, plan, pid, restart_cmd).encode("utf-8"))
    return path


def finish_pending(root):
    """Вызывать при старте лаунчера. Возвращает None (ничего не было) или
    {'status': 'done'|'failed'|'recovered'|'busy', 'from', 'to', 'message'}."""
    root = Path(root)
    journal = read_journal(root)
    result = None
    try:
        result = result_path(root).read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except OSError:
        pass
    if not journal and not result:
        return None
    frm, to = (journal or {}).get("from"), (journal or {}).get("to")
    if result:
        status = "done" if result[0].strip().lower() == "done" else "failed"
        message = "\n".join(result[1:]).strip()
        if status == "done":
            env = active_dir(root)
            if to and env_backend(env) == to:
                write_marker(env, to)
            else:
                status, message = "failed", "После переключения активна не та платформа"
                if journal:
                    rollback(root)
        elif journal:
            rollback(root)  # скрипт уже вернул папки; здесь только чистим журнал и подстраховываемся
        _clear_journal(root)
        try:
            result_path(root).unlink()
        except OSError:
            pass
        return {"status": status, "from": frm, "to": to, "message": message}
    # журнал без результата: скрипт ещё работает или переключение оборвалось
    if time.time() - float(journal.get("started") or 0) < STALE_JOURNAL_SECONDS:
        return {"status": "busy", "from": frm, "to": to, "message": ""}
    rollback(root)
    return {"status": "recovered", "from": frm, "to": to, "message": ""}


# ---------- видеокарты и настройки запуска ----------

def detect_gpus(timeout=8):
    """Названия видеокарт (Windows: Win32_VideoController через PowerShell). На других ОС и при ошибке — []."""
    if os.name != "nt":
        return []
    import subprocess
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
           "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=0x08000000)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in r.stdout.decode("utf-8", "replace").splitlines() if line.strip()]


def gpu_assessment(names, target):
    """Есть ли в компьютере видеокарта целевой платформы и насколько она подходит.
    {'found': bool, 'name': str|None, 'support': 'supported'|'uncertain'|'unsupported'|None}"""
    order = {"supported": 0, "uncertain": 1, "unsupported": 2, None: 0}
    best = None
    for name in names:
        vendor, support = classify_gpu(name)
        if vendor == target:
            if best is None or order[support] < order[best[1]]:
                best = (name, support)
    if not best:
        return {"found": False, "name": None, "support": None}
    return {"found": True, "name": best[0], "support": best[1]}


SAGE = "--use-sage-attention"
FLASH = "--use-flash-attention"
PYTORCH_ATTENTION = "--use-pytorch-cross-attention"


def adapt_options(options, target, saved=None):
    """Настройки запуска для целевой платформы. saved — настройки, сохранённые при прошлом уходе с этой платформы
    (если есть, возвращаются как есть). Для AMD Sage/Flash и «Авто» заменяются на PyTorch attention.
    Возвращает (новые_настройки, список_замен)."""
    if saved:
        return dict(saved), []
    opts = dict(options or {})
    changes = []
    if target == "amd":
        if opts.get("attention") in ("", None, SAGE, FLASH):
            changes.append(("attention", opts.get("attention") or "", PYTORCH_ATTENTION))
            opts["attention"] = PYTORCH_ATTENTION
        if opts.get("fp8_unet"):
            changes.append(("fp8_unet", True, True))  # не меняем, но сообщаем: fp8 на AMD работает не везде
    return opts, changes

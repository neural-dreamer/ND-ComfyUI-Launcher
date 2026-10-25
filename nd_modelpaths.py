# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Neural Dreamer
"""Пути к моделям: extra_model_paths.yaml и ссылки на папки (без Qt).

extra_model_paths.yaml правится по секциям: секция, которую меняет лаунчер, переписывается целиком,
остальной текст файла (секции, написанные вручную, комментарии) остаётся как был. Перед записью — копия .bak.
Секции лаунчера помечены строкой «# ND Launcher: <название>» над ключом. Выключенная секция закомментирована
префиксом «#nd-off# » в каждой строке — ComfyUI её не видит, лаунчер может включить обратно.

Ссылки: для нод, которые ищут модели только в ComfyUI/models и не читают yaml. На Windows — связь (junction,
mklink /J): прав администратора не нужно, работает на локальных дисках. Удаляется только сама ссылка.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

MARK = "# ND Launcher: "
OFF = "#nd-off# "
SERVICE_KEYS = ("base_path", "is_default", "download_model_base")
# Типы, которые ComfyUI знает сам (folder_paths); их обычно достаточно подключить через yaml.
KNOWN_TYPES = {"checkpoints", "configs", "loras", "vae", "text_encoders", "clip", "diffusion_models", "unet",
               "clip_vision", "style_models", "embeddings", "diffusers", "vae_approx", "controlnet", "t2i_adapter",
               "gligen", "upscale_models", "latent_upscale_models", "hypernetworks", "photomaker", "classifiers",
               "model_patches", "audio_encoders"}
LEGACY = {"unet": "diffusion_models", "clip": "text_encoders", "t2i_adapter": "controlnet"}
YAML, LINK, BOTH = "yaml", "link", "both"


def default_method(type_name):
    """Известные ComfyUI типы — через yaml; папки нод (LLM, TTS, sam3…) — yaml и ссылка, на всякий случай."""
    return YAML if type_name in KNOWN_TYPES else BOTH


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _is_abs(p):
    return bool(re.match(r"^([A-Za-z]:[\\/]|[\\/]{2}|/)", p))


def _strip_comment(line):
    out, q = [], None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


# ─────────────────────────────── разбор yaml ───────────────────────────────

def parse(text, yaml_dir):
    """Секции файла: [{key, title, managed, enabled, base, base_raw, is_default, entries: [(тип, [пути])],
    start, end}] — start/end: номера строк (включительно), включая строку-метку над секцией."""
    lines = (text or "").splitlines()
    sections, cur = [], None
    block = None
    for i, raw in enumerate(lines):
        off = raw.startswith(OFF)
        body = raw[len(OFF):] if off else raw
        line = _strip_comment(body)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        st = line.strip()
        if indent == 0 and st.endswith(":") and not body.lstrip().startswith("#"):
            start = i
            title, managed = _unquote(st[:-1]), False
            j = i - 1
            if j >= 0:
                prev = lines[j][len(OFF):] if lines[j].startswith(OFF) else lines[j]
                if prev.startswith(MARK):
                    title, managed, start = prev[len(MARK):].strip(), True, j
            key = _unquote(st[:-1])
            cur = dict(key=key, title=title, managed=managed or key.startswith("nd_"), enabled=not off,
                       base_raw="", is_default=False, entries=[], start=start, end=i, values={})
            sections.append(cur)
            block = None
            continue
        if cur is None:
            continue
        cur["end"] = i
        if block is not None and indent > block[1]:
            block[0].append(_unquote(st))
            continue
        block = None
        m = re.match(r'^("[^"]*"|\'[^\']*\'|[^:]+?)\s*:\s*(.*)$', st)
        if not m:
            continue
        k, v = _unquote(m.group(1)), m.group(2).strip()
        if v in ("|", "|-", "|+", ">", ">-"):
            vals = []
            block = (vals, indent)
        else:
            vals = [_unquote(v)] if v else []
        cur["values"][k] = vals
    for s in sections:
        vals = s.pop("values")
        s["base_raw"] = (vals.get("base_path") or [""])[0]
        bp = os.path.expandvars(os.path.expanduser(s["base_raw"]))
        s["base"] = os.path.normpath(bp if _is_abs(bp) else os.path.join(yaml_dir, bp)) if bp else os.path.normpath(yaml_dir)
        s["is_default"] = (vals.get("is_default") or ["false"])[0].strip().lower() == "true"
        s["entries"] = [(k, [p for p in v if p]) for k, v in vals.items() if k not in SERVICE_KEYS]
    return sections


def entry_paths(section):
    """[(тип, полный путь)] секции."""
    out = []
    for t, paths in section["entries"]:
        for p in paths:
            p = os.path.expandvars(os.path.expanduser(p))
            out.append((t, os.path.normpath(p if _is_abs(p) else os.path.join(section["base"], p))))
    return out


# ─────────────────────────────── запись yaml ───────────────────────────────

def _q(s):
    return '"' + s.replace("\\", "/").replace('"', '\\"') + '"'


def render(key, title, base, entries, is_default=False, enabled=True):
    """Текст секции. entries: [(тип, [пути относительно base или абсолютные])]."""
    base = str(base).replace("\\", "/").rstrip("/") + "/"
    out = [MARK + title, f"{key}:", f"    base_path: {_q(base)}"]
    if is_default:
        out.append("    is_default: true")
    for t, paths in entries:
        paths = [p.replace("\\", "/") for p in paths if p is not None]
        if len(paths) == 1:
            out.append(f"    {t}: {_q(paths[0]) if (' ' in paths[0] or ':' in paths[0] or not paths[0]) else paths[0]}")
        elif paths:
            out.append(f"    {t}: |")
            out += [f"        {p}" for p in paths]
    if not enabled:
        out = [OFF + ln for ln in out]
    return out


def new_key(title, sections):
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40] or "models"
    used = {s["key"] for s in sections}
    key, n = f"nd_{slug}", 2
    while key in used:
        key, n = f"nd_{slug}_{n}", n + 1
    return key


def _lines_without(text, section):
    lines = (text or "").splitlines()
    start, end = section["start"], section["end"]
    while start > 0 and not lines[start - 1].strip():   # пустая строка-разделитель перед секцией
        start -= 1
    return lines[:start] + lines[end + 1:]


def upsert(text, yaml_dir, key, title, base, entries, is_default=False):
    """Заменить секцию key (или добавить в конец). Возвращает новый текст."""
    secs = parse(text, yaml_dir)
    old = next((s for s in secs if s["key"] == key), None)
    block = render(key, title, base, entries, is_default, enabled=old["enabled"] if old else True)
    lines = (text or "").splitlines()
    if old:
        lines = lines[:old["start"]] + block + lines[old["end"] + 1:]
    else:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ([""] if lines else []) + block
    if is_default:   # основная папка для загрузок может быть только одна
        return _clear_default_except(("\n".join(lines) + "\n"), yaml_dir, key)
    return "\n".join(lines) + "\n"


def _clear_default_except(text, yaml_dir, key):
    lines = text.splitlines()
    for s in parse(text, yaml_dir):
        if s["key"] != key and s["is_default"]:
            for i in range(s["start"], s["end"] + 1):
                body = lines[i][len(OFF):] if lines[i].startswith(OFF) else lines[i]
                if re.match(r"^\s+is_default\s*:", body):
                    lines[i] = lines[i].replace("is_default", "# is_default", 1)
    return "\n".join(lines) + "\n"


def remove(text, yaml_dir, key):
    sec = next((s for s in parse(text, yaml_dir) if s["key"] == key), None)
    if not sec:
        return text
    lines = _lines_without(text, sec)
    return ("\n".join(lines) + "\n") if lines else ""


def set_enabled(text, yaml_dir, key, enabled):
    sec = next((s for s in parse(text, yaml_dir) if s["key"] == key), None)
    if not sec or sec["enabled"] == enabled:
        return text
    lines = (text or "").splitlines()
    for i in range(sec["start"], sec["end"] + 1):
        if enabled and lines[i].startswith(OFF):
            lines[i] = lines[i][len(OFF):]
        elif not enabled and lines[i].strip():
            lines[i] = OFF + lines[i]
    return "\n".join(lines) + "\n"


def write(path, text):
    """Записать yaml атомарно; прежний файл — в .bak."""
    path = Path(path)
    if path.is_file():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ─────────────────────────────── источники ───────────────────────────────

def count_files(folder, limit=200000):
    n = 0
    for _dp, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        n += len(files)
        if n >= limit:
            break
    return n


def comfy_dir(folder):
    """Папка ComfyUI для сборки (корень портативной сборки, ComfyUI или её models) или None."""
    f = Path(folder)
    for c in (f / "ComfyUI", f, f.parent if f.name.lower() == "models" else None):
        if c and (c / "models").is_dir() and ((c / "main.py").is_file() or (c / "comfy").is_dir()):
            return c
    return None


def detect(folder):
    """Что можно подключить из папки: dict(kind=build|folder, base, items=[{type, sub, path, files}])."""
    folder = Path(folder)
    comfy = comfy_dir(folder)
    if comfy:
        kind, base, scan_root, prefix = "build", comfy, comfy / "models", "models/"
    else:
        kind, base, scan_root, prefix = "folder", folder, folder, ""
    items = []
    try:
        subs = sorted((d for d in scan_root.iterdir() if d.is_dir() and not d.name.startswith(".")), key=lambda d: d.name.lower())
    except OSError:
        subs = []
    for d in subs:
        items.append(dict(type=d.name, sub=f"{prefix}{d.name}/", path=str(d), files=count_files(d)))
    if kind == "folder" and not items:
        items.append(dict(type="", sub="", path=str(folder), files=count_files(folder)))
    return dict(kind=kind, base=str(base), items=items)


def section_status(section):
    """[(тип, путь, есть ли папка, файлов)] и общая доступность базовой папки."""
    rows = []
    for t, p in entry_paths(section):
        ok = os.path.isdir(p)
        rows.append((t, p, ok, count_files(p) if ok else 0))
    return rows, os.path.isdir(section["base"])


# ─────────────────────────────── ссылки ───────────────────────────────

FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def is_link(path):
    p = str(path)
    if os.path.islink(p):
        return True
    isj = getattr(os.path, "isjunction", None)
    if isj and isj(p):
        return True
    try:
        return bool(getattr(os.lstat(p), "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def link_target(path):
    try:
        t = os.readlink(str(path))
    except OSError:
        return ""
    return t[4:] if t.startswith("\\\\?\\") else t


def list_links(comfy):
    """Ссылки в ComfyUI/models (на первом и втором уровне): [(ссылка, цель, работает ли)]."""
    models = Path(comfy) / "models"
    out = []
    try:
        children = sorted(models.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return out
    for c in children:
        if is_link(c):
            t = link_target(c)
            out.append((str(c), t, os.path.isdir(c)))
        elif c.is_dir():
            try:
                for g in sorted(c.iterdir(), key=lambda p: p.name.lower()):
                    if is_link(g):
                        out.append((str(g), link_target(g), os.path.isdir(g)))
            except OSError:
                pass
    return out


def _same_dir(a, b):
    try:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    except OSError:
        return False


def plan_link(comfy, type_name, target, label):
    """Куда поставить ссылку на target для типа: (путь ссылки, режим) — режим:
    'folder' — ссылкой станет сама models/<тип> (её нет или она пустая), 'subfolder' — models/<тип>/<label>,
    'exists' — такая ссылка уже есть."""
    tdir = Path(comfy) / "models" / type_name
    if is_link(tdir):
        if _same_dir(tdir, target):
            return str(tdir), "exists"
        return str(tdir / _safe(label)), "subfolder"
    if not tdir.exists() or (tdir.is_dir() and not any(tdir.iterdir())):
        return str(tdir), "folder"
    sub = tdir / _safe(label)
    if is_link(sub) and _same_dir(sub, target):
        return str(sub), "exists"
    return str(sub), "subfolder"


def _safe(label):
    return re.sub(r'[<>:"/\\|?*\s]+', "_", label).strip("._") or "linked"


def create_link(link, target):
    """Создаёт ссылку link → target. На Windows — junction (mklink /J), иначе символическая ссылка."""
    link, target = Path(link), Path(target)
    if not target.is_dir():
        raise FileNotFoundError(f"Folder not found: {target}")
    if link.exists() or is_link(link):
        if link.is_dir() and not is_link(link) and not any(link.iterdir()):
            link.rmdir()   # пустая папка заменяется ссылкой
        else:
            raise FileExistsError(f"Already exists: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        r = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0 or not is_link(link):
            raise OSError((r.stdout + r.stderr).strip() or "mklink failed")
    else:
        os.symlink(str(target), str(link), target_is_directory=True)


def remove_link(link):
    """Удаляет только ссылку; содержимое папки, на которую она указывает, не трогается."""
    link = str(link)
    if not is_link(link):
        raise ValueError(f"Not a link: {link}")
    try:
        os.rmdir(link)       # junction и символическая ссылка на папку в Windows
    except OSError:
        os.unlink(link)      # символическая ссылка в Linux/macOS


# ─────────────────────────────── порядок поиска ───────────────────────────────

def search_order(comfy, sections):
    """{тип: [(путь, откуда)]} — где ComfyUI ищет модели. Пути с is_default — первыми, затем папка сборки,
    затем остальные секции по порядку (так же, как folder_paths.add_model_folder_path)."""
    comfy = Path(comfy)
    order = {}
    types = set()
    models = comfy / "models"
    try:
        types |= {d.name for d in models.iterdir() if d.is_dir()}
    except OSError:
        pass
    for s in sections:
        if s["enabled"]:
            types |= {t for t, _ in s["entries"]}
    for t in sorted(types, key=str.lower):
        key = LEGACY.get(t, t)
        own = models / t
        rows = []
        if own.is_dir():
            rows.append((str(own), "link" if is_link(own) else "build"))
        order.setdefault(key, [])
        front = []
        for s in sections:
            if not s["enabled"]:
                continue
            for et, p in entry_paths(s):
                if LEGACY.get(et, et) == key and et == t:
                    (front if s["is_default"] else rows).append((p, s["title"]))
        order[key] = front + order[key] + rows
    return {k: v for k, v in order.items() if v}

#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Neural Dreamer
"""
ND · ComfyUI Launcher — https://github.com/neural-dreamer/ND-ComfyUI-Launcher
Лаунчер для портативной сборки ComfyUI (python_embeded).

Положи файл в корень сборки — рядом с папками python_embeded и ComfyUI.
Описания воркфлоу читаются из utils/*.ndesc (формат — см. docs/NDESC_FORMAT.md).

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version. It is distributed WITHOUT ANY WARRANTY.
See the LICENSE file or <https://www.gnu.org/licenses/>.
"""
import sys
import os
import re
import json
import html
import math
import time
import stat
import shlex
import shutil
import codecs
import subprocess
import base64
import hashlib
import getpass
from pathlib import Path

from PySide6.QtCore import (QTranslator, QLibraryInfo, QLocale, Qt, QObject, QProcess, QProcessEnvironment, QTimer, QUrl, QRectF, QPointF, QSize,
                            QThread, Signal, QEvent)
from PySide6.QtGui import (QColor, QFont, QPainter, QPainterPath, QLinearGradient, QPen, QBrush, QIcon, QPixmap,
                           QDesktopServices, QImage, QTextCursor, QTextCharFormat, QTextDocument, QGuiApplication, QPalette)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QDialog, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPlainTextEdit, QTextBrowser,
    QStackedWidget, QSplitter, QFileDialog, QMessageBox, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QInputDialog, QGraphicsDropShadowEffect, QScrollArea, QButtonGroup, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QSizePolicy, QSystemTrayIcon, QMenu,
)

# ─────────────────────────────── локализация ──────────────────────────────────
# Исходные строки в коде — русские; они же ключи словарей в nd_i18n.py.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # python_embeded (._pth) не видит папку скрипта
try:
    from nd_i18n import TRANSLATIONS
except Exception:
    TRANSLATIONS = {}

LANGS = [("ru", "RU", "Русский"), ("en", "EN", "English"), ("zh", "ZH", "中文")]
QT_LOCALES = {"ru": "ru", "en": "en", "zh": "zh_CN"}
_LANG = "ru"
_qt_translator = None


def set_lang(code):
    global _LANG
    _LANG = code if code in {c for c, _, _ in LANGS} else "ru"


def get_lang():
    return _LANG


def tr(s, *args, **kw):
    """Перевод строки интерфейса. Шаблоны используют {0}, {1}… как str.format."""
    if _LANG != "ru":
        s = TRANSLATIONS.get(_LANG, {}).get(s, s)
    if args or kw:
        try:
            return s.format(*args, **kw)
        except Exception:
            return s
    return s


def install_qt_translator(code):
    """Стандартные кнопки Qt (Да/Нет, Отмена) на выбранном языке, если файлы переводов Qt доступны."""
    global _qt_translator
    app = QApplication.instance()
    if not app:
        return
    if _qt_translator:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    t = QTranslator(app)
    loc = QT_LOCALES.get(code, "en")
    try:
        path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    except Exception:
        path = ""
    if loc != "en" and t.load(f"qtbase_{loc}", path):
        app.installTranslator(t)
        _qt_translator = t
    QLocale.setDefault(QLocale(loc))


APP_TITLE = "ND · ComfyUI Launcher"
VERSION = "1.1.0"
DEFAULT_PORT = 8188
BRAND_NAME = "Neural Dreamer"
REPO_URL = "https://github.com/neural-dreamer/ND-ComfyUI-Launcher"
# аргументы, которые добавляются к любому пресету запуска
# Флаги, включаемые галочками на вкладке «Запуск» (по умолчанию все включены): ключ конфига → аргументы.
LAUNCH_FLAGS = [("arg_manager", ["--enable-manager"]),
                ("arg_manager_legacy", ["--enable-manager-legacy-ui"]),
                ("arg_upload", ["--max-upload-size", "999"])]

# ─────────────────────────────────── темы ─────────────────────────────────────
# CYAN / PINK — два конца фирменного градиента; где они равны, акцент плоский.
THEMES = {
    "neon": dict(
        name="Неон", desc="Фирменный неон Neural Dreamer",
        tokens=dict(
            BG="#0a0a12", SURFACE="#11111c", SURFACE2="#191928", BORDER="#26263a", BORDER_STRONG="#3a3a55",
            TEXT="#e9e9f4", MUTED="#8b8ba6", CYAN="#00e5ff", PINK="#ff2bd6", GREEN="#3dffa0", YELLOW="#ffd84d",
            RED="#ff4d6d", ON_ACCENT="#07070d", ACC_H1="#66f2ff", ACC_H2="#ff73e6",
            SEL="rgba(0,229,255,90)", SEL_MID="rgba(0,229,255,60)", SEL_SOFT="rgba(0,229,255,45)",
            NAV1="rgba(0,229,255,48)", NAV2="rgba(255,43,214,10)", ACC2_SOFT="rgba(255,43,214,30)",
            LINK_HOVER="rgba(255,43,214,22)", DIS_TEXT="#4f4f66", DIS_BORDER="#1c1c2b", DIS_BG="#13131f",
            CONSOLE_BG="#05050a", CONSOLE_TEXT="#c4c4d6", ALT_ROW="#141422",
            R_SM="6px", R_IN="8px", R_BTN="10px", R_LG="12px", R_PANEL="14px", R_PILL="16px",
            GLOW1=(0, 229, 255, 150), GLOW2=(255, 43, 214, 110),
        )),
    "fog": dict(
        name="Туманная ночь", desc="Спокойные серо-синие тона, как мокрый асфальт",
        tokens=dict(
            BG="#181b20", SURFACE="#1f2329", SURFACE2="#272c33", BORDER="#333942", BORDER_STRONG="#46505c",
            TEXT="#d6dbe2", MUTED="#8b939f", CYAN="#86a4bf", PINK="#9a9ec4", GREEN="#88b59c", YELLOW="#cbb87a",
            RED="#c7848c", ON_ACCENT="#13161a", ACC_H1="#9bb6cd", ACC_H2="#adb0d0",
            SEL="rgba(134,164,191,95)", SEL_MID="rgba(134,164,191,70)", SEL_SOFT="rgba(134,164,191,50)",
            NAV1="rgba(134,164,191,40)", NAV2="rgba(134,164,191,6)", ACC2_SOFT="rgba(154,158,196,28)",
            LINK_HOVER="rgba(134,164,191,22)", DIS_TEXT="#59616c", DIS_BORDER="#262b31", DIS_BG="#1c2025",
            CONSOLE_BG="#13161a", CONSOLE_TEXT="#c2c8d0", ALT_ROW="#22262c",
            R_SM="5px", R_IN="7px", R_BTN="8px", R_LG="10px", R_PANEL="12px", R_PILL="14px",
            GLOW1=(134, 164, 191, 45), GLOW2=(0, 0, 0, 0),
        )),
    "classic": dict(
        name="Классик", desc="Классическая тёмная тема Windows",
        tokens=dict(
            BG="#202020", SURFACE="#2b2b2b", SURFACE2="#323232", BORDER="#3d3d3d", BORDER_STRONG="#575757",
            TEXT="#ffffff", MUTED="#a6a6a6", CYAN="#4cc2ff", PINK="#4cc2ff", GREEN="#6ccb5f", YELLOW="#fce100",
            RED="#ff99a4", ON_ACCENT="#000000", ACC_H1="#47b1e8", ACC_H2="#47b1e8",
            SEL="rgba(76,194,255,80)", SEL_MID="rgba(76,194,255,60)", SEL_SOFT="rgba(255,255,255,22)",
            NAV1="rgba(255,255,255,18)", NAV2="rgba(255,255,255,18)", ACC2_SOFT="rgba(76,194,255,30)",
            LINK_HOVER="rgba(255,255,255,14)", DIS_TEXT="#6e6e6e", DIS_BORDER="#353535", DIS_BG="#2a2a2a",
            CONSOLE_BG="#0c0c0c", CONSOLE_TEXT="#cccccc", ALT_ROW="#2f2f2f",
            R_SM="4px", R_IN="4px", R_BTN="4px", R_LG="6px", R_PANEL="8px", R_PILL="4px",
            GLOW1=(0, 0, 0, 0), GLOW2=(0, 0, 0, 0),
        )),
}
DEFAULT_THEME = "neon"
C = dict(THEMES[DEFAULT_THEME]["tokens"])
_THEME = DEFAULT_THEME


def apply_theme(tid):
    """Меняет текущие цвета (C) и таблицу стилей приложения."""
    global _THEME
    _THEME = tid if tid in THEMES else DEFAULT_THEME
    C.clear()
    C.update(THEMES[_THEME]["tokens"])
    app = QApplication.instance()
    if app:
        app.setStyleSheet(build_qss())


def get_theme():
    return _THEME


def glow_effect(parent, rgba, blur):
    """Свечение по цвету темы; в темах без неона — без эффекта."""
    if not rgba or rgba[3] == 0:
        return None
    g = QGraphicsDropShadowEffect(parent)
    g.setBlurRadius(blur)
    g.setOffset(0, 0)
    g.setColor(QColor(*rgba))
    return g


# Приглушённая палитра для карточек описаний воркфлоу: длинный текст читается легче, чем на неоновых акцентах.
DESC = dict(TEXT="#d3d3e0", HEAD="#93c9d6", TAG="#bfa5d3", OK="#8cc9a4", BAD="#d98e98", LINK="#a3c2e6")


# ─────────────────────────────── пути и конфиг ───────────────────────────────

def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = app_dir() / "nd_launcher.json"


def brand_dir() -> Path:
    """Папка brand: в собранном .exe она зашита внутрь (распаковывается PyInstaller во временную папку),
    при запуске из исходников лежит рядом с nd_launcher.py."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "brand"
    return app_dir() / "brand"


def load_links(bdir: Path = None):
    bdir = Path(bdir or brand_dir())
    try:
        data = json.loads((bdir / "links.json").read_text("utf-8-sig"))
        links = data.get("links", []) if isinstance(data, dict) else data
        return [l for l in links if isinstance(l, dict) and str(l.get("url", "")).strip()]
    except Exception:
        return []


def link_host(url: str) -> str:
    m = re.match(r"^(?:[a-z]+://)?([^/?#]+)", url.strip(), re.I)
    return (m.group(1) if m else url).lower()


def link_slug(url: str) -> str:
    host = link_host(url)
    host = re.sub(r"^(www|m)\.", "", host)
    return re.sub(r"[^a-z0-9]+", "", host.split(".")[0]) or "link"


def fetch_link_icons(bdir: Path, links=None, force=False, log=print):
    """Скачивает иконки сайтов (favicon) для ссылок в brand/icons. Только stdlib — работает без Qt."""
    import urllib.request
    bdir = Path(bdir)
    links = load_links(bdir) if links is None else links
    (bdir / "icons").mkdir(parents=True, exist_ok=True)
    changed = False
    for l in links:
        url = str(l.get("url", "")).strip()
        if not url:
            continue
        rel = l.get("icon") or f"icons/{link_slug(url)}.png"
        target = bdir / rel
        if target.exists() and not force:
            continue
        host = link_host(url)
        for src in (f"https://www.google.com/s2/favicons?domain={host}&sz=64",
                    f"https://icons.duckduckgo.com/ip3/{host}.ico"):
            try:
                req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 ND-Launcher"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = r.read()
                if len(data) < 60 or not (data[:8] == b"\x89PNG\r\n\x1a\n" or data[:4] == b"\x00\x00\x01\x00"):
                    continue
                if data[:4] == b"\x00\x00\x01\x00" and target.suffix.lower() == ".png":
                    target = target.with_suffix(".ico")
                    rel = str(Path(rel).with_suffix(".ico")).replace("\\", "/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                if l.get("icon") != rel:
                    l["icon"] = rel
                    changed = True
                log(f"иконка: {l.get('title') or host} ← {src.split('/')[2]}")
                break
            except Exception:
                pass
        else:
            log(f"не удалось скачать иконку для {host}")
    return changed


def is_root(p) -> bool:
    try:
        p = Path(p)
        return (p / "python_embeded" / "python.exe").exists() and (p / "ComfyUI" / "main.py").exists()
    except Exception:
        return False


def detect_root():
    base = app_dir()
    for c in (base, base.parent, base.parent.parent):
        if is_root(c):
            return c
    return None


def resolve_comfy(path):
    """Папка ComfyUI по пути к корню портативки или к самой папке ComfyUI."""
    try:
        p = Path(path)
        if (p / "ComfyUI" / "main.py").exists():
            return p / "ComfyUI"
        if (p / "main.py").exists():
            return p
    except Exception:
        pass
    return None


def find_git(root):
    g = shutil.which("git")
    if g:
        return g
    cands = [Path(r"C:\Program Files\Git\cmd\git.exe"), Path(r"C:\Program Files (x86)\Git\cmd\git.exe")]
    if root:
        cands += [Path(root) / "git" / "cmd" / "git.exe", Path(root) / "PortableGit" / "cmd" / "git.exe"]
    for c in cands:
        if c.exists():
            return str(c)
    return None


def node_base_name(name: str) -> str:
    return name[: -len(".disabled")] if name.endswith(".disabled") else name


def list_node_dirs(comfy: Path):
    cn = Path(comfy) / "custom_nodes"
    if not cn.exists():
        return []
    return sorted([d for d in cn.iterdir() if d.is_dir() and not d.name.startswith((".", "__"))],
                  key=lambda d: d.name.lower())


def parse_repo_url(text: str):
    """Ссылка на репозиторий ноды → dict(name, owner, host, branch, clone, zip, page) или None.
    Понимает: https://github.com/a/b, …/b.git, …/tree/<ветка>, git@github.com:a/b.git, a/b (сокращение GitHub)."""
    t = (text or "").strip().strip('"\'<>').rstrip("/")
    if not t:
        return None
    if re.match(r"^[\w.-]+/[\w.-]+$", t) and "." not in t.split("/")[0]:
        t = "https://github.com/" + t
    elif re.match(r"^(?:www\.)?[\w-]+(?:\.[\w-]+)+/", t, re.I):  # github.com/a/b без https://
        t = "https://" + t
    m = re.match(r"^(?:git\+)?(?:(https?)://(?:www\.)?|git@)([^/:\s]+)[/:]([^/\s]+)/([^/#?\s]+?)(?:\.git)?"
                 r"(?:/(?:tree|blob|src|-/tree)/([^?#\s]+))?/?(?:[?#]\S*)?$", t, re.I)
    if not m:
        return None
    scheme, host, owner, repo, branch = m.groups()
    host = host.lower()
    if not re.match(r"^[\w.-]+$", repo) or repo.lower() in ("archive", "releases"):
        return None
    branch = branch.split("/")[0] if branch else None
    clone = t if (not scheme and t.startswith("git@")) else f"https://{host}/{owner}/{repo}.git"
    zip_url = None
    if host == "github.com":
        zip_url = f"https://github.com/{owner}/{repo}/archive/" + (f"refs/heads/{branch}.zip" if branch else "HEAD.zip")
    return dict(name=repo, owner=owner, host=host, branch=branch, clone=clone, zip=zip_url,
                page=f"https://{host}/{owner}/{repo}")


def split_urls(text: str):
    return [u for u in re.split(r"[\s,;]+", text or "") if u.strip()]


# Скачивание ноды архивом, если git не установлен (запускается через python_embeded).
ZIP_INSTALL_SCRIPT = r"""
import sys, io, os, shutil, tempfile, zipfile, urllib.request
url, dest = sys.argv[1], sys.argv[2]
print("↓", url, flush=True)
req = urllib.request.Request(url, headers={"User-Agent": "ND-Launcher"})
data = urllib.request.urlopen(req, timeout=180).read()
tmp = tempfile.mkdtemp(prefix="nd_node_")
zipfile.ZipFile(io.BytesIO(data)).extractall(tmp)
items = [os.path.join(tmp, d) for d in os.listdir(tmp)]
src = items[0] if len(items) == 1 and os.path.isdir(items[0]) else tmp
shutil.move(src, dest)
print("✓", dest, flush=True)
"""

# ───────────────────────────── загрузка моделей ───────────────────────────────

MODEL_FOLDERS = ["checkpoints", "diffusion_models", "unet", "loras", "vae", "text_encoders", "clip", "clip_vision",
                 "controlnet", "model_patches", "upscale_models", "latent_upscale_models", "embeddings", "LLM",
                 "ipadapter", "style_models", "audio_encoders", "animatediff_models", "hypernetworks"]

CIVITAI_TYPE_FOLDER = {"checkpoint": "checkpoints", "lora": "loras", "locon": "loras", "dora": "loras",
                       "lycoris": "loras", "textualinversion": "embeddings", "vae": "vae", "controlnet": "controlnet",
                       "upscaler": "upscale_models", "hypernetwork": "hypernetworks",
                       "motionmodule": "animatediff_models"}

MODEL_EXTS = (".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin", ".sft", ".onnx")


def suggest_folder(path, model_type="", file_type=""):
    """Папка внутри ComfyUI/models для файла: по типу Civitai, по папкам в репозитории, по имени файла."""
    if (file_type or "").lower() == "vae":
        return "vae"
    mt = re.sub(r"[^a-z]", "", (model_type or "").lower())
    if CIVITAI_TYPE_FOLDER.get(mt):
        return CIVITAI_TYPE_FOLDER[mt]
    path = (path or "").replace("\\", "/")
    for seg in reversed([x.lower() for x in path.split("/")[:-1]]):
        for f in MODEL_FOLDERS:
            if seg == f.lower():
                return f
        if seg in ("text_encoder", "text_encoder_2", "text_encoder_3", "tokenizer_encoder"):
            return "text_encoders"
        if seg in ("transformer", "transformers"):
            return "diffusion_models"
        if seg in ("lora", "lycoris"):
            return "loras"
    name = path.rsplit("/", 1)[-1].lower()
    if not name.endswith(MODEL_EXTS):
        return ""
    if "lora" in name:
        return "loras"
    if re.search(r"(^|[_.-])vae([_.-]|$)|^ae\.", name):
        return "vae"
    if "controlnet" in name:
        return "controlnet"
    if re.search(r"(^|[^a-z0-9])\d+x[^a-z]|esrgan|upscal", name):
        return "upscale_models"
    if name.endswith(".gguf") and re.search(r"instruct|chat|-it[-_.]|gemma|llama|mistral|qwen\d", name):
        return "LLM"
    if re.search(r"t5xxl|umt5|clip_[lg]|text_?enc|qwen_?2\.5_?vl|qwen\d?_?vl|byt5|llava", name):
        return "text_encoders"
    return "diffusion_models"


def parse_model_url(text: str):
    """Ссылка → {"kind": "hf", repo, repo_type, revision, file, subdir} или {"kind": "civitai", host, model_id, version_id}."""
    import urllib.parse
    t = (text or "").strip().strip('"\'<>')
    if not t:
        return None
    m = re.match(r"^(?:https?://)?(?:www\.)?(civitai\.(?:com|red))/(.*)$", t, re.I)
    if m:
        host, rest = m.group(1).lower(), m.group(2)
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit("http://x/" + rest).query))
        mv = re.match(r"api/download/models/(\d+)", rest)
        if mv:
            return dict(kind="civitai", host=host, model_id=None, version_id=int(mv.group(1)))
        mm = re.match(r"models/(\d+)", rest)
        if mm:
            vid = query.get("modelVersionId", "")
            return dict(kind="civitai", host=host, model_id=int(mm.group(1)), version_id=int(vid) if vid.isdigit() else None)
        return None
    m = re.match(r"^(?:https?://)?(?:www\.)?(?:huggingface\.co|hf\.co)/(.*)$", t, re.I)
    if m:
        rest = m.group(1).split("?")[0].split("#")[0].strip("/")
    elif re.match(r"^[\w.-]+/[\w.-]+$", t) and "." not in t.split("/")[0]:
        rest = t
    else:
        return None
    repo_type = "model"
    if rest.startswith("datasets/"):
        repo_type, rest = "dataset", rest[len("datasets/"):]
    elif rest.startswith(("spaces/", "docs/", "api/", "settings/")):
        return None
    parts = rest.split("/")
    if len(parts) < 2 or not all(parts[:2]):
        return None
    info = dict(kind="hf", repo="/".join(parts[:2]), repo_type=repo_type, revision="main", file=None, subdir=None)
    if len(parts) >= 4 and parts[2] in ("blob", "resolve", "tree"):
        info["revision"] = urllib.parse.unquote(parts[3])
        tail = "/".join(urllib.parse.unquote(x) for x in parts[4:]) or None
        info["subdir" if parts[2] == "tree" else "file"] = tail
    return info


class HttpError(Exception):
    def __init__(self, code, msg=""):
        super().__init__(msg or f"HTTP {code}")
        self.code = code


def http_get(url, headers=None, timeout=30):
    import urllib.request
    import urllib.error
    req = urllib.request.Request(url, headers={"User-Agent": f"ND-Launcher/{VERSION}", "Accept": "application/json",
                                               **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.headers
    except urllib.error.HTTPError as e:
        raise HttpError(e.code) from None
    except (urllib.error.URLError, OSError) as e:
        raise HttpError(0, str(getattr(e, "reason", e))) from None


def hf_fetch(info, token=""):
    """Список файлов репозитория Hugging Face (с учётом ветки и подпапки из ссылки)."""
    import urllib.parse
    base = "datasets" if info["repo_type"] == "dataset" else "models"
    url = (f"https://huggingface.co/api/{base}/{info['repo']}/tree/"
           f"{urllib.parse.quote(info['revision'], safe='')}?recursive=true&expand=false")
    hdr = {"Authorization": f"Bearer {token}"} if token else {}
    files, pages = [], 0
    while url and pages < 100:
        body, headers = http_get(url, hdr)
        for it in json.loads(body.decode("utf-8")):
            if it.get("type") != "file":
                continue
            size = (it.get("lfs") or {}).get("size") or it.get("size") or 0
            files.append({"path": it["path"], "size": int(size)})
        m = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", "") or "")
        url = m.group(1) if m else None
        pages += 1
    if info.get("subdir"):
        pre = info["subdir"].rstrip("/") + "/"
        files = [f for f in files if f["path"].startswith(pre)]
    out = []
    for f in sorted(files, key=lambda x: x["path"].lower()):
        out.append(dict(name=f["path"], size=f["size"], note="", folder=suggest_folder(f["path"]),
                        checked=(f["path"] == info.get("file")), hf_path=f["path"]))
    if info.get("file") and not any(f["checked"] for f in out):
        raise HttpError(404)
    title = info["repo"]
    sub = "Hugging Face" + (f" · {info['revision']}" if info["revision"] != "main" else "")
    return dict(source="hf", title=title, subtitle=sub, repo=info["repo"], repo_type=info["repo_type"],
                revision=info["revision"], versions=[dict(id=info["revision"], name=info["revision"], files=out)],
                selected=0)


def _civitai_api(host, path, token):
    hdr = {"Authorization": f"Bearer {token}"} if token else {}
    body, _ = http_get(f"https://{host}/api/v1/{path}", hdr)
    return json.loads(body.decode("utf-8"))


def civitai_fetch(info, token=""):
    """Версии и файлы модели Civitai. civitai.com отдаёт только часть каталога —
    если там модели нет, пробуем civitai.red (тот же аккаунт и те же id)."""
    hosts = [info["host"]] + [h for h in ("civitai.red", "civitai.com") if h != info["host"]]
    last = HttpError(404)
    for host in hosts:
        try:
            if info.get("model_id"):
                model = _civitai_api(host, f"models/{info['model_id']}", token)
            else:
                ver = _civitai_api(host, f"model-versions/{info['version_id']}", token)
                try:
                    model = _civitai_api(host, f"models/{ver['modelId']}", token)
                except HttpError:
                    m = ver.get("model") or {}
                    model = dict(name=m.get("name") or f"#{ver.get('modelId')}", type=m.get("type", ""),
                                 modelVersions=[ver])
            if not model.get("modelVersions"):
                raise HttpError(404)
            return civitai_normalize(model, host, info.get("version_id"))
        except HttpError as e:
            last = e
            if e.code != 404:
                raise
    raise last


def civitai_normalize(model, host, version_id=None):
    mtype = model.get("type") or ""
    versions, selected = [], 0
    for v in model.get("modelVersions") or []:
        files = []
        for f in v.get("files") or []:
            url = f.get("downloadUrl") or v.get("downloadUrl")
            if not url:
                continue
            url = re.sub(r"^https?://(?:www\.)?civitai\.(?:com|red)", f"https://{host}", url)
            meta = f.get("metadata") or {}
            note = " · ".join(str(x) for x in (f.get("type"), meta.get("fp"), meta.get("size"), meta.get("format")) if x)
            size = int(float(f.get("sizeKB") or f.get("sizeKb") or 0) * 1024)
            files.append(dict(name=f.get("name") or f"file_{f.get('id')}", size=size, note=note, url=url,
                              folder=suggest_folder(f.get("name") or "", mtype, f.get("type")),
                              checked=bool(f.get("primary"))))
        if files and not any(x["checked"] for x in files):
            files[0]["checked"] = True
        if version_id and v.get("id") == version_id:
            selected = len(versions)
        label = " · ".join(str(x) for x in (v.get("name"), v.get("baseModel")) if x) or f"#{v.get('id')}"
        versions.append(dict(id=v.get("id"), name=label, files=files))
    return dict(source="civitai", host=host, title=model.get("name") or "Civitai",
                subtitle=f"Civitai · {mtype}" if mtype else "Civitai", versions=versions, selected=selected)


def disk_free(path):
    """(свободно байт, корень диска) для папки, даже если она ещё не создана."""
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return shutil.disk_usage(p).free, (p.anchor or str(p))
    except OSError:
        return None, (p.anchor or str(p))


FOLDER_ALIASES = {"text_encoders": ("clip",), "clip": ("text_encoders",),
                  "diffusion_models": ("unet",), "unet": ("diffusion_models",)}


def _yaml_unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        inner = v[1:-1]
        return inner.replace("\\\\", "\\") if v[0] == '"' else inner
    return v


def _is_abs_path(pth):
    return os.path.isabs(pth) or bool(re.match(r"^[A-Za-z]:[\\/]|^\\\\", pth))


def parse_extra_model_paths(text, yaml_dir):
    """Корни моделей из extra_model_paths.yaml (формат ComfyUI): [{name, base, folders: [(ключ, путь)], default}].
    Без PyYAML: секции верхнего уровня, «ключ: значение» и многострочные значения «|»."""
    sections, cur, block, block_indent = [], None, None, 0
    for raw in (text or "").splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw.rstrip())
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        st = line.strip()
        if block is not None and indent > block_indent:
            block.append(_yaml_unquote(st))
            continue
        block = None
        if indent == 0:
            cur = None
            if st.endswith(":"):
                cur = {"name": _yaml_unquote(st[:-1]), "values": {}}
                sections.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r'^("[^"]*"|\'[^\']*\'|[^:]+?)\s*:\s*(.*)$', st)
        if not m:
            continue
        key, val = _yaml_unquote(m.group(1)), m.group(2).strip()
        if val in ("|", "|-", "|+", ">", ">-"):
            cur["values"][key] = block = []
            block_indent = indent
        else:
            cur["values"][key] = [_yaml_unquote(val)] if val else []
    roots = []
    for sec in sections:
        vals = sec["values"]
        bp = os.path.expandvars(os.path.expanduser((vals.get("base_path") or [""])[0]))
        base = os.path.normpath(bp if _is_abs_path(bp) else os.path.join(yaml_dir, bp))
        folders = []
        for key, paths in vals.items():
            if key in ("base_path", "is_default", "custom_nodes", "download_model_base"):
                continue
            for pth in paths:
                pth = os.path.expandvars(os.path.expanduser(pth))
                if pth:
                    full = os.path.normpath(pth if _is_abs_path(pth) else os.path.join(base, pth))
                    if (key, full) not in folders:
                        folders.append((key, full))
        if folders:
            default = (vals.get("is_default") or ["false"])[0].strip().lower() == "true"
            roots.append(dict(name=sec["name"], base=base, folders=folders, default=default))
    return roots


# Запуск hf CLI внутри python_embeded — работает и со старым huggingface-cli, и с новым hf.
HF_CLI_SHIM = r"""
import sys
try:
    from huggingface_hub.cli.hf import main
except ImportError:
    try:
        from huggingface_hub.commands.huggingface_cli import main
    except ImportError:
        print("huggingface_hub is not installed", flush=True)
        sys.exit(9)
sys.argv = ["hf"] + sys.argv[1:]
sys.exit(main())
"""

# Многопоточная загрузка (Civitai): одна подписанная ссылка на хранилище, файл качается кусками в N соединений.
# Коды выхода: 3 — нет доступа (нужен токен), 4 — не найдено, 5 — ошибка HTTP, 6 — сеть, 7 — размер не совпал.
FAST_DL_SCRIPT = r"""
import os, sys, time, threading, urllib.request, urllib.error, urllib.parse
url, dest, conns = sys.argv[1], sys.argv[2], max(1, min(32, int(sys.argv[3])))
token = os.environ.get("ND_DL_TOKEN", "")
UA = "ND-Launcher"
def fmt(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return ("%.0f %s" if u in ("B", "KB") else "%.1f %s") % (n, u)
        n /= 1024.0
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None
opener = urllib.request.build_opener(NoRedirect)
def req(u, auth, rng=None):
    h = {"User-Agent": UA}
    if auth:
        h["Authorization"] = "Bearer " + auth
    if rng:
        h["Range"] = "bytes=%d-%d" % rng
    return urllib.request.Request(u, headers=h)
cur, auth = url, token
resp = None
try:
    for _ in range(10):
        try:
            resp = opener.open(req(cur, auth, (0, 0)), timeout=60)
            break
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location") if e.code in (301, 302, 303, 307, 308) else None
            if not loc:
                print("HTTP %d" % e.code, flush=True)
                sys.exit(3 if e.code in (401, 403) else 4 if e.code == 404 else 5)
            cur = urllib.parse.urljoin(cur, loc)
            auth = ""  # после редиректа токен не нужен: ссылка на хранилище уже подписана
    else:
        print("too many redirects", flush=True)
        sys.exit(5)
except (urllib.error.URLError, OSError) as e:
    print("network:", e, flush=True)
    sys.exit(6)
status, cr, cl = resp.status, resp.headers.get("Content-Range", ""), resp.headers.get("Content-Length", "")
resp.close()
total = cr.rsplit("/", 1)[-1]
size = int(total) if status == 206 and total.isdigit() else (int(cl) if status == 200 and cl.isdigit() else 0)
ranged = status == 206 and size > 0
tmp = dest + ".ndpart"
if os.path.exists(tmp):
    os.remove(tmp)
done, lock, errors, finished = [0], threading.Lock(), [], threading.Event()
def progress():
    t_last, d_last, speed = time.time(), 0, 0.0
    while not finished.wait(0.5):
        now, d = time.time(), done[0]
        inst = (d - d_last) / max(1e-3, now - t_last)
        speed = inst if speed == 0 else speed * 0.7 + inst * 0.3
        t_last, d_last = now, d
        pct = int(d * 100 / size) if size else 0
        sys.stdout.write("\r%3d%%|%-20s| %s/%s [%s/s]" % (pct, "#" * (pct // 5), fmt(d), fmt(size) if size else "?", fmt(speed)))
        sys.stdout.flush()
threading.Thread(target=progress, daemon=True).start()
if ranged and size > 32 * 1024 * 1024 and conns > 1:
    with open(tmp, "wb") as f:
        f.truncate(size)
    chunk = max(16 * 1024 * 1024, size // (conns * 6))
    queue = [(s, min(s + chunk, size) - 1) for s in range(0, size, chunk)]
    def worker():
        while True:
            with lock:
                if not queue or errors:
                    return
                start, end = queue.pop(0)
            pos, tries = start, 0
            while pos <= end:
                try:
                    with urllib.request.urlopen(req(cur, auth, (pos, end)), timeout=60) as r, open(tmp, "r+b") as f:
                        if r.status != 206:
                            raise IOError("no range support")
                        f.seek(pos)
                        while pos <= end:
                            b = r.read(1 << 20)
                            if not b:
                                break
                            f.write(b)
                            pos += len(b)
                            with lock:
                                done[0] += len(b)
                    if pos <= end:
                        raise IOError("short read")
                except Exception as e:
                    tries += 1
                    if tries > 6:
                        with lock:
                            errors.append(e)
                        return
                    time.sleep(min(2 * tries, 10))
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(conns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
else:
    try:
        with urllib.request.urlopen(req(cur, auth), timeout=60) as r, open(tmp, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                done[0] += len(b)
    except Exception as e:
        errors.append(e)
finished.set()
time.sleep(0.05)
sys.stdout.write("\n")
if errors:
    print("download failed:", errors[0], flush=True)
    sys.exit(6)
if size and os.path.getsize(tmp) != size:
    print("size mismatch", flush=True)
    sys.exit(7)
os.replace(tmp, dest)
print("OK", dest, flush=True)
"""


# ───────────────────────────── токены (шифрование) ────────────────────────────

def _dpapi(data: bytes, encrypt: bool) -> bytes:
    """Windows DPAPI: расшифровать может только этот пользователь Windows на этом компьютере."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    inp = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0x1, ctypes.byref(out)):  # CRYPTPROTECT_UI_FORBIDDEN
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def protect_secret(text: str) -> str:
    if not text:
        return ""
    if sys.platform == "win32":
        try:
            return "dpapi:" + base64.b64encode(_dpapi(text.encode("utf-8"), True)).decode("ascii")
        except Exception:
            pass
    return "b64:" + base64.b64encode(text.encode("utf-8")).decode("ascii")


def unprotect_secret(value: str) -> str:
    try:
        if value.startswith("dpapi:"):
            return _dpapi(base64.b64decode(value[6:]), False).decode("utf-8")
        if value.startswith("b64:"):
            return base64.b64decode(value[4:]).decode("utf-8")
    except Exception:
        return ""
    return value or ""


# ───────────────────────────────── браузеры ───────────────────────────────────

CHROMIUM_EXES = {"chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "launcher.exe", "vivaldi.exe",
                 "browser.exe", "chromium.exe", "thorium.exe", "yandex.exe", "arc.exe"}


def detect_browsers():
    """Установленные браузеры Windows из реестра (StartMenuInternet): [(название, путь к exe)]."""
    if sys.platform != "win32":
        return []
    import winreg
    found, seen = [], set()
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for base in (r"SOFTWARE\Clients\StartMenuInternet", r"SOFTWARE\WOW6432Node\Clients\StartMenuInternet"):
            try:
                root = winreg.OpenKey(hive, base)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    name = winreg.QueryValue(root, sub) or sub
                    cmd = winreg.QueryValue(root, sub + r"\shell\open\command")
                except OSError:
                    continue
                m = re.match(r'\s*"([^"]+)"|\s*(\S+)', cmd or "")
                exe = (m.group(1) or m.group(2)) if m else ""
                if exe and os.path.isfile(exe) and exe.lower() not in seen:
                    seen.add(exe.lower())
                    found.append((name, exe))
            winreg.CloseKey(root)
    return sorted(found, key=lambda x: x[0].lower())


def browser_args(exe, url, app_mode=False):
    name = re.split(r"[\\/]", exe)[-1].lower()
    if app_mode and name in CHROMIUM_EXES:
        return [f"--app={url}"]
    if "firefox" in name or "waterfox" in name or "librewolf" in name:
        return ["-new-tab", url]
    return [url]



def fmt_size(n):
    n = float(n)
    for unit in (tr('Б'), tr('КБ'), tr('МБ'), tr('ГБ')):
        if n < 1024 or unit == tr('ГБ'):
            return f"{n:.0f} {unit}" if unit in (tr('Б'), tr('КБ')) else f"{n:.1f} {unit}"
        n /= 1024


DEFAULT_OPTIONS = dict(vram="", attention="", preview="", fast=False, fp8_unet=False, fp16_vae=False,
                       no_smart_mem=False, reserve_vram=0.0)

BUILTIN_PRESETS = {
    "Стандарт": {},
    "Экономия VRAM": dict(vram="--lowvram", fp8_unet=True, fp16_vae=True, preview="latent2rgb"),
    "Максимум скорости": dict(vram="--highvram", attention="--use-sage-attention", fast=True, preview="auto"),
    "Видео и большие модели": dict(reserve_vram=1.0, no_smart_mem=True, preview="latent2rgb"),
    "Только CPU": dict(vram="--cpu", preview="latent2rgb"),
}
CUSTOM = "Свой"

DEFAULT_CONFIG = dict(
    root="", preset="Стандарт", options=dict(DEFAULT_OPTIONS), listen=False, port=DEFAULT_PORT,
    auto_browser=True, extra_args="", user_presets={}, deps_after_nodes_update=True,
    transfer_source="", transfer_policy="skip", transfer_models_mode="copy", transfer_node_deps=True, transfer_gentle=True,
    transfer_input_mode="copy", transfer_output_mode="copy",
    browser="", browser_app_mode=False,
    hf_token="", civitai_token="", dl_connections=8, dl_xet_hp=False, dl_last_folder="checkpoints", dl_custom_folders=[],
    minimize_to_tray=False, shortcut_name="ComfyUI Neural Dreamer", shortcut_minimized=False,
    arg_manager=True, arg_manager_legacy=True, arg_upload=True,
    example_replace=True, example_custom="",
    install_deps=True, install_history=[], lang="ru", theme=DEFAULT_THEME,
)

VRAM_MODES = [
    ("Авто (по умолчанию)", ""),
    ("Low VRAM — мало видеопамяти", "--lowvram"),
    ("High VRAM — держать модели в VRAM", "--highvram"),
    ("GPU only — всё на видеокарте", "--gpu-only"),
    ("No VRAM — минимум видеопамяти", "--novram"),
    ("Только процессор (CPU)", "--cpu"),
]
ATTENTION_MODES = [
    ("Авто", ""),
    ("PyTorch SDPA", "--use-pytorch-cross-attention"),
    ("SageAttention", "--use-sage-attention"),
    ("FlashAttention", "--use-flash-attention"),
    ("Split cross-attention", "--use-split-cross-attention"),
    ("Quad cross-attention", "--use-quad-cross-attention"),
]
PREVIEW_MODES = [
    ("По умолчанию", ""),
    ("Авто", "auto"),
    ("Latent2RGB — быстро", "latent2rgb"),
    ("TAESD — качественно", "taesd"),
    ("Выключено", "none"),
]

FOLDERS = [
    ("ComfyUI", "ComfyUI"),
    ("Модели", "ComfyUI/models"),
    ("Checkpoints", "ComfyUI/models/checkpoints"),
    ("Diffusion models", "ComfyUI/models/diffusion_models"),
    ("LoRA", "ComfyUI/models/loras"),
    ("VAE", "ComfyUI/models/vae"),
    ("Text encoders", "ComfyUI/models/text_encoders"),
    ("LLM", "ComfyUI/models/LLM"),
    ("Upscale", "ComfyUI/models/upscale_models"),
    ("Кастом-ноды", "ComfyUI/custom_nodes"),
    ("Input", "ComfyUI/input"),
    ("Output", "ComfyUI/output"),
    ("Воркфлоу", "ComfyUI/user/default/workflows"),
    ("Описания (utils)", "utils"),
]

PAGES = [  # ключ, подпись, иконка, обернуть в прокрутку
    ("launch", "Запуск", "launch", True),
    ("console", "Консоль", "console", False),
    ("workflows", "Воркфлоу", "workflows", False),
    ("updates", "Обновления", "updates", True),
    ("install", "Установка нод", "install", True),
    ("models", "Загрузка моделей", "cloud", True),
    ("transfer", "Перенос", "transfer", True),
    ("folders", "Папки и ссылки", "folder", True),
    ("settings", "Настройки", "settings", True),
]


def encode_profile(d) -> str:
    raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_profile(s: str):
    s = s.strip().strip('"')
    return json.loads(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8"))


def parse_cli(argv):
    """--autostart — сразу запустить ComfyUI; --minimized — стартовать свёрнутым;
    --profile=<base64> — настройки запуска, сохранённые в ярлыке."""
    cli = dict(autostart="--autostart" in argv, minimized="--minimized" in argv, profile=None)
    for a in argv:
        if a.startswith("--profile="):
            try:
                cli["profile"] = decode_profile(a.split("=", 1)[1])
            except Exception:
                pass
    return cli


def instance_key() -> str:
    # один экземпляр на каждую папку лаунчера (две разные сборки друг другу не мешают)
    h = hashlib.md5(str(app_dir()).lower().encode("utf-8")).hexdigest()[:10]
    try:
        user = re.sub(r"\W+", "", getpass.getuser()) or "user"
    except Exception:
        user = "user"
    return f"ND_ComfyUI_Launcher_{user}_{h}"


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text("utf-8"))
            if isinstance(data, dict):
                opts = data.pop("options", {}) or {}
                cfg.update(data)
                cfg["options"].update(opts)
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    except Exception:
        pass


# ─────────────────────────── описания воркфлоу (.ndesc) ───────────────────────

NDESC_NOT_FOUND = "Описания воркфлоу не найдены."


def norm_key(s: str) -> str:
    s = str(s).replace("\\", "/").strip().lstrip("./").lower()
    if s.startswith("workflows/"):
        s = s[len("workflows/"):]
    return s


class NDescIndex:
    """Все описания из utils/*.ndesc, объединённые в один индекс."""

    def __init__(self):
        self.files = []        # загруженные файлы
        self.errors = []       # (файл, текст ошибки)
        self.build = {}        # блок "build" из первого файла, где он есть
        self.by_path = {}      # "flux/txt2img.json" -> entry
        self.by_name = {}      # "txt2img.json" -> entry (запасное совпадение по имени файла)
        self.base_dirs = {}    # id(entry) -> папка файла .ndesc (для относительных путей к превью)

    @property
    def loaded(self):
        return bool(self.files)

    @classmethod
    def load(cls, utils_dir: Path):
        idx = cls()
        utils_dir = Path(utils_dir)
        if not utils_dir.is_dir():
            return idx
        files = {f.resolve(): f for pat in ("*.ndesc", "*.ndesc.json") for f in utils_dir.glob(pat)}
        for f in sorted(files.values(), key=lambda x: x.name.lower()):
            try:
                data = json.loads(f.read_text("utf-8-sig"))
                if not isinstance(data, dict) or data.get("format") != "ndesc":
                    raise ValueError(tr('нет поля "format": "ndesc"'))
                ver = int(data.get("version", 1))
                if ver > 1:
                    idx.errors.append((f.name, tr('версия формата {0} новее, чем знает лаунчер — читаю как v1', ver)))
                wfs = data.get("workflows", {})
                if isinstance(wfs, list):  # допускаем и список с полем "file"
                    wfs = {w.get("file", ""): w for w in wfs if isinstance(w, dict)}
                if not isinstance(wfs, dict):
                    raise ValueError(tr('"workflows" должен быть объектом'))
                if not idx.build and isinstance(data.get("build"), dict):
                    idx.build = data["build"]
                for key, entry in wfs.items():
                    if not key or not isinstance(entry, dict):
                        continue
                    k = norm_key(key)
                    entry = dict(entry)
                    entry["_key"] = key
                    idx.by_path[k] = entry
                    idx.by_name.setdefault(k.rsplit("/", 1)[-1], entry)
                    idx.base_dirs[id(entry)] = f.parent
                idx.files.append(f)
            except Exception as e:
                idx.errors.append((f.name, str(e)))
        return idx

    def find(self, rel_path: str):
        k = norm_key(rel_path)
        return self.by_path.get(k) or self.by_name.get(k.rsplit("/", 1)[-1])

    def base_dir(self, entry):
        return self.base_dirs.get(id(entry))


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


# ──────────────────────────────── перенос файлов ──────────────────────────────

class TransferJob:
    def __init__(self, label, src, dst, move=False, exclude=(), policy=None, hardlink=False):
        self.label = label
        self.src = Path(src)
        self.dst = Path(dst)
        self.move = move
        self.hardlink = hardlink  # на том же диске — жёсткая ссылка вместо копии
        self.exclude = tuple(e.strip("/").lower() for e in exclude)
        self.policy = policy  # None -> общая политика


def _make_writable(p: Path):
    try:
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    except Exception:
        pass


GENTLE_BPS = 250 * 1024 * 1024      # потолок скорости в бережном режиме
UNBUFFERED_FROM = 64 * 1024 * 1024  # файлы крупнее копируются без системного кэша


class _Throttle:
    """Ограничивает среднюю скорость копирования (бережный режим)."""

    def __init__(self, bps):
        self.bps = bps
        self.t0 = time.monotonic()
        self.bytes = 0

    def add(self, n):
        if not self.bps:
            return
        self.bytes += n
        ahead = self.bytes / self.bps - (time.monotonic() - self.t0)
        if ahead > 0.02:
            time.sleep(min(ahead, 2.0))


def _copy_windows(src, dst, on_bytes, is_cancelled):
    """CopyFileExW, как в Проводнике: большие файлы без буферизации — системный кэш
    не забивается гигабайтами «грязных» страниц, и компьютер не подвисает."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    LI = ctypes.c_longlong
    Routine = ctypes.WINFUNCTYPE(wintypes.DWORD, LI, LI, LI, LI, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.HANDLE, wintypes.HANDLE, wintypes.LPVOID)
    last = [0]

    def cb(total, done, _ss, _sd, _sn, _reason, _hs, _hd, _data):
        if done > last[0]:
            on_bytes(done - last[0])
            last[0] = done
        return 1 if is_cancelled() else 0  # PROGRESS_CANCEL / PROGRESS_CONTINUE

    routine = Routine(cb)
    cancel = wintypes.BOOL(False)
    flags = 0x00001000 if os.path.getsize(src) >= UNBUFFERED_FROM else 0  # COPY_FILE_NO_BUFFERING
    k32.CopyFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, Routine, wintypes.LPVOID,
                                ctypes.POINTER(wintypes.BOOL), wintypes.DWORD]
    k32.CopyFileExW.restype = wintypes.BOOL
    if not k32.CopyFileExW(str(src), str(dst), routine, None, ctypes.byref(cancel), flags):
        err = ctypes.get_last_error()
        if err == 1235:  # ERROR_REQUEST_ABORTED — отмена из колбэка
            raise InterruptedError
        raise ctypes.WinError(err)


def _copy_portable(src, dst, on_bytes, is_cancelled):
    with open(src, "rb", buffering=0) as fi, open(dst, "wb", buffering=0) as fo:
        while True:
            if is_cancelled():
                raise InterruptedError
            buf = fi.read(16 * 1024 * 1024)
            if not buf:
                break
            fo.write(buf)
            on_bytes(len(buf))
    shutil.copystat(src, dst)


def copy_file(src, dst, on_bytes, is_cancelled):
    if sys.platform == "win32":
        try:
            return _copy_windows(src, dst, on_bytes, is_cancelled)
        except (InterruptedError, PermissionError, FileNotFoundError):
            raise
        except (AttributeError, OSError) as e:
            if getattr(e, "winerror", None) in (112,):  # ERROR_DISK_FULL — не маскируем
                raise
    _copy_portable(src, dst, on_bytes, is_cancelled)


def _same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def background_io(on):
    """Фоновый приоритет ввода-вывода для текущего потока (Windows): копирование уступает
    диск остальным программам. THREAD_MODE_BACKGROUND_BEGIN / _END."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetThreadPriority(k32.GetCurrentThread(), 0x00010000 if on else 0x00020000)
    except Exception:
        pass


def run_transfer(jobs, policy, on_progress, on_log, is_cancelled, gentle=False):
    """Копирует/перемещает файлы по заданиям. policy: skip | newer | replace.
    gentle — фоновый приоритет диска и ограничение скорости.
    Возвращает статистику. Без Qt — можно вызывать откуда угодно."""
    st = dict(copied=0, skipped=0, errors=0, bytes=0, cancelled=False, linked=0)
    throttle = _Throttle(GENTLE_BPS if gentle else 0)
    link_failed_noted = False
    plan = []
    on_progress(0, tr('Подсчёт файлов…'))
    for job in jobs:
        if not job.src.exists():
            on_log(tr('Пропуск «{0}»: нет {1}', job.label, job.src))
            continue
        if job.src.is_file():
            plan.append((job, job.src, job.dst))
            continue
        for dp, dns, fns in os.walk(job.src):
            dns[:] = [d for d in dns if d != "__pycache__"]
            rel_dir = Path(dp).relative_to(job.src)
            for fn in fns:
                rel = (rel_dir / fn).as_posix()
                low = rel.lower()
                if any(low == e or low.startswith(e + "/") for e in job.exclude):
                    continue
                plan.append((job, Path(dp) / fn, job.dst / rel))
            if is_cancelled():
                break
    sizes = []
    for _, s, _ in plan:
        try:
            sizes.append(s.stat().st_size)
        except OSError:
            sizes.append(0)
    total = max(1, sum(sizes))
    done = 0
    last = [0.0]

    def report(cur_done, name):
        now = time.monotonic()
        if now - last[0] > 0.1:
            last[0] = now
            on_progress(min(100, int(cur_done * 100 / total)), f"{name} · {fmt_size(cur_done)} / {fmt_size(total)}")

    on_log(tr('Файлов к переносу: {0}, объём: {1}', len(plan), fmt_size(total if plan else 0)))
    for (job, s, d), size in zip(plan, sizes):
        if is_cancelled():
            st["cancelled"] = True
            break
        pol = job.policy or policy
        try:
            if d.exists() and _same_file(s, d):  # уже та же жёсткая ссылка — копировать нечего
                st["skipped"] += 1
                done += size
                report(done, s.name)
                continue
            if d.exists():
                if pol == "skip" or (pol == "newer" and s.stat().st_mtime <= d.stat().st_mtime + 1):
                    st["skipped"] += 1
                    done += size
                    report(done, s.name)
                    continue
                _make_writable(d)
            d.parent.mkdir(parents=True, exist_ok=True)
            moved = False
            if job.move:
                try:
                    os.replace(s, d)  # тот же диск — мгновенно
                    moved = True
                except OSError:
                    moved = False
            elif job.hardlink:
                tmp = d.with_name(d.name + ".ndlink")
                try:
                    if tmp.exists():
                        tmp.unlink()
                    os.link(s, tmp)
                    os.replace(tmp, d)
                    moved = True
                    st["linked"] += 1
                except OSError:
                    if not link_failed_noted:
                        link_failed_noted = True
                        on_log(tr("Жёсткие ссылки недоступны (другой диск или файловая система) — копирую файлы."))
            if not moved:
                base = done
                prog = [0]
                tmp = d.with_name(d.name + ".ndpart")

                def on_bytes(n, _base=base, _name=s.name):
                    prog[0] += n
                    report(_base + prog[0], _name)
                    throttle.add(n)
                try:
                    copy_file(s, tmp, on_bytes, is_cancelled)
                    os.replace(tmp, d)
                except BaseException:
                    try:
                        tmp.unlink()
                    except Exception:
                        pass
                    raise
                if job.move:
                    _make_writable(s)
                    s.unlink()
            st["copied"] += 1
            st["bytes"] += size
        except InterruptedError:
            st["cancelled"] = True
            break
        except Exception as e:
            st["errors"] += 1
            on_log(tr('Ошибка: {0} → {1}: {2}', s, d, e))
        done += size
        report(done, s.name)
    for job in jobs:  # после перемещения убираем пустые папки в источнике
        if job.move and job.src.is_dir():
            for dp, _dns, _fns in os.walk(job.src, topdown=False):
                try:
                    if not os.listdir(dp) and Path(dp) != job.src:
                        os.rmdir(dp)
                except OSError:
                    pass
    on_progress(100, tr('Готово'))
    return st


def _yaml_sections(text):
    """[(имя секции, текст секции)] — секции верхнего уровня extra_model_paths.yaml с их строками."""
    out, cur = [], None
    for line in (text or "").splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if bare and not bare[0].isspace() and not bare.lstrip().startswith("#") and bare.rstrip().endswith(":"):
            cur = [bare.rstrip()[:-1].strip().strip("\"'"), [line]]
            out.append(cur)
        elif cur is not None:
            cur[1].append(line)
    return [(n, "".join(ls)) for n, ls in out]


def merge_extra_model_paths(src_text, src_dir, dst_text, dst_comfy=None):
    """Перенос extra_model_paths.yaml в другую сборку. Относительные base_path пересчитываются от старой
    папки ComfyUI в абсолютные (иначе в новой сборке они указывали бы не туда). Секции, которые в новой
    сборке уже есть, и секции, указывающие на саму новую сборку, пропускаются.
    Возвращает (новый текст, добавленные имена, пропущенные имена)."""
    have = {n.lower() for n, _ in _yaml_sections(dst_text)}
    dst_real = os.path.normcase(os.path.normpath(str(dst_comfy))) if dst_comfy else None
    added, skipped, blocks = [], [], []
    for name, block in _yaml_sections(src_text):
        lines = block.splitlines(keepends=True)
        bp_idx, bp_val, indent = None, "", "    "
        for i, ln in enumerate(lines[1:], 1):
            m = re.match(r"^(\s+)([\"']?)base_path\2\s*:\s*(.*?)\s*$", ln.rstrip("\r\n"))
            if m:
                bp_idx, indent, bp_val = i, m.group(1), _yaml_unquote(re.sub(r"\s+#.*$", "", m.group(3)))
                break
            if ln.strip() and not ln.lstrip().startswith("#"):
                indent = re.match(r"^(\s*)", ln).group(1) or indent
        raw = os.path.expandvars(os.path.expanduser(bp_val))
        base = os.path.normpath(raw if _is_abs_path(raw) else os.path.join(src_dir, raw))
        if name.lower() in have or (dst_real and os.path.normcase(base) == dst_real):
            skipped.append(name)
            continue
        new_line = f'{indent}base_path: "{base.replace(os.sep, "/").rstrip("/")}/"\n'
        if bp_idx is None:
            lines.insert(1, new_line)
        else:
            lines[bp_idx] = new_line
        text = "".join(lines)
        blocks.append(text if text.endswith("\n") else text + "\n")
        added.append(name)
    if not blocks:
        return dst_text, added, skipped
    head = dst_text if not dst_text or dst_text.endswith("\n") else dst_text + "\n"
    note = "\n# Перенесено ND Launcher из другой сборки\n"
    return head + note + "".join(blocks), added, skipped


def build_extra_paths_block(src_comfy: Path, existing_text: str):
    """Блок для extra_model_paths.yaml, подключающий модели другой сборки. None — если уже подключено."""
    models = Path(src_comfy) / "models"
    subs = sorted(d.name for d in models.iterdir() if d.is_dir()) if models.is_dir() else []
    base = Path(src_comfy).resolve().as_posix().rstrip("/") + "/"
    if f'"{base}"' in existing_text or not subs:
        return None
    tag = re.sub(r"[^a-z0-9]+", "_", (Path(src_comfy).parent.name or "comfy").lower()).strip("_") or "comfy"
    key = f"nd_import_{tag}"
    n = 2
    while re.search(rf"^{re.escape(key)}:", existing_text, re.M):
        key = f"nd_import_{tag}_{n}"
        n += 1
    lines = [tr('\n# Подключено ND Launcher: модели из другой сборки'), f"{key}:", f'    base_path: "{base}"']
    lines += [f'    "{s}": "models/{s}/"' for s in subs]
    return "\n".join(lines) + "\n"


# ─────────────────────────────────── стиль ───────────────────────────────────

QSS = """
QWidget { background: @BG; color: @TEXT; font-family: "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Inter", sans-serif; font-size: 13px; }
QLabel { background: transparent; }
QToolTip { background: @SURFACE2; color: @TEXT; border: 1px solid @CYAN; padding: 6px; border-radius: @R_SM; }

#Header { background: @SURFACE; border-bottom: 1px solid @BORDER; }
#Sidebar { background: @SURFACE; border-right: 1px solid @BORDER; }
#Title { font-size: 20px; font-weight: 800; }
#Subtitle, #Muted { color: @MUTED; }
#PageTitle { font-size: 24px; font-weight: 800; }
#PanelTitle { font-size: 14px; font-weight: 700; color: @CYAN; }
#Mono { font-family: "Cascadia Mono", "Consolas", monospace; color: @TEXT; }

#Panel { background: @SURFACE; border: 1px solid @BORDER; border-radius: @R_PANEL; }
#Pill { background: @SURFACE2; border: 1px solid @BORDER; border-radius: @R_PILL; }
#Pill QLabel { background: transparent; }

QPushButton { background: @SURFACE2; border: 1px solid @BORDER; border-radius: @R_BTN; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { border-color: @CYAN; }
QPushButton:pressed { background: @BORDER; }
QPushButton:disabled { color: @DIS_TEXT; border-color: @DIS_BORDER; background: @DIS_BG; }

QPushButton#Nav { text-align: left; padding: 11px 14px; border: none; border-radius: @R_BTN;
                  background: transparent; color: @MUTED; font-size: 14px; }
QPushButton#Nav:hover { background: @SURFACE2; color: @TEXT; }
QPushButton#Nav:checked { color: @TEXT; border-left: 3px solid @CYAN;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @NAV1, stop:1 @NAV2); }

QPushButton#Primary { border: none; color: @ON_ACCENT; font-size: 15px; font-weight: 800; padding: 14px; border-radius: @R_LG;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @CYAN, stop:1 @PINK); }
QPushButton#Primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @ACC_H1, stop:1 @ACC_H2); }
QPushButton#Primary:disabled { background: @SURFACE2; color: @DIS_TEXT; }
QPushButton#Danger:hover { border-color: @RED; color: @RED; }
QPushButton#Accent { border-color: @PINK; }
QPushButton#Accent:hover { background: @ACC2_SOFT; }

QPushButton#Link { text-align: left; padding: 11px 14px; border-radius: @R_LG; background: @SURFACE2; font-size: 13px; }
QPushButton#Link:hover { border-color: @PINK; background: @LINK_HOVER; }

QPushButton#Lang { padding: 3px 7px; border-radius: @R_SM; font-size: 11px; font-weight: 700; color: @MUTED;
                   background: transparent; border: 1px solid @BORDER; min-width: 22px; }
QPushButton#Lang:hover { color: @TEXT; border-color: @CYAN; }
QPushButton#Lang:checked { color: @ON_ACCENT; border: 1px solid transparent;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @CYAN, stop:1 @PINK); }

QPushButton#ThemeCard { text-align: left; padding: 0; border-radius: @R_LG; background: @SURFACE2; border: 1px solid @BORDER; }
QPushButton#ThemeCard:hover { border-color: @BORDER_STRONG; }
QPushButton#ThemeCard:checked { border: 2px solid @CYAN; background: @SURFACE; }
QPushButton#ThemeCard QLabel { background: transparent; }

QPushButton#Card { text-align: left; padding: 0; border-radius: @R_PANEL; background: @SURFACE; }
QPushButton#Card:hover { border-color: @CYAN; background: @SURFACE2; }
QPushButton#Card QLabel { background: transparent; }
#CardTitle { font-size: 14px; font-weight: 700; }
#CardPath { color: @MUTED; font-size: 11px; }

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background: @SURFACE2; border: 1px solid @BORDER; border-radius: @R_IN; padding: 7px 10px; min-height: 20px;
    selection-background-color: @CYAN; selection-color: #000; }
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover { border-color: @BORDER_STRONG; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus { border-color: @CYAN; }
QComboBox { combobox-popup: 0; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox#CellCombo { padding: 3px 8px; min-height: 0; border-radius: @R_IN; }
#CellHolder { background: transparent; }
QPushButton#Collapse { text-align: left; background: transparent; border: none; padding: 0;
    color: @CYAN; font-size: 14px; font-weight: 700; }
QPushButton#Collapse:hover { color: @TEXT; }
QComboBox QAbstractItemView { background: @SURFACE2; border: 1px solid @BORDER; outline: 0; padding: 4px;
    selection-background-color: @SEL_MID; selection-color: @TEXT; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0; border: none; }

QCheckBox { spacing: 10px; background: transparent; }
QCheckBox::indicator, QTreeWidget::indicator { width: 18px; height: 18px; border-radius: @R_SM; border: 1px solid @BORDER_STRONG; background: @SURFACE2; }
QCheckBox::indicator:hover, QTreeWidget::indicator:hover { border-color: @CYAN; }
QCheckBox::indicator:checked, QTreeWidget::indicator:checked { border: none;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @CYAN, stop:1 @PINK); }

QPlainTextEdit#Console { background: @CONSOLE_BG; border: 1px solid @BORDER; border-radius: @R_LG; padding: 8px;
    selection-background-color: @SEL; }
QTextBrowser#WfView { background: @SURFACE; color: #d3d3e0; border: none; selection-background-color: @SEL; }

QProgressBar { background: @SURFACE2; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; color: transparent; }
QProgressBar::chunk { border-radius: 4px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @CYAN, stop:1 @PINK); }

QTreeWidget, QTableWidget { background: @SURFACE; border: 1px solid @BORDER; border-radius: @R_LG;
    alternate-background-color: @ALT_ROW; gridline-color: @BORDER; outline: 0; }
QTreeWidget::item, QTableWidget::item { padding: 6px 4px; }
QTreeWidget::item:selected, QTableWidget::item:selected { background: @SEL_SOFT; color: @TEXT; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section { background: @SURFACE2; color: @MUTED; border: none; padding: 8px; font-weight: 700; }
QHeaderView::section:horizontal:first { border-top-left-radius: @R_LG; }
QHeaderView::section:horizontal:last { border-top-right-radius: @R_LG; }
QHeaderView::section:horizontal:only-one { border-top-left-radius: @R_LG; border-top-right-radius: @R_LG; }
QTreeWidget > QWidget, QTableWidget > QWidget { background: transparent; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @BORDER; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @MUTED; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @BORDER; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QSplitter::handle { background: @BG; }
QMessageBox, QInputDialog { background: @SURFACE; }
QMenu { background: @SURFACE2; border: 1px solid @BORDER; padding: 6px; }
QMenu::item { padding: 8px 22px 8px 14px; border-radius: @R_SM; }
QMenu::item:selected { background: @SEL_SOFT; }
QMenu::item:disabled { color: @DIS_TEXT; }
QMenu::separator { height: 1px; background: @BORDER; margin: 6px 8px; }
"""


def build_qss():
    s = QSS
    for k in sorted(C, key=len, reverse=True):
        if isinstance(C[k], str):
            s = s.replace("@" + k, C[k])
    return s


def neon_gradient(s):
    g = QLinearGradient(0, 0, s, s)
    g.setColorAt(0, QColor(C["CYAN"]))
    g.setColorAt(1, QColor(C["PINK"]))
    return g


def paint_logo(p: QPainter, s: float):
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    m = max(2.0, s * 0.05)
    r = QRectF(m, m, s - 2 * m, s - 2 * m)
    g = neon_gradient(s)
    p.setPen(QPen(QBrush(g), max(2.0, s / 20)))
    p.setBrush(QColor(C["BG"]))
    p.drawRoundedRect(r, s * 0.22, s * 0.22)
    f = QFont("Segoe UI")
    f.setPixelSize(max(8, int(s * 0.42)))
    f.setWeight(QFont.Weight.Black)
    p.setFont(f)
    p.setPen(QPen(QBrush(g), 1))
    p.drawText(r, Qt.AlignCenter, "ND")


def make_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        paint_logo(p, size)
        p.end()
        icon.addPixmap(pm)
    return icon


def draw_icon(kind, size=20, color=None, gradient=False) -> QPixmap:
    """Векторные иконки в едином стиле (рисуются на сетке 20×20)."""
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    u = size / 20.0
    brush = QBrush(neon_gradient(size)) if gradient else QBrush(QColor(color or C["MUTED"]))
    pen = QPen(brush, 1.7 * u)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    def P(x, y):
        return QPointF(x * u, y * u)

    def poly(*pts, close=True):
        path = QPainterPath(P(*pts[0]))
        for pt in pts[1:]:
            path.lineTo(P(*pt))
        if close:
            path.closeSubpath()
        p.drawPath(path)

    if kind == "launch":
        poly((6.5, 4), (16, 10), (6.5, 16))
    elif kind == "console":
        p.drawRoundedRect(QRectF(2.5 * u, 4 * u, 15 * u, 12 * u), 2.2 * u, 2.2 * u)
        poly((5.8, 8), (8.3, 10), (5.8, 12), close=False)
        p.drawLine(P(10, 12.2), P(14, 12.2))
    elif kind == "workflows":
        for cx, cy in ((5, 5.5), (15, 5.5), (10, 15)):
            p.drawEllipse(P(cx, cy), 2.3 * u, 2.3 * u)
        p.drawLine(P(7.4, 5.5), P(12.6, 5.5))
        p.drawLine(P(6.2, 7.6), P(8.9, 12.9))
        p.drawLine(P(13.8, 7.6), P(11.1, 12.9))
    elif kind == "updates":
        rect = QRectF(4 * u, 4 * u, 12 * u, 12 * u)
        path = QPainterPath()
        path.arcMoveTo(rect, 50)
        path.arcTo(rect, 50, 280)
        p.drawPath(path)
        tip = QPointF(10 * u + 6 * u * math.cos(math.radians(50)), 10 * u - 6 * u * math.sin(math.radians(50)))
        p.drawLine(tip, tip + QPointF(-3.2 * u, 0.2 * u))
        p.drawLine(tip, tip + QPointF(0.4 * u, -3.2 * u))
    elif kind == "transfer":
        p.drawLine(P(3, 7), P(16, 7))
        poly((13, 4), (16, 7), (13, 10), close=False)
        p.drawLine(P(17, 13), P(4, 13))
        poly((7, 10), (4, 13), (7, 16), close=False)
    elif kind == "folder":
        poly((2.5, 5), (7.8, 5), (9.6, 7), (17.5, 7), (17.5, 15.5), (2.5, 15.5))
        p.drawLine(P(2.5, 9.6), P(17.5, 9.6))
    elif kind == "file":
        poly((5, 2.5), (12, 2.5), (15.5, 6), (15.5, 17.5), (5, 17.5))
        poly((12, 2.5), (12, 6), (15.5, 6), close=False)
    elif kind == "cloud":  # облако со стрелкой вниз
        path = QPainterPath(P(6.3, 14.5))
        path.cubicTo(P(2.6, 14.5), P(2.4, 9.2), P(6.1, 9.0))
        path.cubicTo(P(6.6, 4.8), P(12.9, 4.2), P(14.0, 8.3))
        path.cubicTo(P(18.2, 8.2), P(18.6, 14.5), P(14.4, 14.5))
        p.drawPath(path)
        p.drawLine(P(10.2, 9.6), P(10.2, 17.4))
        poly((7.6, 15.0), (10.2, 17.6), (12.8, 15.0), close=False)
    elif kind == "install":  # стрелка вниз в лоток
        p.drawLine(P(10, 3), P(10, 12.5))
        poly((6, 9), (10, 13), (14, 9), close=False)
        poly((3.5, 12), (3.5, 16.5), (16.5, 16.5), (16.5, 12), close=False)
    elif kind == "link":  # «внешняя ссылка»: рамка и стрелка наружу
        poly((9, 4), (4, 4), (4, 16), (16, 16), (16, 11), close=False)
        p.drawLine(P(10, 10), P(16.5, 3.5))
        poly((12, 3.5), (16.5, 3.5), (16.5, 8), close=False)
    elif kind == "settings":
        c = P(10, 10)
        p.drawEllipse(c, 2.4 * u, 2.4 * u)
        p.drawEllipse(c, 5.4 * u, 5.4 * u)
        tooth = QPen(brush, 2.6 * u)
        tooth.setCapStyle(Qt.FlatCap)
        p.setPen(tooth)
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(c + QPointF(math.cos(a) * 5.6 * u, math.sin(a) * 5.6 * u),
                       c + QPointF(math.cos(a) * 8.3 * u, math.sin(a) * 8.3 * u))
    p.end()
    return pm


def nav_icon(kind) -> QIcon:
    ic = QIcon()
    ic.addPixmap(draw_icon(kind, 20, C["MUTED"]), QIcon.Normal, QIcon.Off)
    ic.addPixmap(draw_icon(kind, 20, gradient=True), QIcon.Normal, QIcon.On)
    ic.addPixmap(draw_icon(kind, 20, C["TEXT"]), QIcon.Active, QIcon.Off)
    ic.addPixmap(draw_icon(kind, 20, gradient=True), QIcon.Active, QIcon.On)
    return ic


class NDLogo(QWidget):
    def __init__(self, size=50, parent=None):
        super().__init__(parent)
        self._s = size
        self.setFixedSize(size, size)
        glow = glow_effect(self, C["GLOW1"], 30)
        if glow:
            self.setGraphicsEffect(glow)

    def paintEvent(self, _):
        p = QPainter(self)
        paint_logo(p, self._s)
        p.end()


def panel(title=None):
    frame = QFrame()
    frame.setObjectName("Panel")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(18, 16, 18, 18)
    lay.setSpacing(12)
    if title:
        t = QLabel(title)
        t.setObjectName("PanelTitle")
        lay.addWidget(t)
    return frame, lay


def muted(text, wrap=True):
    l = QLabel(text)
    l.setObjectName("Muted")
    l.setWordWrap(wrap)
    return l


def button(text, slot=None, name=None):
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    if slot:
        b.clicked.connect(slot)
    return b


def reveal_in_explorer(path: Path):
    path = Path(path)
    if sys.platform == "win32" and path.exists():
        subprocess.Popen(f'explorer /select,"{os.path.normpath(str(path))}"')
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent if path.is_file() else path)))


# ─────────────────────────────────── консоль ──────────────────────────────────

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
PROGRESS_RE = re.compile(r"(\d{1,3})%\|")


class Console(QPlainTextEdit):
    line_received = Signal(str, str)
    progress = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(8000)
        self.setUndoRedoEnabled(False)
        f = QFont()
        f.setFamilies(["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "monospace"])
        f.setStyleHint(QFont.Monospace)
        f.setPointSize(10)
        self.setFont(f)
        self._buf = {}
        self._empty = True

    @staticmethod
    def color_for(line: str) -> str:
        low = line.lower()
        if line.startswith("[ND]"):
            return C["PINK"]
        if "traceback" in low or "error" in low or "exception" in low or "failed" in low or "cannot import" in low:
            return C["RED"]
        if "warning" in low or "warn:" in low or "deprecat" in low:
            return C["YELLOW"]
        if "to see the gui go to" in low or "starting server" in low:
            return C["CYAN"]
        if "prompt executed" in low or "successfully" in low or "already up to date" in low:
            return C["GREEN"]
        return C["CONSOLE_TEXT"]

    def append_line(self, text: str, color: str = None):
        sb = self.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        cur = QTextCursor(self.document())
        cur.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color or self.color_for(text)))
        if not self._empty:
            cur.insertBlock()
        cur.insertText(text, fmt)
        self._empty = False
        if at_bottom:
            sb.setValue(sb.maximum())

    def system(self, msg: str, error=False):
        self.append_line(f"[ND] {msg}", C["RED"] if error else C["PINK"])

    def feed(self, data: str, source: str):
        data = ANSI_RE.sub("", data).replace("\r\n", "\n")
        buf = self._buf.get(source, "") + data
        lines = buf.split("\n")
        rest = lines.pop()
        for ln in lines:
            if "\r" in ln:
                segs = [s for s in ln.split("\r") if s.strip()]
                ln = segs[-1] if segs else ""
            m = PROGRESS_RE.search(ln)
            if m:
                self.progress.emit(int(m.group(1)), ln.strip())
            self.append_line(ln)
            self.line_received.emit(ln, source)
        if "\r" in rest:
            segs = [s for s in rest.split("\r") if s.strip()]
            last = segs[-1] if segs else ""
            m = PROGRESS_RE.search(last)
            if m:
                self.progress.emit(int(m.group(1)), last.strip())
            rest = rest.split("\r")[-1]
        self._buf[source] = rest

    def clear_all(self):
        self.clear()
        self._empty = True


# ──────────────────────────────── процессы ────────────────────────────────────

def make_env():
    env = QProcessEnvironment.systemEnvironment()
    env.insert("PYTHONUNBUFFERED", "1")
    env.insert("PYTHONIOENCODING", "utf-8")
    return env


class TaskRunner(QObject):
    """Последовательно выполняет шаги: (подпись, программа, аргументы, папка) или callable."""
    output = Signal(str)
    started = Signal(str)
    finished = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []
        self.title = ""
        self.errors = 0
        self.proc = None
        self.busy = False
        self.last_code = 0

    def run(self, title, steps):
        if self.busy:
            return False
        self.busy = True
        self.title = title
        self.steps = list(steps)
        self.errors = 0
        self.started.emit(title)
        QTimer.singleShot(0, self._next)
        return True

    def _next(self):
        if not self.steps:
            self.busy = False
            self.proc = None
            self.finished.emit(self.title, self.errors)
            return
        st = self.steps.pop(0)
        if callable(st):
            try:
                more = st()
                if more:
                    self.steps[0:0] = list(more)
            except Exception as e:
                self.errors += 1
                self.output.emit(tr('[ND] Ошибка: {0}\n', e))
            QTimer.singleShot(0, self._next)
            return
        label, prog, args, cwd = st[:4]
        extra_env = st[4] if len(st) > 4 else None
        self.output.emit(f"[ND] ▶ {label}\n")
        dec = codecs.getincrementaldecoder("utf-8")("replace")
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        env = make_env()
        for k, v in (extra_env or {}).items():
            env.insert(k, str(v))
        p.setProcessEnvironment(env)
        p.setWorkingDirectory(str(cwd))
        p.readyReadStandardOutput.connect(lambda: self.output.emit(dec.decode(bytes(p.readAllStandardOutput()))))
        p.finished.connect(lambda code, _st=None: self._done(code, label))
        p.errorOccurred.connect(lambda err: self._failed(err, label))
        self.proc = p
        p.start(str(prog), [str(a) for a in args])

    def extend(self, steps):
        """Добавить шаги в конец уже идущей очереди."""
        self.steps.extend(steps)

    def _done(self, code, label):
        self.last_code = code
        if code != 0:
            self.errors += 1
            self.output.emit(tr('\n[ND] ✖ {0}: завершилось с кодом {1}\n', label, code))
        else:
            self.output.emit("\n")
        QTimer.singleShot(0, self._next)

    def _failed(self, err, label):
        if err == QProcess.FailedToStart:
            self.last_code = -1
            self.errors += 1
            self.output.emit(tr('[ND] ✖ {0}: не удалось запустить процесс\n', label))
            QTimer.singleShot(0, self._next)

    def kill(self):
        self.steps = []
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()


class NoWheelComboBox(QComboBox):
    """Значение меняется только через раскрытый список: колесо мыши над полем прокручивает страницу,
    а не переключает пункт. Сам раскрытый список прокручивается как обычно."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, e):
        e.ignore()

    def showPopup(self):
        # список раскрывается вниз от поля и начинается с первого пункта («Другая папка…»), а не с выбранного
        self.setMaxVisibleItems(14)
        super().showPopup()
        self.view().scrollToTop()


class _Bridge(QObject):
    """Доставляет результат фонового потока в GUI-поток."""
    done = Signal(object, object, object)  # (метка, результат, ошибка)


def run_in_thread(bridge, tag, fn):
    import threading

    def work():
        try:
            res, err = fn(), None
        except Exception as e:
            res, err = None, e
        bridge.done.emit(tag, res, err)
    threading.Thread(target=work, daemon=True).start()


class TransferWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str)
    done = Signal(object)

    def __init__(self, jobs, policy, gentle=False):
        super().__init__()
        self.jobs = jobs
        self.policy = policy
        self.gentle = gentle
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        if self.gentle:
            background_io(True)
        try:
            st = run_transfer(self.jobs, self.policy, self.progress.emit, self.log.emit, lambda: self._cancel,
                              gentle=self.gentle)
        except Exception as e:
            self.log.emit(tr('Перенос прерван: {0}', e))
            st = dict(copied=0, skipped=0, errors=1, bytes=0, cancelled=False, linked=0)
        finally:
            if self.gentle:
                background_io(False)
        self.done.emit(st)


class GpuMonitor(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Pill")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 14, 6)
        lay.setSpacing(10)
        self.name = QLabel("GPU")
        self.name.setStyleSheet("font-weight:700;")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setFixedWidth(110)
        self.bar.setTextVisible(False)
        self.info = QLabel(tr('нет данных'))
        self.info.setObjectName("Muted")
        lay.addWidget(self.name)
        lay.addWidget(self.bar)
        lay.addWidget(self.info)
        self.smi = shutil.which("nvidia-smi")
        self.proc = QProcess(self)
        self.proc.finished.connect(self._done)
        if not self.smi:
            self.bar.hide()
            self.info.setText(tr('nvidia-smi не найден'))
            return
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(2000)
        QTimer.singleShot(200, self.poll)

    def poll(self):
        if self.proc.state() != QProcess.NotRunning:
            return
        self.proc.start(self.smi, ["--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                                   "--format=csv,noheader,nounits"])

    def _done(self, *_):
        out = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace").strip().splitlines()
        if not out:
            return
        try:
            name, used, total, util, temp = [x.strip() for x in out[0].split(",")][:5]
            used, total = float(used), float(total)
            self.name.setText(name.replace("NVIDIA ", "").replace("GeForce ", ""))
            self.bar.setValue(int(used / total * 100) if total else 0)
            self.info.setText(tr('{0:.1f}/{1:.1f} ГБ · {2}% · {3}°C', used/1024, total/1024, util, temp))
            self.setToolTip(tr('{0}\nVRAM: {1:.0f} / {2:.0f} МБ\nЗагрузка GPU: {3}%\nТемпература: {4}°C', name, used, total, util, temp))
        except Exception:
            pass


def theme_swatch(tokens, w=112, h=62):
    """Мини-превью темы: фон, боковое меню, строки текста и акцентная кнопка."""
    pm = QPixmap(w * 2, h * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r = float(str(tokens["R_LG"]).rstrip("px") or 6)
    p.setPen(QPen(QColor(tokens["BORDER"]), 1))
    p.setBrush(QColor(tokens["BG"]))
    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(tokens["SURFACE"]))
    p.drawRoundedRect(QRectF(4, 4, 30, h - 8), r / 2, r / 2)
    for i, c in enumerate(("TEXT", "MUTED", "MUTED")):
        p.setBrush(QColor(tokens[c]))
        p.drawRoundedRect(QRectF(42, 9 + i * 9, 58 - i * 14, 4), 2, 2)
    g = QLinearGradient(42, 0, 100, 0)
    g.setColorAt(0, QColor(tokens["CYAN"]))
    g.setColorAt(1, QColor(tokens["PINK"]))
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(42, h - 20, 50, 12), min(r, 6), min(r, 6))
    p.setBrush(QColor(tokens["CYAN"]))
    for i in range(3):
        p.drawRoundedRect(QRectF(8, 10 + i * 10, 22 if i == 0 else 16, 4), 2, 2)
    p.end()
    return pm


class ThemeCard(QPushButton):
    def __init__(self, tid, theme, parent=None):
        super().__init__(parent)
        self.setObjectName("ThemeCard")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)
        sw = QLabel()
        sw.setPixmap(theme_swatch(theme["tokens"]))
        sw.setFixedSize(112, 62)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(tr(theme["name"]))
        t.setObjectName("CardTitle")
        d = QLabel(tr(theme["desc"]))
        d.setObjectName("CardPath")
        d.setWordWrap(True)
        col.addStretch()
        col.addWidget(t)
        col.addWidget(d)
        col.addStretch()
        lay.addWidget(sw)
        lay.addLayout(col, 1)
        for w in (sw, t, d):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)


class Card(QPushButton):
    def __init__(self, icon_kind, title, sub, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(78)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)
        ic = QLabel()
        ic.setPixmap(draw_icon(icon_kind, 28, gradient=True))
        ic.setFixedSize(30, 30)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("CardTitle")
        s = QLabel(sub)
        s.setObjectName("CardPath")
        col.addWidget(t)
        col.addWidget(s)
        lay.addWidget(ic)
        lay.addLayout(col, 1)
        for w in (ic, t, s):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)


# ─────────────────────────────── главное окно ─────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, cli=None):
        super().__init__()
        cli = cli or parse_cli([])
        self.cfg = load_config()
        set_lang(self.cfg.get("lang", "ru"))
        apply_theme(self.cfg.get("theme", DEFAULT_THEME))
        install_qt_translator(get_lang())
        saved = self.cfg.get("root")
        self.root = Path(saved) if saved and is_root(saved) else detect_root()
        if self.root:
            self.cfg["root"] = str(self.root)
        self.proc = None
        self.server_url = None
        self._restart_pending = False
        self._applying = False
        self._dark_applied = False
        self.ndesc = NDescIndex()
        self._model_cache = {}
        self.src_comfy = None
        self._xfer_thread = None
        self._xfer_worker = None
        self._xfer_nodes = []
        self._tray_hint_shown = False
        self.tray = None

        self.tasks = TaskRunner(self)
        self.dl_tasks = TaskRunner(self)   # загрузки моделей идут отдельно и не мешают запуску ComfyUI
        self.model_info = None
        self.dl_queue = []
        self.dl_current = None
        self._fetch_seq = 0
        self._bridge = _Bridge()
        self._bridge.done.connect(self._on_bridge)
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(make_icon())
        self.resize(1240, 940)  # точная высота подгоняется под вкладку «Запуск» при первом показе
        self.setMinimumSize(1000, 660)

        self._build_ui()
        self.tasks.output.connect(lambda s: self.console.feed(s, "task"))
        self.dl_tasks.output.connect(self._on_dl_output)
        self.dl_tasks.started.connect(lambda t: self.console.system(f"━━ {t} ━━"))
        self.dl_tasks.finished.connect(self._on_dl_finished)
        self.tasks.started.connect(self._on_task_started)
        self.tasks.finished.connect(self._on_task_finished)

        self.apply_options(self.cfg["options"])
        self._select_preset(self.cfg.get("preset", "Стандарт"))
        self.set_status("stopped")
        self.console.system(f"{APP_TITLE} v{VERSION}")
        self.refresh_root_state()
        if self.root:
            self.console.system(tr('Сборка: {0}', self.root))
        else:
            self.console.system(tr('Сборка ComfyUI не найдена — укажи папку в «Настройках».'), error=True)
            self.go("settings")
        self._setup_tray()
        if cli["profile"]:
            self.apply_profile(cli["profile"])

    # ── paths ──
    @property
    def python_exe(self):
        return (self.root or Path(".")) / "python_embeded" / "python.exe"

    @property
    def comfy(self):
        return (self.root or Path(".")) / "ComfyUI"

    @property
    def workflows_dir(self):
        return self.comfy / "user" / "default" / "workflows"

    @property
    def utils_dir(self):
        return (self.root or Path(".")) / "utils"

    @property
    def running(self):
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    @property
    def transferring(self):
        return self._xfer_thread is not None

    # ── UI ──
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.page_index = {}
        builders = dict(launch=self._page_launch, console=self._page_console, workflows=self._page_workflows,
                        updates=self._page_updates, install=self._page_install, models=self._page_models, transfer=self._page_transfer, folders=self._page_folders,
                        settings=self._page_settings)
        self._page_contents = []
        for key, _title, _icon, scroll in PAGES:
            page = builders[key]()
            self._page_contents.append(page)
            if scroll:
                sa = QScrollArea()
                sa.setWidgetResizable(True)
                sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                sa.setWidget(page)
                page = sa
            self.page_index[key] = self.stack.addWidget(page)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

    def _fit_min_width(self):
        """Минимальная ширина окна = самая широкая вкладка + меню + полоса прокрутки,
        чтобы содержимое никогда не обрезалось справа."""
        need = max(p.minimumSizeHint().width() for p in self._page_contents)
        need = max(need, self._header.minimumSizeHint().width() - 230)
        self.setMinimumWidth(max(1000, 230 + need + 16))
        self.setMinimumHeight(max(660, (self._header.height() or 78) + self._sidebar.minimumSizeHint().height()))
        self._fit_default_height()

    def _fit_default_height(self):
        """Высота по умолчанию: вкладка «Запуск» видна целиком, без прокрутки.
        Считается по реальному содержимому (учитывает масштаб Windows) и не выходит за пределы экрана."""
        if self.isMaximized() or self.isFullScreen():
            return
        launch = self._page_contents[0]
        header = self._header.height() or 78
        frame = self.frameGeometry().height() - self.geometry().height()  # заголовок окна Windows
        need = header + launch.sizeHint().height() + 8
        scr = self.screen().availableGeometry() if self.screen() else None
        limit = (scr.height() - frame - 8) if scr else need
        h = min(max(self.height(), need), limit)
        if h != self.height():
            self.resize(self.width(), h)
            if scr:  # после увеличения держим окно на экране
                g = self.frameGeometry()
                g.moveCenter(scr.center())
                g.moveTop(max(scr.top(), min(g.top(), scr.bottom() - g.height())))
                self.move(g.topLeft())

    def go(self, key):
        i = self.page_index[key]
        self.nav_buttons[key].setChecked(True)
        self.stack.setCurrentIndex(i)

    def _build_header(self):
        h = QFrame()
        h.setObjectName("Header")
        self._header = h
        h.setFixedHeight(78)
        lay = QHBoxLayout(h)
        lay.setContentsMargins(22, 12, 22, 12)
        lay.setSpacing(16)
        lay.addWidget(NDLogo(50))
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel("ComfyUI Launcher")
        t.setObjectName("Title")
        s = QLabel(BRAND_NAME)
        s.setObjectName("Subtitle")
        col.addStretch()
        col.addWidget(t)
        col.addWidget(s)
        col.addStretch()
        lay.addLayout(col)
        lay.addStretch()
        self.gpu = GpuMonitor()
        lay.addWidget(self.gpu)
        pill = QFrame()
        pill.setObjectName("Pill")
        pl = QHBoxLayout(pill)
        pl.setContentsMargins(14, 6, 16, 6)
        self.status_label = QLabel()
        self.status_label.setTextFormat(Qt.RichText)
        pl.addWidget(self.status_label)
        lay.addWidget(pill)
        return h

    def _build_sidebar(self):
        sb = QFrame()
        sb.setObjectName("Sidebar")
        self._sidebar = sb
        sb.setFixedWidth(230)
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(14, 18, 14, 18)
        lay.setSpacing(4)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for key, title, icon, _ in PAGES:
            b = QPushButton("  " + tr(title))
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setIcon(nav_icon(icon))
            b.setIconSize(QSize(20, 20))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            lay.addWidget(b)
        self.nav_buttons["launch"].setChecked(True)
        lay.addStretch()

        self.btn_start = button(tr('▶   ЗАПУСТИТЬ'), self.start_comfy, "Primary")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        glow = glow_effect(self.btn_start, C["GLOW2"], 28)
        if glow:
            self.btn_start.setGraphicsEffect(glow)
        lay.addWidget(self.btn_start)
        lay.addSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_stop = button(tr('■  Стоп'), self.stop_comfy, "Danger")
        self.btn_restart = button(tr('↻  Рестарт'), self.restart_comfy)
        row.addWidget(self.btn_stop)
        row.addWidget(self.btn_restart)
        lay.addLayout(row)
        lay.addSpacing(2)
        self.btn_open = button(tr('Открыть в браузере'), self.open_browser)
        lay.addWidget(self.btn_open)
        lrow = QHBoxLayout()
        lrow.setSpacing(4)
        self.lang_buttons = {}
        lang_group = QButtonGroup(sb)
        lang_group.setExclusive(True)
        for code, label, full in LANGS:
            lb = QPushButton(label)
            lb.setObjectName("Lang")
            lb.setCheckable(True)
            lb.setChecked(code == get_lang())
            lb.setCursor(Qt.PointingHandCursor)
            lb.setToolTip(full)
            lb.clicked.connect(lambda _=False, c=code: self.set_language(c))
            lang_group.addButton(lb)
            self.lang_buttons[code] = lb
            lrow.addWidget(lb)
        lrow.addStretch()
        ver = muted(f"v{VERSION}", False)
        ver.setAlignment(Qt.AlignCenter)
        lay.addSpacing(6)
        lrow.addWidget(ver)
        lay.addLayout(lrow)
        return sb

    def _new_page(self, title, sub, margins=(26, 22, 26, 22)):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(*margins)
        lay.setSpacing(14)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        lay.addWidget(muted(sub))
        lay.addSpacing(4)
        return page, lay

    # ── страница: запуск ──
    def _page_launch(self):
        page, lay = self._new_page(tr('Запуск'), tr('Выбери пресет или настрой параметры вручную — лаунчер соберёт команду сам.'))

        pr, prl = panel(tr('Пресет'))
        row = QHBoxLayout()
        self.cb_preset = QComboBox()
        self.cb_preset.setMinimumWidth(220)
        self.cb_preset.currentIndexChanged.connect(self._on_preset_changed)
        self.btn_del_preset = button(tr('Удалить'), self.delete_preset, "Danger")
        row.addWidget(self.cb_preset, 1)
        row.addWidget(button(tr('Сохранить как пресет'), self.save_preset))
        row.addWidget(self.btn_del_preset)
        prl.addLayout(row)
        lay.addWidget(pr)
        self._fill_presets()

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        mem, ml = panel(tr('Память и скорость'))
        g = QGridLayout()
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(10)
        self.cb_vram = self._combo(VRAM_MODES, tr('Как ComfyUI распоряжается видеопамятью.\nLow VRAM — если не хватает памяти и ловишь OOM.'))
        self.cb_attn = self._combo(ATTENTION_MODES, tr('Механизм внимания.\nSageAttention быстрее, но должен быть установлен в python_embeded.'))
        self.cb_preview = self._combo(PREVIEW_MODES, tr('Превью картинки в процессе генерации в KSampler.'))
        self.spin_reserve = QDoubleSpinBox()
        self.spin_reserve.setRange(0, 16)
        self.spin_reserve.setSingleStep(0.5)
        self.spin_reserve.setDecimals(1)
        self.spin_reserve.setSuffix(tr(' ГБ'))
        self.spin_reserve.setSpecialValueText(tr('выкл'))
        self.spin_reserve.setToolTip(tr('Сколько VRAM оставить свободной для системы и других программ (--reserve-vram).'))
        self.spin_reserve.valueChanged.connect(self._on_option_changed)
        for r, (lbl, w) in enumerate([(tr('Видеопамять'), self.cb_vram), ("Attention", self.cb_attn),
                                      (tr('Превью'), self.cb_preview), (tr('Резерв VRAM'), self.spin_reserve)]):
            g.addWidget(muted(lbl, False), r, 0)
            g.addWidget(w, r, 1)
        g.setColumnStretch(1, 1)
        ml.addLayout(g)
        grid.addWidget(mem, 0, 0)

        fl, fll = panel(tr('Оптимизации'))
        self.chk_fast = self._check(tr('Fast-режим  (--fast)'), tr('Экспериментальные ускорения: fp16 accumulation, fp8 matmul и т.п.'))
        self.chk_fp8 = self._check(tr('FP8 для UNet  (--fp8_e4m3fn-unet)'), tr('Хранить веса диффузионной модели в fp8 — экономит VRAM.'))
        self.chk_fp16vae = self._check("FP16 VAE  (--fp16-vae)", tr('VAE в половинной точности — быстрее и меньше памяти.'))
        self.chk_nosmart = self._check(tr('Без smart memory  (--disable-smart-memory)'), tr('Агрессивно выгружать модели из VRAM в RAM.'))
        for w in (self.chk_fast, self.chk_fp8, self.chk_fp16vae, self.chk_nosmart):
            fll.addWidget(w)
        fll.addStretch()
        grid.addWidget(fl, 0, 1)

        net, nl = panel(tr('Сеть и браузер'))
        self.chk_listen = self._check(tr('Доступ из локальной сети  (--listen)'), tr('Открыть ComfyUI для других устройств в сети (телефон, второй ПК).'), option=False)
        self.chk_listen.setChecked(bool(self.cfg.get("listen")))
        self.chk_listen.toggled.connect(self._on_misc_changed)
        prow = QHBoxLayout()
        prow.addWidget(muted(tr('Порт'), False))
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(int(self.cfg.get("port", DEFAULT_PORT)))
        self.spin_port.setFixedWidth(110)
        self.spin_port.valueChanged.connect(self._on_misc_changed)
        prow.addWidget(self.spin_port)
        prow.addStretch()
        self.chk_browser = self._check(tr('Открывать браузер после запуска'), tr('Как только сервер поднимется, лаунчер откроет вкладку с ComfyUI.'), option=False)
        self.chk_browser.setChecked(bool(self.cfg.get("auto_browser", True)))
        self.chk_browser.toggled.connect(self._on_misc_changed)
        nl.addWidget(self.chk_listen)
        nl.addLayout(prow)
        nl.addWidget(self.chk_browser)
        nl.addStretch()
        grid.addWidget(net, 1, 0)

        ex, exl = panel(tr('Дополнительные аргументы'))
        self.chk_arg_manager = self._check(tr("ComfyUI-Manager  (--enable-manager)"),
                                           tr("Включает встроенный ComfyUI-Manager. Нужен свежий ComfyUI с pip-версией Manager — "
                                              "в старых сборках с этим флагом ComfyUI может не запуститься."), option=False)
        self.chk_arg_legacy = self._check(tr("Классический интерфейс Manager  (--enable-manager-legacy-ui)"),
                                          tr("Привычное окно Manager вместо нового интерфейса."), option=False)
        self.chk_arg_upload = self._check(tr("Загрузка файлов до 999 МБ  (--max-upload-size 999)"),
                                          tr("Позволяет загружать в ComfyUI большие видео и картинки (по умолчанию лимит 100 МБ)."), option=False)
        for chk, key in ((self.chk_arg_manager, "arg_manager"), (self.chk_arg_legacy, "arg_manager_legacy"),
                         (self.chk_arg_upload, "arg_upload")):
            chk.setChecked(bool(self.cfg.get(key, True)))
            chk.toggled.connect(self._on_misc_changed)
            exl.addWidget(chk)
        self.chk_arg_legacy.setEnabled(self.chk_arg_manager.isChecked())
        self.edit_extra = QLineEdit(self.cfg.get("extra_args", ""))
        self.edit_extra.setPlaceholderText(tr('например:  --cuda-device 0  --output-directory D:\\renders'))
        self.edit_extra.textChanged.connect(self._on_misc_changed)
        exl.addWidget(self.edit_extra)
        exl.addWidget(muted(tr('Любые флаги ComfyUI, которых нет в интерфейсе. Добавляются в конец команды.')))
        exl.addStretch()
        grid.addWidget(ex, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        cmd, cl = panel(tr('Команда запуска'))
        crow = QHBoxLayout()
        self.lbl_cmd = QLabel()
        self.lbl_cmd.setObjectName("Mono")
        self.lbl_cmd.setWordWrap(True)
        self.lbl_cmd.setTextInteractionFlags(Qt.TextSelectableByMouse)
        crow.addWidget(self.lbl_cmd, 1)
        crow.addWidget(button(tr('Копировать'), lambda: QGuiApplication.clipboard().setText(self.command_text())), 0, Qt.AlignTop)
        cl.addLayout(crow)
        srow = QHBoxLayout()
        srow.addWidget(button(tr('Создать ярлык на рабочий стол'), self.open_shortcut_dialog, "Accent"))
        srow.addWidget(muted(tr('Ярлык откроет лаунчер и сразу запустит ComfyUI с этими настройками.')), 1)
        cl.addLayout(srow)
        lay.addWidget(cmd)
        lay.addStretch()
        return page

    # ── страница: консоль ──
    def _page_console(self):
        page, lay = self._new_page(tr('Консоль'), tr('Вывод ComfyUI, обновлений и переноса. Ошибки подсвечиваются красным.'))
        row = QHBoxLayout()
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setFixedWidth(260)
        self.pbar.setTextVisible(False)
        self.lbl_progress = QLabel("")
        self.lbl_progress.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_progress.setObjectName("Mono")
        self.pbar.hide()
        row.addWidget(self.pbar)
        row.addWidget(self.lbl_progress, 1)
        row.addWidget(button(tr('Копировать всё'), lambda: QGuiApplication.clipboard().setText(self.console.toPlainText())))
        row.addWidget(button(tr('Очистить'), lambda: self.console.clear_all()))
        lay.addLayout(row)
        if getattr(self, "console", None) is None:
            self.console = Console()
            self.console.line_received.connect(self._on_line)
            self.console.progress.connect(self._on_progress)
            self._progress_hide = QTimer(self)
            self._progress_hide.setSingleShot(True)
            self._progress_hide.timeout.connect(lambda: (self.pbar.hide(), self.lbl_progress.setText("")))
        lay.addWidget(self.console, 1)
        return page

    # ── страница: воркфлоу ──
    def _page_workflows(self):
        page, lay = self._new_page(tr('Воркфлоу'), tr('Все воркфлоу сборки. Выбери воркфлоу — справа появится описание.'))
        top = QHBoxLayout()
        self.edit_wf_search = QLineEdit()
        self.edit_wf_search.setPlaceholderText(tr('Поиск по названию, категории и тегам…'))
        self.edit_wf_search.textChanged.connect(self.filter_workflows)
        top.addWidget(self.edit_wf_search, 1)
        top.addWidget(button(tr('↻  Обновить'), self.refresh_workflows))
        top.addWidget(button(tr('Открыть папку'), lambda: self._open_dir(self.workflows_dir)))
        lay.addLayout(top)
        self.lbl_wf = muted("")
        lay.addWidget(self.lbl_wf)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(10)
        self.tree_wf = QTreeWidget()
        self.tree_wf.setHeaderLabels([tr('Воркфлоу')])
        self.tree_wf.setAlternatingRowColors(True)
        self.tree_wf.currentItemChanged.connect(lambda cur, _prev: self.show_workflow(cur))
        self.tree_wf.itemDoubleClicked.connect(lambda it, _c: it.data(0, Qt.UserRole) and reveal_in_explorer(Path(it.data(0, Qt.UserRole))))
        split.addWidget(self.tree_wf)

        right, rl = panel()
        self.wf_desc_panel = right
        rl.setContentsMargins(20, 16, 20, 16)
        self.wf_view = QTextBrowser()
        self.wf_view.setObjectName("WfView")
        self.wf_view.setOpenExternalLinks(True)
        pal = self.wf_view.palette()
        pal.setColor(QPalette.Link, QColor(DESC["LINK"]))
        pal.setColor(QPalette.LinkVisited, QColor(DESC["LINK"]))
        pal.setColor(QPalette.Text, QColor(DESC["TEXT"]))
        self.wf_view.setPalette(pal)
        rl.addWidget(self.wf_view, 1)
        brow = QHBoxLayout()
        self.btn_wf_reveal = button(tr('Показать в папке'), lambda: self._current_wf_path() and reveal_in_explorer(self._current_wf_path()))
        self.btn_wf_copy = button(tr('Копировать путь'), lambda: self._current_wf_path() and QGuiApplication.clipboard().setText(str(self._current_wf_path())))
        brow.addWidget(self.btn_wf_reveal)
        brow.addWidget(self.btn_wf_copy)
        brow.addStretch()
        rl.addLayout(brow)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        split.setSizes([380, 620])
        lay.addWidget(split, 1)
        return page

    # ── страница: обновления ──
    def _page_updates(self):
        page, lay = self._new_page(tr('Обновления'), tr('Обновляй ComfyUI и кастом-ноды в один клик. Перед обновлением останови ComfyUI.'))

        cp, cpl = panel("ComfyUI")
        cpl.addWidget(muted(tr('Использует штатный апдейтер портативной сборки (update/update.py). Вариант «+ зависимости» дополнительно ставит пакеты из requirements.txt — нужен, когда после обновления ругается на фронтенд или новые модули.')))
        row = QHBoxLayout()
        row.addWidget(button(tr('⟳  Обновить ComfyUI'), lambda: self.update_comfy(False)))
        row.addWidget(button(tr('⟳  ComfyUI + зависимости'), lambda: self.update_comfy(True)))
        row.addStretch()
        cpl.addLayout(row)
        lay.addWidget(cp)

        np_, npl = panel(tr('Кастом-ноды'))
        top = QHBoxLayout()
        self.lbl_nodes = muted("", False)
        self.lbl_git = QLabel()
        top.addWidget(self.lbl_nodes)
        top.addStretch()
        top.addWidget(self.lbl_git)
        npl.addLayout(top)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr('Нода'), tr('Статус'), "Git", "requirements"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setMinimumHeight(200)
        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in (1, 2, 3):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.tree.itemDoubleClicked.connect(lambda it, _c: self._open_dir(Path(it.data(0, Qt.UserRole))))
        npl.addWidget(self.tree, 1)
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        for text, fn in [(tr('↻  Список'), self.refresh_nodes),
                         (tr('⟳  Обновить все'), lambda: self.update_nodes(all_nodes=True)),
                         (tr('⟳  Выбранные'), lambda: self.update_nodes(all_nodes=False)),
                         (tr('Вкл / Выкл'), self.toggle_nodes),
                         (tr('Зависимости'), self.install_node_deps)]:
            row2.addWidget(button(text, fn))
        row2.addStretch()
        npl.addLayout(row2)
        self.chk_deps = QCheckBox(tr('После обновления нод ставить их зависимости (pip install -r requirements.txt)'))
        self.chk_deps.setChecked(bool(self.cfg.get("deps_after_nodes_update", True)))
        self.chk_deps.toggled.connect(lambda v: self._set_cfg("deps_after_nodes_update", v))
        npl.addWidget(self.chk_deps)
        npl.addWidget(muted(tr('Отключение ноды переименовывает её папку в «имя.disabled» — ComfyUI такие папки пропускает. Двойной клик по ноде открывает её папку.')))
        lay.addWidget(np_, 1)
        return page

    # ── страница: установка нод ──
    def _page_install(self):
        page, lay = self._new_page(tr('Установка нод'), tr('Вставь ссылку на репозиторий кастом-ноды — лаунчер скачает её в custom_nodes и поставит зависимости.'))
        ip, il = panel(tr('Ссылка на репозиторий'))
        self.edit_install = QPlainTextEdit()
        self.edit_install.setPlaceholderText(tr('https://github.com/автор/ComfyUI-Название\nМожно вставить несколько ссылок — каждую с новой строки'))
        self.edit_install.setFixedHeight(92)
        self.edit_install.setTabChangesFocus(True)
        self.edit_install.textChanged.connect(self._update_install_preview)
        il.addWidget(self.edit_install)
        self.lbl_install_preview = QLabel()
        self.lbl_install_preview.setWordWrap(True)
        self.lbl_install_preview.setTextFormat(Qt.RichText)
        il.addWidget(self.lbl_install_preview)
        row = QHBoxLayout()
        self.chk_install_deps = QCheckBox(tr('Установить зависимости (requirements.txt и install.py)'))
        self.chk_install_deps.setChecked(bool(self.cfg.get("install_deps", True)))
        self.chk_install_deps.toggled.connect(lambda v: self._set_cfg("install_deps", v))
        row.addWidget(self.chk_install_deps)
        row.addStretch()
        self.btn_install = button(tr('⇩   Установить ноду'), self.install_nodes, "Accent")
        row.addWidget(self.btn_install)
        il.addLayout(row)
        self.lbl_install_git = QLabel()
        il.addWidget(self.lbl_install_git)
        il.addWidget(muted(tr('Поддерживаются ссылки GitHub (в том числе на ветку: …/tree/dev), GitLab и других git-хостингов, а также короткая запись «автор/репозиторий». После установки перезапусти ComfyUI.')))
        lay.addWidget(ip)

        hp, hl = panel(tr('История установки'))
        self.tree_install = QTreeWidget()
        self.tree_install.setHeaderLabels([tr('Нода'), tr('Результат'), tr('Когда'), tr('Ссылка')])
        self.tree_install.setRootIsDecorated(False)
        self.tree_install.setAlternatingRowColors(True)
        self.tree_install.setMinimumHeight(180)
        h = self.tree_install.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree_install.itemDoubleClicked.connect(lambda it, _c: self._open_install_item(it, folder=True))
        hl.addWidget(self.tree_install, 1)
        hrow = QHBoxLayout()
        hrow.addWidget(button(tr('Открыть папку ноды'), lambda: self._open_install_item(self.tree_install.currentItem(), folder=True)))
        hrow.addWidget(button(tr('Открыть страницу'), lambda: self._open_install_item(self.tree_install.currentItem(), folder=False)))
        hrow.addStretch()
        hrow.addWidget(button(tr('Очистить историю'), self._clear_install_history, "Danger"))
        hl.addLayout(hrow)
        lay.addWidget(hp, 1)
        self._update_install_preview()
        self._fill_install_history()
        return page

    # ── страница: загрузка моделей ──
    def _page_models(self):
        page, lay = self._new_page(tr("Загрузка моделей"), tr("Вставь ссылку на модель с Hugging Face или Civitai — "
                                                               "выбери файлы и папку, лаунчер скачает их в сборку."))
        tp, tl = panel()
        self.btn_tokens = QPushButton()
        self.btn_tokens.setObjectName("Collapse")
        self.btn_tokens.setCheckable(True)
        self.btn_tokens.setCursor(Qt.PointingHandCursor)
        tl.addWidget(self.btn_tokens)
        self.tokens_body = QWidget()
        tbl = QVBoxLayout(self.tokens_body)
        tbl.setContentsMargins(0, 4, 0, 0)
        tbl.setSpacing(10)
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)
        self.edit_hf_token = self._token_edit("hf_token", "hf_…")
        self.edit_civ_token = self._token_edit("civitai_token", tr("ключ API из настроек аккаунта Civitai"))
        for r, (label, edit, url) in enumerate([("Hugging Face", self.edit_hf_token, "https://huggingface.co/settings/tokens"),
                                                ("Civitai", self.edit_civ_token, "https://civitai.com/user/account")]):
            g.addWidget(QLabel(label), r, 0)
            g.addWidget(edit, r, 1)
            show = button(tr("Показать"))
            show.setCheckable(True)
            show.toggled.connect(lambda on, e=edit: e.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
            g.addWidget(show, r, 2)
            g.addWidget(button(tr("Получить токен"), lambda _=False, u=url: self.open_url(u)), r, 3)
        g.setColumnStretch(1, 1)
        tbl.addLayout(g)
        tbl.addWidget(muted(tr("Токены хранятся только на этом компьютере в зашифрованном виде. Hugging Face: нужен для "
                               "закрытых (gated) моделей. Civitai: нужен для большинства загрузок.")))
        tl.addWidget(self.tokens_body)
        self.btn_tokens.toggled.connect(self._toggle_tokens)
        for e in (self.edit_hf_token, self.edit_civ_token):
            e.editingFinished.connect(self._update_tokens_header)
        self._toggle_tokens(False)  # по умолчанию свёрнуто
        lay.addWidget(tp)

        sp, sl = panel(tr("Ссылка на модель"))
        row = QHBoxLayout()
        self.edit_model_url = QLineEdit()
        self.edit_model_url.setPlaceholderText(tr("https://huggingface.co/… или https://civitai.com/models/…"))
        self.edit_model_url.returnPressed.connect(self.fetch_model_info)
        self.btn_fetch = button(tr("Найти файлы"), self.fetch_model_info, "Accent")
        row.addWidget(self.edit_model_url, 1)
        row.addWidget(self.btn_fetch)
        sl.addLayout(row)
        self.lbl_model_info = QLabel()
        self.lbl_model_info.setWordWrap(True)
        self.lbl_model_info.setTextFormat(Qt.RichText)
        sl.addWidget(self.lbl_model_info)
        self.ver_row = QWidget()
        vr = QHBoxLayout(self.ver_row)
        vr.setContentsMargins(0, 0, 0, 0)
        vr.addWidget(muted(tr("Версия"), False))
        self.cb_version = QComboBox()
        self._compact_combo(self.cb_version, 24)
        self.cb_version.currentIndexChanged.connect(self._on_version_changed)
        vr.addWidget(self.cb_version, 1)
        sl.addWidget(self.ver_row)
        lay.addWidget(sp)

        fp, fl = panel(tr("Файлы"))
        frow = QHBoxLayout()
        self.edit_file_filter = QLineEdit()
        self.edit_file_filter.setPlaceholderText(tr("Фильтр: например safetensors или fp8"))
        self.edit_file_filter.textChanged.connect(self._filter_files)
        frow.addWidget(self.edit_file_filter, 1)
        frow.addWidget(button(tr("Отметить видимые"), lambda: self._check_files(True)))
        frow.addWidget(button(tr('Снять'), lambda: self._check_files(False)))
        fl.addLayout(frow)
        self.dl_roots = self._load_model_roots()
        rrow = QHBoxLayout()
        rrow.addWidget(muted(tr("Корень моделей:"), False))
        self.cb_dl_root = NoWheelComboBox()
        self._compact_combo(self.cb_dl_root, 20)
        self.cb_dl_root.setToolTip(tr("Папка ComfyUI, в которую складываются модели. Кроме этой сборки сюда "
                                      "подтягиваются пути из extra_model_paths.yaml."))
        self._fill_root_combo()
        self.cb_dl_root.currentIndexChanged.connect(self._on_root_changed)
        rrow.addWidget(self.cb_dl_root, 1)
        rrow.addWidget(button(tr("↻  Обновить"), self._reload_roots))
        fl.addLayout(rrow)
        self.tree_files = QTreeWidget()
        self.tree_files.setHeaderLabels([tr("Файл"), tr("Размер"), tr("Папка назначения")])
        self.tree_files.setRootIsDecorated(False)
        self.tree_files.setAlternatingRowColors(True)
        self.tree_files.setMinimumHeight(200)
        h = self.tree_files.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Interactive)
        h.resizeSection(2, 230)
        self.tree_files.itemChanged.connect(lambda *_: self._update_dl_summary())
        fl.addWidget(self.tree_files, 1)
        drow = QHBoxLayout()
        drow.addWidget(muted(tr("Назначить для всех (отмеченных):"), False))
        last = self.cfg.get("dl_last_folder") or "checkpoints"
        self.cb_dl_folder = self._folder_combo(key=None if os.path.isabs(last) else last,
                                               path=last if os.path.isabs(last) else None)
        self.cb_dl_folder.currentIndexChanged.connect(lambda _: self._update_dl_summary())
        drow.addWidget(self.cb_dl_folder, 1)
        drow.addWidget(button(tr("Назначить отмеченным"), self._assign_folder))
        fl.addLayout(drow)
        self.lbl_space = QLabel()
        self.lbl_space.setWordWrap(True)
        self.lbl_space.setTextFormat(Qt.RichText)
        fl.addWidget(self.lbl_space)
        orow = QHBoxLayout()
        orow.addWidget(muted(tr("Потоков (Civitai):"), False))
        self.spin_conn = QSpinBox()
        self.spin_conn.setRange(1, 16)
        self.spin_conn.setValue(int(self.cfg.get("dl_connections") or 8))
        self.spin_conn.setFixedWidth(70)
        self.spin_conn.setToolTip(tr("Сколько соединений одновременно качают один файл с Civitai. 8 — оптимально для большинства каналов."))
        self.spin_conn.valueChanged.connect(lambda v: self._set_cfg("dl_connections", v))
        orow.addWidget(self.spin_conn)
        orow.addSpacing(12)
        self.chk_xet_hp = QCheckBox(tr("Высокая скорость Hugging Face"))
        self.chk_xet_hp.setToolTip(tr("HF_XET_HIGH_PERFORMANCE: больше потоков и буферов. Рекомендуется при 64 ГБ ОЗУ и быстром интернете."))
        self.chk_xet_hp.setChecked(bool(self.cfg.get("dl_xet_hp")))
        self.chk_xet_hp.toggled.connect(lambda v: self._set_cfg("dl_xet_hp", v))
        orow.addWidget(self.chk_xet_hp)
        orow.addStretch()
        self.btn_download = button(tr("⇩   Скачать отмеченные"), self.start_downloads, "Accent")
        orow.addWidget(self.btn_download)
        fl.addLayout(orow)
        lay.addWidget(fp, 1)

        qp, ql = panel(tr("Загрузки"))
        prow = QHBoxLayout()
        self.dl_bar = QProgressBar()
        self.dl_bar.setRange(0, 100)
        self.dl_bar.setTextVisible(False)
        self.dl_bar.setFixedWidth(260)
        self.lbl_dl = QLabel("")
        self.lbl_dl.setObjectName("Mono")
        self.lbl_dl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.btn_dl_cancel = button(tr("Отмена"), self.cancel_downloads, "Danger")
        prow.addWidget(self.dl_bar)
        prow.addWidget(self.lbl_dl, 1)
        prow.addWidget(button(tr("Очистить список"), self._clear_dl_queue))
        prow.addWidget(self.btn_dl_cancel)
        ql.addLayout(prow)
        self.tree_dl = QTreeWidget()
        self.tree_dl.setHeaderLabels([tr("Файл"), tr("Куда"), tr("Статус")])
        self.tree_dl.setRootIsDecorated(False)
        self.tree_dl.setAlternatingRowColors(True)
        self.tree_dl.setMinimumHeight(130)
        h = self.tree_dl.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree_dl.itemDoubleClicked.connect(lambda it, _c: it.data(0, Qt.UserRole) and reveal_in_explorer(Path(it.data(0, Qt.UserRole))))
        ql.addWidget(self.tree_dl)
        lay.addWidget(qp)
        self._render_model_info()
        self._render_dl_queue()
        return page

    # ── загрузка моделей: виджеты ──
    def _token_edit(self, key, placeholder):
        e = QLineEdit(unprotect_secret(self.cfg.get(key) or ""))
        e.setEchoMode(QLineEdit.Password)
        e.setPlaceholderText(placeholder)
        e.editingFinished.connect(lambda: self._set_cfg(key, protect_secret(e.text().strip())))
        return e

    def _toggle_tokens(self, on):
        self.tokens_body.setVisible(on)
        self._update_tokens_header()

    def _update_tokens_header(self):
        mark = lambda e: "✓" if e.text().strip() else "—"
        arrow = "▾" if self.btn_tokens.isChecked() else "▸"
        self.btn_tokens.setText(f"{arrow}  {tr('API-токены')}    Hugging Face {mark(self.edit_hf_token)}  ·  "
                                f"Civitai {mark(self.edit_civ_token)}")

    # корни моделей: эта сборка + секции extra_model_paths.yaml
    def _load_model_roots(self):
        roots = []
        yaml = self.comfy / "extra_model_paths.yaml"
        if self.root and yaml.is_file():
            try:
                roots = parse_extra_model_paths(yaml.read_text("utf-8", errors="replace"), str(yaml.parent))
            except Exception as e:
                self.console.system(tr("Не удалось прочитать extra_model_paths.yaml: {0}", e), error=True)
        return roots

    def _fill_root_combo(self):
        cb = self.cb_dl_root
        cb.blockSignals(True)
        cb.clear()
        cb.addItem(tr("Эта сборка") + f"  ({self.comfy / 'models'})", "")
        for r in self.dl_roots:
            cb.addItem(f"{r['name']}  ({r['base']})", r["name"])
            cb.setItemData(cb.count() - 1, "\n".join(f"{k}: {pth}" for k, pth in r["folders"]), Qt.ToolTipRole)
        want = self.cfg.get("dl_root")
        if want is None:  # первый раз — корень с is_default из yaml
            want = next((r["name"] for r in self.dl_roots if r["default"]), "")
        cb.setCurrentIndex(max(0, cb.findData(want)))
        cb.blockSignals(False)

    def _reload_roots(self):
        self.dl_roots = self._load_model_roots()
        self._fill_root_combo()
        self._on_root_changed()
        self.console.system(tr("Корни моделей: эта сборка + {0} из extra_model_paths.yaml", len(self.dl_roots)))

    def _on_root_changed(self, *_):
        self._set_cfg("dl_root", self.cb_dl_root.currentData() or "")
        for v in (self.model_info or {}).get("versions", []):
            for f in v["files"]:
                f["custom"] = None  # ручной выбор относился к старому корню
        self._fill_folder_combo(self.cb_dl_folder, key=self._last_folder_key())
        if self.model_info:
            self._show_version_files()
        else:
            self._update_dl_summary()

    def _current_root_folders(self):
        """[(ключ, абсолютный путь)] для выбранного корня."""
        name = self.cfg.get("dl_root") or ""
        root = next((r for r in getattr(self, "dl_roots", []) if r["name"] == name), None)
        if root:
            return list(root["folders"]), True
        names = list(MODEL_FOLDERS)
        base = self.comfy / "models"
        if self.root and base.is_dir():
            for d in sorted(base.iterdir(), key=lambda x: x.name.lower()):
                if d.is_dir() and not d.name.startswith(".") and d.name not in names:
                    names.append(d.name)
        return [(n, str(base / n)) for n in names], False

    def _last_folder_key(self):
        v = self.cfg.get("dl_last_folder") or "checkpoints"
        return None if os.path.isabs(v) else v

    def _folder_combo(self, key=None, path=None, cell=False):
        cb = NoWheelComboBox()
        if cell:
            cb.setObjectName("CellCombo")
        self._compact_combo(cb, 14)
        cb.activated.connect(lambda i, c=cb: self._on_folder_activated(c, i))
        self._fill_folder_combo(cb, key=key or (None if path else self._last_folder_key()), path=path)
        return cb

    def _fill_folder_combo(self, cb, key=None, path=None):
        folders, external = self._current_root_folders()
        models = self.comfy / "models"
        cb.blockSignals(True)
        cb.clear()
        cb.addItem(tr("Другая папка…"), "__browse__")
        cb.insertSeparator(1)
        for k, pth in folders:
            if external:
                label = k if sum(1 for x, _ in folders if x == k) == 1 else f"{k} · {Path(pth).name}"
            else:
                label = "models\\" + k
            cb.addItem(label, pth)
            cb.setItemData(cb.count() - 1, k, Qt.UserRole + 1)
            cb.setItemData(cb.count() - 1, pth, Qt.ToolTipRole)
        for pth in self.cfg.get("dl_custom_folders") or []:
            if cb.findData(pth) < 0:
                cb.addItem(pth, pth)
                cb.setItemData(cb.count() - 1, pth, Qt.ToolTipRole)
        self._select_folder(cb, key=key, path=path)
        cb.blockSignals(False)

    def _select_folder(self, cb, key=None, path=None):
        i = -1
        if path:
            i = cb.findData(path)
            if i < 0:
                cb.addItem(path, path)
                cb.setItemData(cb.count() - 1, path, Qt.ToolTipRole)
                i = cb.count() - 1
        elif key:
            for k in (key,) + FOLDER_ALIASES.get(key, ()):
                i = next((j for j in range(cb.count()) if cb.itemData(j, Qt.UserRole + 1) == k), -1)
                if i >= 0:
                    break
        if i < 0:  # нет такой папки у корня — первая обычная папка
            i = next((j for j in range(2, cb.count()) if cb.itemData(j) not in (None, "__browse__")), 0)
        cb.setCurrentIndex(i)
        cb.setProperty("prev", i)

    def _on_folder_activated(self, cb, i):
        if cb.itemData(i) != "__browse__":
            cb.setProperty("prev", i)
            return
        start = cb.itemData(int(cb.property("prev") or 2)) or str(self.comfy / "models")
        d = QFileDialog.getExistingDirectory(self, tr("Папка для модели"), str(start))
        if not d:
            cb.setCurrentIndex(int(cb.property("prev") or 2))
            return
        d = os.path.normpath(d)
        known = next((j for j in range(2, cb.count()) if os.path.normcase(str(cb.itemData(j) or "")) == os.path.normcase(d)), -1)
        if known < 0:
            lst = [x for x in (self.cfg.get("dl_custom_folders") or []) if x != d]
            self._set_cfg("dl_custom_folders", ([d] + lst)[:6])
        self._select_folder(cb, path=d)
        self._update_dl_summary()

    @staticmethod
    def _row_combo(tree, it):
        w = tree.itemWidget(it, 2)
        return getattr(w, "combo", None)

    # ── загрузка моделей: поиск файлов ──
    def fetch_model_info(self):
        text = self.edit_model_url.text().strip()
        info = parse_model_url(text)
        if not info:
            self.lbl_model_info.setText(f'<span style="color:{C["RED"]}">' + html.escape(
                tr("Не похоже на ссылку Hugging Face или Civitai.")) + "</span>")
            return
        self._fetch_seq += 1
        seq = self._fetch_seq
        self.btn_fetch.setEnabled(False)
        self.lbl_model_info.setText(f'<span style="color:{C["MUTED"]}">' + html.escape(tr("Ищу файлы…")) + "</span>")
        if info["kind"] == "hf":
            tok = self.edit_hf_token.text().strip()
            run_in_thread(self._bridge, ("fetch", seq, "hf"), lambda: hf_fetch(info, tok))
        else:
            tok = self.edit_civ_token.text().strip()
            run_in_thread(self._bridge, ("fetch", seq, "civitai"), lambda: civitai_fetch(info, tok))

    def _on_bridge(self, tag, result, error):
        if not (isinstance(tag, tuple) and tag[0] == "fetch") or tag[1] != self._fetch_seq:
            return
        self.btn_fetch.setEnabled(True)
        if error is not None:
            self.model_info = None
            self._render_model_info()
            self.lbl_model_info.setText(f'<span style="color:{C["RED"]}">' + html.escape(self._fetch_error(tag[2], error)) + "</span>")
            return
        self.model_info = result
        self._render_model_info()

    def _fetch_error(self, kind, e):
        code = getattr(e, "code", None)
        if code == 401:
            return tr("Нужен токен Hugging Face: модель закрытая (gated) или приватная.") if kind == "hf" \
                else tr("Нужен API-токен Civitai.")
        if code == 403:
            return tr("Нет доступа: открой страницу модели и прими условия использования тем же аккаунтом, что и токен.") \
                if kind == "hf" else tr("Нет доступа: модель требует входа в аккаунт Civitai или раннего доступа.")
        if code == 404:
            return tr("Не найдено. Проверь ссылку.")
        if code == 0:
            return tr("Нет соединения: {0}", e)
        return tr("Ошибка сервера: HTTP {0}", code) if code else tr("Ошибка: {0}", e)

    def _render_model_info(self):
        if not hasattr(self, "tree_files"):
            return
        info = self.model_info
        self.cb_version.blockSignals(True)
        self.cb_version.clear()
        if not info:
            self.lbl_model_info.setText(f'<span style="color:{C["MUTED"]}">' + html.escape(
                tr("Поддерживаются ссылки на репозиторий, папку или файл Hugging Face и страницы моделей Civitai (civitai.com и civitai.red).")) + "</span>")
            self.ver_row.hide()
            self.cb_version.blockSignals(False)
            self.tree_files.clear()
            self._update_dl_summary()
            return
        nfiles = sum(len(v["files"]) for v in info["versions"])
        self.lbl_model_info.setText(f'<b>{html.escape(info["title"])}</b> &nbsp;<span style="color:{C["MUTED"]}">'
                                    f'{html.escape(info["subtitle"])} · ' + html.escape(tr("файлов: {0}", nfiles)) + "</span>")
        for v in info["versions"]:
            self.cb_version.addItem(v["name"], v["id"])
        self.cb_version.setCurrentIndex(info.get("selected", 0))
        self.cb_version.blockSignals(False)
        self.ver_row.setVisible(info["source"] == "civitai" and len(info["versions"]) > 1)
        self._show_version_files()

    def _on_version_changed(self, i):
        if self.model_info and 0 <= i < len(self.model_info["versions"]):
            self.model_info["selected"] = i
            self._show_version_files()

    def _current_files(self):
        if not self.model_info or not self.model_info["versions"]:
            return []
        return self.model_info["versions"][self.model_info.get("selected", 0)]["files"]

    def _show_version_files(self):
        self.tree_files.blockSignals(True)
        self.tree_files.clear()
        default_key = self.cb_dl_folder.currentData(Qt.UserRole + 1)
        for i, f in enumerate(self._current_files()):
            label = f["name"] + (f"   ({f['note']})" if f.get("note") else "")
            it = QTreeWidgetItem([label, fmt_size(f["size"]) if f["size"] else "—", ""])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(0, Qt.Checked if f.get("checked") else Qt.Unchecked)
            it.setData(0, Qt.UserRole, i)
            it.setToolTip(0, f["name"])
            self.tree_files.addTopLevelItem(it)
            cb = self._folder_combo(key=f.get("folder") or default_key, path=f.get("custom"), cell=True)
            cb.currentIndexChanged.connect(lambda _=0: self._update_dl_summary())
            holder = QWidget()
            holder.setObjectName("CellHolder")
            holder.setAttribute(Qt.WA_StyledBackground, True)
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(2, 3, 6, 3)
            hl.addWidget(cb)
            holder.combo = cb
            it.setSizeHint(0, QSize(0, max(34, cb.sizeHint().height() + 8)))
            self.tree_files.setItemWidget(it, 2, holder)
        self.tree_files.blockSignals(False)
        self._filter_files(self.edit_file_filter.text())

    def _filter_files(self, text):
        q = (text or "").strip().lower()
        for i in range(self.tree_files.topLevelItemCount()):
            it = self.tree_files.topLevelItem(i)
            it.setHidden(bool(q) and q not in it.text(0).lower())
        self._update_dl_summary()

    def _check_files(self, on):
        self.tree_files.blockSignals(True)
        for i in range(self.tree_files.topLevelItemCount()):
            it = self.tree_files.topLevelItem(i)
            if not it.isHidden():
                it.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self.tree_files.blockSignals(False)
        self._update_dl_summary()

    def _assign_folder(self):
        path = self.cb_dl_folder.currentData()
        if not path or path == "__browse__":
            return
        self._set_cfg("dl_last_folder", self.cb_dl_folder.currentData(Qt.UserRole + 1) or path)
        for i in range(self.tree_files.topLevelItemCount()):
            it = self.tree_files.topLevelItem(i)
            cb = self._row_combo(self.tree_files, it)
            if cb and it.checkState(0) == Qt.Checked:
                cb.blockSignals(True)
                self._select_folder(cb, path=path)
                cb.blockSignals(False)
        self._update_dl_summary()

    def _checked_rows(self):
        files = self._current_files()
        out = []
        for i in range(self.tree_files.topLevelItemCount()):
            it = self.tree_files.topLevelItem(i)
            idx = it.data(0, Qt.UserRole)
            cb = self._row_combo(self.tree_files, it)
            f = files[idx]
            value = cb.currentData() if cb else None
            if value and value != "__browse__":
                # ручной выбор запоминаем отдельно — переживёт смену темы/языка; подсказка остаётся в f["folder"]
                key = cb.currentData(Qt.UserRole + 1)
                f["custom"] = None if key and key in (f.get("folder"),) + FOLDER_ALIASES.get(f.get("folder") or "", ()) else value
            f["checked"] = it.checkState(0) == Qt.Checked
            if f["checked"] and value and value != "__browse__":
                out.append((f, Path(value)))
        return out

    def _update_dl_summary(self):
        if not hasattr(self, "lbl_space"):
            return
        rows = self._checked_rows() if self.model_info else []
        self.btn_download.setEnabled(bool(rows))
        need = {}
        for f, folder in rows:
            free, anchor = disk_free(folder)
            d = need.setdefault(anchor, [0, free])
            d[0] += f["size"]
        if not rows:
            g = self.cb_dl_folder.currentData()
            if g and g != "__browse__":
                free, anchor = disk_free(Path(g))
                need[anchor] = [0, free]
        parts = []
        for anchor, (n, free) in need.items():
            if free is None:
                parts.append(html.escape(tr("Диск {0}: свободное место неизвестно", anchor)))
                continue
            left = free - n
            color = C["RED"] if left < 0 else (C["YELLOW"] if left < 20 * 1024 ** 3 else C["GREEN"])
            txt = tr("Диск {0}: свободно {1}", anchor, fmt_size(free))
            if n:
                txt += " · " + tr("к загрузке {0}", fmt_size(n))
                if left < 0:
                    txt += " · " + tr("не хватает {0}", fmt_size(-left))
            parts.append(f'<span style="color:{color}">● {html.escape(txt)}</span>')
        head = ""
        if rows:
            head = html.escape(tr("Отмечено файлов: {0}, объём: {1}", len(rows), fmt_size(sum(f["size"] for f, _ in rows)))) + "<br>"
        self.lbl_space.setText(head + "<br>".join(parts))

    # ── загрузка моделей: очередь ──
    def start_downloads(self):
        if not self.root:
            QMessageBox.warning(self, APP_TITLE, tr('Сначала укажи папку сборки ComfyUI в настройках.'))
            return
        rows = self._checked_rows()
        if not rows or not self.model_info:
            QMessageBox.information(self, APP_TITLE, tr("Отметь файлы для загрузки."))
            return
        info = self.model_info
        jobs = []
        for f, folder in rows:
            name = f["name"].replace("\\", "/").rsplit("/", 1)[-1]
            jobs.append(dict(f=f, folder=folder, name=name, dest=folder / name, size=f["size"]))
        existing = [j for j in jobs if j["dest"].exists()]
        if existing:
            box = QMessageBox(self)
            box.setWindowTitle(APP_TITLE)
            box.setText(tr("Эти файлы уже есть:") + "\n\n" + "\n".join(str(j["dest"]) for j in existing[:10])
                        + ("\n…" if len(existing) > 10 else "") + "\n\n" + tr("Перезаписать их?"))
            yes = box.addButton(tr("Перезаписать"), QMessageBox.YesRole)
            skip = box.addButton(tr("Пропустить"), QMessageBox.NoRole)
            box.addButton(tr("Отмена"), QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is skip:
                jobs = [j for j in jobs if j not in existing]
            elif box.clickedButton() is not yes:
                return
        if not jobs:
            return
        short = {}
        for j in jobs:
            free, anchor = disk_free(j["folder"])
            d = short.setdefault(anchor, [0, free])
            d[0] += j["size"]
        lack = [(a, n, fr) for a, (n, fr) in short.items() if fr is not None and n > fr]
        if lack and QMessageBox.question(self, APP_TITLE, "\n".join(
                tr("Диск {0}: нужно {1}, свободно {2}.", a, fmt_size(n), fmt_size(fr)) for a, n, fr in lack)
                + "\n\n" + tr("Места может не хватить. Всё равно начать?")) != QMessageBox.Yes:
            return
        self._set_cfg("dl_last_folder", self.cb_dl_folder.currentData(Qt.UserRole + 1) or self.cb_dl_folder.currentData())
        steps = []
        if info["source"] == "hf":
            if not self.has_package("huggingface_hub"):
                steps.append((tr("Установка huggingface_hub"), self.python_exe,
                              ["-s", "-m", "pip", "install", "huggingface_hub"], self.root))
            elif not self.has_package("hf_xet"):
                steps.append((tr("Установка hf_xet (быстрая загрузка с Hugging Face)"), self.python_exe,
                              ["-s", "-m", "pip", "install", "hf_xet"], self.root))
        for j in jobs:
            q = dict(name=j["name"], dest=j["dest"], folder=j["folder"], size=j["size"], status="queued",
                     source=info["source"])
            self.dl_queue.append(q)
            steps += [lambda q=q: self._dl_begin(q), self._dl_step(q, j["f"], info), lambda q=q: self._dl_finish(q)]
        self._render_dl_queue()
        if self.dl_tasks.busy:
            self.dl_tasks.extend(steps)
            self.console.system(tr("В очередь загрузок добавлено файлов: {0}", len(jobs)))
        else:
            self.dl_tasks.run(tr("Загрузка моделей ({0})", len(jobs)), steps)
        self.update_controls()

    def _dl_step(self, q, f, info):
        if info["source"] == "hf":
            stage = q["folder"] / f".nd_hf_{abs(hash((str(q['dest']), time.time()))) % 10 ** 8}"
            q["stage"], q["hf_path"] = stage, f["hf_path"]
            args = ["-s", "-c", HF_CLI_SHIM, "download", info["repo"], f["hf_path"], "--local-dir", str(stage)]
            if info["revision"] and info["revision"] != "main":
                args += ["--revision", info["revision"]]
            if info["repo_type"] == "dataset":
                args += ["--repo-type", "dataset"]
            env = {"HF_HUB_DISABLE_TELEMETRY": "1", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
                   "HF_HUB_DOWNLOAD_TIMEOUT": "60", "HF_HOME": str(self.root / ".hf_home")}
            tok = self.edit_hf_token.text().strip()
            if tok:
                env["HF_TOKEN"] = tok
            if self.chk_xet_hp.isChecked():
                env["HF_XET_HIGH_PERFORMANCE"] = "1"
            return (f"hf download · {q['name']}", self.python_exe, args, q["folder"], env)
        env = {}
        tok = self.edit_civ_token.text().strip()
        if tok:
            env["ND_DL_TOKEN"] = tok
        return (f"Civitai · {q['name']}", self.python_exe,
                ["-s", "-c", FAST_DL_SCRIPT, f["url"], str(q["dest"]), str(self.spin_conn.value())], q["folder"], env)

    def _dl_begin(self, q):
        q["status"] = "work"
        self.dl_current = q
        try:
            q["folder"].mkdir(parents=True, exist_ok=True)
        except OSError as e:
            q["status"] = "error"
            q["error"] = str(e)
        if hasattr(self, "dl_bar"):
            self.dl_bar.setValue(0)
            self.lbl_dl.setText(q["name"])
        self._render_dl_queue()
        return None

    DL_ERRORS = {3: "Нет доступа: нужен API-токен Civitai или модель требует входа в аккаунт.",
                 4: "Файл не найден на сервере.", 5: "Ошибка сервера.", 6: "Ошибка сети — загрузка прервана.",
                 7: "Файл скачался не полностью.", 9: "Не установлен huggingface_hub.", -1: "Не удалось запустить загрузку."}

    def _dl_finish(self, q):
        code = self.dl_tasks.last_code
        ok = False
        if q["status"] == "error":
            pass
        elif q["source"] == "hf":
            staged = q["stage"] / q["hf_path"]
            if code == 0 and staged.is_file():
                try:
                    os.replace(staged, q["dest"])
                    ok = True
                except OSError as e:
                    q["error"] = str(e)
            shutil.rmtree(q["stage"], ignore_errors=True)
        else:
            ok = code == 0 and q["dest"].is_file()
        if ok:
            q["status"] = "done"
            self.console.system(tr("Скачано: {0}", q["dest"]))
        else:
            q["status"] = "error"
            q.setdefault("error", tr(self.DL_ERRORS.get(code, "Ошибка загрузки (код {0})."), code))
            if q["source"] == "hf" and code == 1:
                q["error"] = tr("Hugging Face вернул ошибку — проверь токен и доступ к модели (подробности в консоли).")
            self.console.system(f"{q['name']}: {q['error']}", error=True)
            self._cleanup_partial(q)
        self.dl_current = None
        self._render_dl_queue()
        return None

    def _cleanup_partial(self, q):
        try:
            part = Path(str(q["dest"]) + ".ndpart")
            if part.exists():
                part.unlink()
        except OSError:
            pass
        if q.get("stage"):
            shutil.rmtree(q["stage"], ignore_errors=True)

    def cancel_downloads(self):
        if not self.dl_tasks.busy:
            return
        self.dl_tasks.kill()
        for q in self.dl_queue:
            if q["status"] in ("queued", "work"):
                if q["status"] == "work":
                    self._cleanup_partial(q)
                q["status"] = "cancelled"
        self.dl_current = None
        self.console.system(tr("Загрузка отменена."))
        self._render_dl_queue()

    def _clear_dl_queue(self):
        self.dl_queue = [q for q in self.dl_queue if q["status"] in ("queued", "work")]
        self._render_dl_queue()

    def _on_dl_output(self, text):
        self.console.feed(text, "dl")
        if not hasattr(self, "dl_bar") or not self.dl_current:
            return
        pcts = re.findall(r"(\d{1,3})%\|", text)
        if pcts:
            self.dl_bar.setValue(min(100, int(pcts[-1])))
        speeds = re.findall(r"([\d.,]+\s*[kKMG]i?B/s)", text)
        if pcts or speeds:
            bits = [self.dl_current["name"]] + ([f"{pcts[-1]}%"] if pcts else []) + (speeds[-1:] if speeds else [])
            self.lbl_dl.setText(" · ".join(bits))

    def _on_dl_finished(self, title, errors):
        done = sum(1 for q in self.dl_queue if q["status"] == "done")
        failed = sum(1 for q in self.dl_queue if q["status"] == "error")
        self.console.system(tr("{0}: скачано {1}, с ошибкой {2}", title, done, failed), error=bool(failed))
        if hasattr(self, "lbl_dl"):
            self.lbl_dl.setText(tr("Готово") if not failed else tr("Есть ошибки — подробности в консоли"))
            self.dl_bar.setValue(100 if not failed else self.dl_bar.value())
        self._render_dl_queue()
        self._update_dl_summary()
        self.update_controls()

    def _render_dl_queue(self):
        if not hasattr(self, "tree_dl"):
            return
        names = {"queued": (tr("в очереди"), C["MUTED"]), "work": (tr("скачивается…"), C["CYAN"]),
                 "done": (tr("✓ готово"), C["GREEN"]), "error": (tr("✗ ошибка"), C["RED"]),
                 "cancelled": (tr("отменено"), C["YELLOW"])}
        self.tree_dl.clear()
        for q in self.dl_queue:
            label, color = names[q["status"]]
            folder = q["folder"]
            try:
                where = "models\\" + folder.resolve().relative_to((self.comfy / "models").resolve()).as_posix().replace("/", "\\")
            except Exception:
                where = str(folder)
            it = QTreeWidgetItem([q["name"] + (f"  ·  {fmt_size(q['size'])}" if q["size"] else ""), where, label])
            it.setForeground(2, QColor(color))
            it.setData(0, Qt.UserRole, str(q["dest"]) if q["status"] == "done" else str(folder))
            if q.get("error"):
                it.setToolTip(2, q["error"])
            self.tree_dl.addTopLevelItem(it)
        busy = self.dl_tasks.busy
        self.btn_dl_cancel.setEnabled(busy)
        self.dl_bar.setVisible(busy or any(q["status"] != "queued" for q in self.dl_queue))

    # ── страница: перенос ──
    def _page_transfer(self):
        page, lay = self._new_page(tr('Перенос'), tr('Перенеси настройки, модели, кастом-ноды и папки Input / Output из другой сборки ComfyUI.'))

        sp, spl = panel(tr('Откуда переносим'))
        row = QHBoxLayout()
        self.edit_src = QLineEdit(self.cfg.get("transfer_source", ""))
        self.edit_src.setPlaceholderText(tr('Корень другой портативной сборки или её папка ComfyUI'))
        self.edit_src.returnPressed.connect(self.scan_source)
        row.addWidget(self.edit_src, 1)
        row.addWidget(button(tr('Обзор…'), self.browse_source))
        row.addWidget(button(tr('Сканировать'), self.scan_source))
        spl.addLayout(row)
        self.lbl_src = muted(tr('Укажи папку другой сборки и нажми «Сканировать».'))
        spl.addWidget(self.lbl_src)
        lay.addWidget(sp)

        body = QHBoxLayout()
        body.setSpacing(14)

        wp, wpl = panel(tr('Что перенести'))
        wp.setMinimumWidth(300)
        wp.setMaximumWidth(400)
        wp.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.chk_t_settings = QCheckBox(tr('Настройки и Manager (папка user)'))
        self.chk_t_settings.setToolTip(tr('Всё из ComfyUI/user, кроме воркфлоу: настройки интерфейса, горячие клавиши, конфиг Manager.'))
        self.chk_t_workflows = QCheckBox(tr('Воркфлоу пользователя'))
        self.chk_t_workflows.setToolTip("ComfyUI/user/default/workflows")
        self.chk_t_models = QCheckBox(tr('Модели (папка models)'))
        self.cb_models_mode = QComboBox()
        for text, data in [(tr('Копировать'), "copy"), (tr("Жёсткие ссылки (мгновенно)"), "hardlink"),
                           (tr('Переместить'), "move"), (tr('Подключить без копирования'), "link")]:
            self.cb_models_mode.addItem(text, data)
        self.cb_models_mode.setToolTip(tr("«Жёсткие ссылки» — если обе сборки на одном диске: перенос мгновенный и не занимает места,\n"
                                          "старую сборку потом можно удалить. На другом диске лаунчер просто скопирует файлы.") + "\n\n" +
                                       tr('«Подключить» добавляет папку моделей другой сборки в extra_model_paths.yaml —\nComfyUI будет видеть модели, а место на диске не тратится.'))
        self._compact_combo(self.cb_models_mode, 12)
        self.cb_models_mode.setCurrentIndex(max(0, self.cb_models_mode.findData(self.cfg.get("transfer_models_mode", "copy"))))
        self.cb_models_mode.currentIndexChanged.connect(lambda _: self._set_cfg("transfer_models_mode", self.cb_models_mode.currentData()))
        self.chk_t_input = QCheckBox(tr('Папка Input'))
        self.chk_t_output = QCheckBox(tr('Папка Output'))
        self.chk_t_yaml = QCheckBox(tr("Файл extra_model_paths.yaml"))
        self.chk_t_yaml.setToolTip(tr("Дополнительные папки моделей из старой сборки. Относительные пути пересчитываются, "
                                      "а если файл в новой сборке уже есть — недостающие секции дописываются в него."))
        self.cb_input_mode = self._file_mode_combo("transfer_input_mode")
        self.cb_output_mode = self._file_mode_combo("transfer_output_mode")
        for w in (self.chk_t_settings, self.chk_t_workflows, self.chk_t_models):
            wpl.addWidget(w)
        mrow = QHBoxLayout()
        mrow.addSpacing(28)
        mrow.addWidget(self.cb_models_mode, 1)
        wpl.addLayout(mrow)
        for chk, cb in ((self.chk_t_input, self.cb_input_mode), (self.chk_t_output, self.cb_output_mode)):
            wpl.addWidget(chk)
            r = QHBoxLayout()
            r.addSpacing(28)
            r.addWidget(cb, 1)
            wpl.addLayout(r)
        wpl.addWidget(self.chk_t_yaml)
        wpl.addSpacing(6)
        wpl.addWidget(muted(tr('Если файл уже есть в текущей сборке:'), False))
        self.cb_policy = QComboBox()
        for text, data in [(tr('Пропускать'), "skip"), (tr('Заменять, если новее'), "newer"), (tr('Заменять всегда'), "replace")]:
            self.cb_policy.addItem(text, data)
        self._compact_combo(self.cb_policy, 12)
        self.cb_policy.setCurrentIndex(max(0, self.cb_policy.findData(self.cfg.get("transfer_policy", "skip"))))
        self.cb_policy.currentIndexChanged.connect(lambda _: self._set_cfg("transfer_policy", self.cb_policy.currentData()))
        wpl.addWidget(self.cb_policy)
        self.chk_gentle = QCheckBox(tr("Бережный режим"))
        self.chk_gentle.setToolTip(tr("Копирование с фоновым приоритетом диска и скоростью до 250 МБ/с:\n"
                                      "компьютер не подвисает, но перенос идёт дольше."))
        self.chk_gentle.setChecked(bool(self.cfg.get("transfer_gentle", True)))
        self.chk_gentle.toggled.connect(lambda v: self._set_cfg("transfer_gentle", v))
        wpl.addWidget(self.chk_gentle)
        wpl.addStretch()
        wpl.addWidget(button(tr('⇄  Перенести выбранное'), self.transfer_selected_items))
        body.addWidget(wp)

        npnl, npl = panel(tr('Кастом-ноды'))
        self.lbl_src_nodes = muted(tr('Ноды появятся после сканирования. Недостающие подсвечиваются и отмечаются автоматически.'))
        npl.addWidget(self.lbl_src_nodes)
        self.tree_src = QTreeWidget()
        self.tree_src.setHeaderLabels([tr('Нода'), tr('В текущей сборке'), "requirements"])
        self.tree_src.setRootIsDecorated(False)
        self.tree_src.setAlternatingRowColors(True)
        self.tree_src.setMinimumHeight(220)
        h = self.tree_src.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree_src.itemChanged.connect(lambda *_: self._update_src_nodes_label())
        npl.addWidget(self.tree_src, 1)
        r1 = QHBoxLayout()
        r1.setSpacing(8)
        r1.addWidget(muted(tr('Отметить:'), False))
        r1.addWidget(button(tr('Недостающие'), lambda: self._mark_src_nodes("missing")))
        r1.addWidget(button(tr('Все'), lambda: self._mark_src_nodes("all")))
        r1.addWidget(button(tr('Снять'), lambda: self._mark_src_nodes("none")))
        r1.addStretch()
        npl.addLayout(r1)
        r2 = QHBoxLayout()
        r2.setSpacing(8)
        r2.addWidget(button(tr('⇄  Перенести недостающие'), lambda: self.transfer_nodes(only_missing=True)))
        r2.addWidget(button(tr('⇄  Перенести отмеченные'), lambda: self.transfer_nodes(only_missing=False)))
        r2.addStretch()
        npl.addLayout(r2)
        self.chk_t_deps = QCheckBox(tr('После переноса поставить зависимости нод'))
        self.chk_t_deps.setToolTip(tr('pip install -r requirements.txt для каждой перенесённой ноды'))
        self.chk_t_deps.setChecked(bool(self.cfg.get("transfer_node_deps", True)))
        self.chk_t_deps.toggled.connect(lambda v: self._set_cfg("transfer_node_deps", v))
        npl.addWidget(self.chk_t_deps)
        body.addWidget(npnl, 1)
        lay.addLayout(body, 1)

        self.xfer_panel, xl = panel()
        xrow = QHBoxLayout()
        self.xfer_bar = QProgressBar()
        self.xfer_bar.setRange(0, 100)
        self.xfer_bar.setTextVisible(False)
        self.xfer_bar.setFixedWidth(260)
        self.lbl_xfer = QLabel("")
        self.lbl_xfer.setObjectName("Mono")
        self.lbl_xfer.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # длинный текст не раздвигает окно
        xrow.addWidget(self.xfer_bar)
        xrow.addWidget(self.lbl_xfer, 1)
        xrow.addWidget(button(tr('Отмена'), self.cancel_transfer, "Danger"))
        xl.addLayout(xrow)
        self.xfer_panel.hide()
        lay.addWidget(self.xfer_panel)
        return page

    # ── страница: папки ──
    def _page_folders(self):
        page, lay = self._new_page(tr('Папки и ссылки'), tr('Быстрый доступ к моделям, нодам и результатам генераций.'))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.folder_cards = []
        cols = 3
        items = [("folder", t, r) for t, r in FOLDERS] + [("file", "extra_model_paths.yaml", "ComfyUI/extra_model_paths.yaml")]
        for i, (kind, title, rel) in enumerate(items):
            c = Card(kind, tr(title), rel.replace("/", "\\"))
            c.clicked.connect(lambda _=False, r=rel: self.open_rel(r))
            grid.addWidget(c, i // cols, i % cols)
            self.folder_cards.append(c)
        for c in range(cols):
            grid.setColumnStretch(c, 1)
        lay.addLayout(grid)

        lp, self.links_layout = panel(tr('{0} · ресурсы', BRAND_NAME))
        self.links_grid = QGridLayout()
        self.links_grid.setSpacing(10)
        self.links_layout.addLayout(self.links_grid)
        lay.addWidget(lp)
        self.rebuild_links()
        lay.addStretch()
        return page

    # ── страница: настройки ──
    def _page_settings(self):
        page, lay = self._new_page(tr('Настройки'), tr('Путь к сборке ComfyUI. Настройки сохраняются в nd_launcher.json рядом с лаунчером.'))

        rp, rl = panel(tr('Сборка ComfyUI'))
        row = QHBoxLayout()
        self.edit_root = QLineEdit(str(self.root or ""))
        self.edit_root.setPlaceholderText(tr('Папка, где лежат python_embeded и ComfyUI'))
        self.edit_root.editingFinished.connect(lambda: self.set_root(self.edit_root.text().strip(), quiet=True))
        row.addWidget(self.edit_root, 1)
        row.addWidget(button(tr('Обзор…'), self.browse_root))
        row.addWidget(button(tr('Найти автоматически'), self.auto_root))
        rl.addLayout(row)
        self.lbl_root = QLabel()
        rl.addWidget(self.lbl_root)
        lay.addWidget(rp)

        brp, brl = panel(tr("Браузер для ComfyUI"))
        brow = QHBoxLayout()
        self.cb_browser = QComboBox()
        self._compact_combo(self.cb_browser, 20)
        self.cb_browser.activated.connect(self._on_browser_chosen)
        brow.addWidget(self.cb_browser, 1)
        brow.addWidget(button(tr('Обзор…'), self.browse_browser))
        brl.addLayout(brow)
        self.chk_app_mode = QCheckBox(tr("Открывать как отдельное приложение (окно без вкладок и адресной строки)"))
        self.chk_app_mode.setToolTip(tr("Только для браузеров на Chromium: Chrome, Edge, Brave, Opera, Vivaldi, Яндекс."))
        self.chk_app_mode.setChecked(bool(self.cfg.get("browser_app_mode")))
        self.chk_app_mode.toggled.connect(lambda v: self._set_cfg("browser_app_mode", v))
        brl.addWidget(self.chk_app_mode)
        lay.addWidget(brp)
        self._fill_browsers()

        xp, xl = panel(tr("Картинка example.png"))
        self.chk_example = QCheckBox(tr("Заменять ComfyUI\\input\\example.png после обновлений ComfyUI"))
        self.chk_example.setToolTip(tr("При каждом обновлении ComfyUI возвращает свою example.png — лаунчер заменит её выбранной картинкой."))
        self.chk_example.setChecked(bool(self.cfg.get("example_replace", True)))
        self.chk_example.toggled.connect(self._on_example_toggled)
        xl.addWidget(self.chk_example)
        xrow = QHBoxLayout()
        xrow.setSpacing(12)
        self.lbl_example_thumb = QLabel()
        self.lbl_example_thumb.setFixedSize(56, 56)
        self.lbl_example_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_example_name = muted("", True)
        xrow.addWidget(self.lbl_example_thumb)
        xrow.addWidget(self.lbl_example_name, 1)
        self.btn_example_pick = button(tr("Выбрать картинку…"), self.pick_example_image)
        self.btn_example_reset = button(tr("Встроенный логотип"), self.reset_example_image)
        xrow.addWidget(self.btn_example_pick)
        xrow.addWidget(self.btn_example_reset)
        xl.addLayout(xrow)
        lay.addWidget(xp)
        self._update_example_ui()

        bp, bl = panel(tr('Поведение лаунчера'))
        self.chk_tray = QCheckBox(tr('Сворачивать в трей'))
        self.chk_tray.setChecked(bool(self.cfg.get("minimize_to_tray")))
        self.chk_tray.toggled.connect(self._on_tray_toggled)
        bl.addWidget(self.chk_tray)
        bl.addWidget(muted(tr('При сворачивании окно прячется в значок у часов, ComfyUI продолжает работать. Клик по значку открывает лаунчер, правый клик — меню. Ярлык с «Запускать в свёрнутом виде» при этой настройке стартует сразу в трее.')))
        lay.addWidget(bp)

        tp, tl = panel(tr("Оформление"))
        trow = QHBoxLayout()
        trow.setSpacing(10)
        self.theme_buttons = {}
        tg = QButtonGroup(page)
        tg.setExclusive(True)
        for tid, th in THEMES.items():
            card = ThemeCard(tid, th)
            card.setChecked(tid == get_theme())
            card.clicked.connect(lambda _=False, t=tid: self.set_theme(t))
            tg.addButton(card)
            self.theme_buttons[tid] = card
            trow.addWidget(card, 1)
        tl.addLayout(trow)
        tl.addWidget(muted(tr("Тема применяется сразу и запоминается.")))
        lay.addWidget(tp)

        ap, al = panel(tr('О лаунчере'))
        al.addWidget(QLabel(f"<b>{APP_TITLE}</b> &nbsp;v{VERSION}"))
        al.addWidget(muted(tr('Сделано для сборок {0}.', BRAND_NAME)))
        lic = QLabel(f'<a href="{REPO_URL}" style="color:{C["CYAN"]}">{REPO_URL.replace("https://", "")}</a>'
                     f' &nbsp;·&nbsp; ' + html.escape(tr("Свободное ПО под лицензией GPL-3.0, без каких-либо гарантий.")))
        lic.setOpenExternalLinks(False)
        lic.linkActivated.connect(self.open_url)
        lic.setWordWrap(True)
        al.addWidget(lic)
        al.addWidget(muted(tr('Конфиг: {0}', CONFIG_PATH)))
        lay.addWidget(ap)
        lay.addStretch()
        return page

    # ── helpers ──
    def _combo(self, items, tip):
        cb = QComboBox()
        for text, data in items:
            cb.addItem(tr(text), data)
        cb.setToolTip(tip)
        self._compact_combo(cb)
        cb.currentIndexChanged.connect(self._on_option_changed)
        return cb

    @staticmethod
    def _compact_combo(cb, chars=16):
        # не даём длинным пунктам раздувать минимальную ширину страницы
        cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        cb.setMinimumContentsLength(chars)
        cb.view().setMinimumWidth(cb.view().sizeHintForColumn(0) + 30)

    def _check(self, text, tip, option=True):
        c = QCheckBox(text)
        c.setToolTip(tip)
        if option:
            c.toggled.connect(self._on_option_changed)
        return c

    def _file_mode_combo(self, cfg_key):
        """Выбор способа переноса для папок Input / Output: копия, жёсткие ссылки или перемещение."""
        cb = QComboBox()
        for text, data in [(tr('Копировать'), "copy"), (tr("Жёсткие ссылки (мгновенно)"), "hardlink"),
                           (tr('Переместить'), "move")]:
            cb.addItem(text, data)
        cb.setToolTip(tr("«Жёсткие ссылки» — если обе сборки на одном диске: перенос мгновенный и не занимает места,\n"
                         "старую сборку потом можно удалить. На другом диске лаунчер просто скопирует файлы."))
        self._compact_combo(cb, 12)
        cb.setCurrentIndex(max(0, cb.findData(self.cfg.get(cfg_key, "copy"))))
        cb.currentIndexChanged.connect(lambda _: self._set_cfg(cfg_key, cb.currentData()))
        return cb

    def _set_cfg(self, key, value):
        self.cfg[key] = value
        save_config(self.cfg)

    def _open_dir(self, path: Path):
        path = Path(path)
        if not path.exists() and self.root:
            path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ── options / presets ──
    def current_options(self):
        return dict(vram=self.cb_vram.currentData(), attention=self.cb_attn.currentData(),
                    preview=self.cb_preview.currentData(), fast=self.chk_fast.isChecked(),
                    fp8_unet=self.chk_fp8.isChecked(), fp16_vae=self.chk_fp16vae.isChecked(),
                    no_smart_mem=self.chk_nosmart.isChecked(), reserve_vram=round(self.spin_reserve.value(), 1))

    def apply_options(self, opts):
        o = dict(DEFAULT_OPTIONS)
        o.update(opts or {})
        self._applying = True
        for cb, key in ((self.cb_vram, "vram"), (self.cb_attn, "attention"), (self.cb_preview, "preview")):
            cb.setCurrentIndex(max(0, cb.findData(o[key])))
        self.chk_fast.setChecked(bool(o["fast"]))
        self.chk_fp8.setChecked(bool(o["fp8_unet"]))
        self.chk_fp16vae.setChecked(bool(o["fp16_vae"]))
        self.chk_nosmart.setChecked(bool(o["no_smart_mem"]))
        self.spin_reserve.setValue(float(o["reserve_vram"] or 0))
        self._applying = False
        self.cfg["options"] = self.current_options()
        save_config(self.cfg)
        self.update_command()

    def _fill_presets(self):
        self.cb_preset.blockSignals(True)
        self.cb_preset.clear()
        for name in BUILTIN_PRESETS:
            self.cb_preset.addItem(tr(name), name)
        for name in self.cfg.get("user_presets", {}):
            self.cb_preset.addItem(f"★  {name}", name)
        self.cb_preset.addItem(tr('— свои настройки —'), CUSTOM)
        self.cb_preset.blockSignals(False)

    def _select_preset(self, name):
        i = self.cb_preset.findData(name)
        if i < 0:
            i = self.cb_preset.findData(CUSTOM)
        self.cb_preset.blockSignals(True)
        self.cb_preset.setCurrentIndex(i)
        self.cb_preset.blockSignals(False)
        self.btn_del_preset.setEnabled(name in self.cfg.get("user_presets", {}))

    def _on_preset_changed(self, _):
        name = self.cb_preset.currentData()
        self.btn_del_preset.setEnabled(name in self.cfg.get("user_presets", {}))
        if name == CUSTOM:
            self._set_cfg("preset", CUSTOM)
            return
        opts = BUILTIN_PRESETS.get(name)
        if opts is None:
            opts = self.cfg.get("user_presets", {}).get(name, {})
        self.cfg["preset"] = name
        self.apply_options(opts)

    def _on_option_changed(self, *_):
        if self._applying:
            return
        if self.cb_preset.currentData() != CUSTOM:
            self._select_preset(CUSTOM)
            self.cfg["preset"] = CUSTOM
        self.cfg["options"] = self.current_options()
        save_config(self.cfg)
        self.update_command()

    def _on_misc_changed(self, *_):
        self.cfg["listen"] = self.chk_listen.isChecked()
        self.cfg["port"] = self.spin_port.value()
        self.cfg["auto_browser"] = self.chk_browser.isChecked()
        self.cfg["extra_args"] = self.edit_extra.text()
        for key, chk in self._flag_checks():
            self.cfg[key] = chk.isChecked()
        self.chk_arg_legacy.setEnabled(self.chk_arg_manager.isChecked())
        save_config(self.cfg)
        self.update_command()

    def _flag_checks(self):
        return [("arg_manager", self.chk_arg_manager), ("arg_manager_legacy", self.chk_arg_legacy),
                ("arg_upload", self.chk_arg_upload)]

    def save_preset(self):
        name, ok = QInputDialog.getText(self, tr('Новый пресет'), tr('Название пресета:'))
        name = (name or "").strip()
        if not ok or not name:
            return
        if name in BUILTIN_PRESETS or name == CUSTOM:
            QMessageBox.warning(self, APP_TITLE, tr('Такое имя занято встроенным пресетом.'))
            return
        self.cfg.setdefault("user_presets", {})[name] = self.current_options()
        self.cfg["preset"] = name
        save_config(self.cfg)
        self._fill_presets()
        self._select_preset(name)
        self.console.system(tr('Пресет «{0}» сохранён', name))

    def delete_preset(self):
        name = self.cb_preset.currentData()
        if name not in self.cfg.get("user_presets", {}):
            return
        if QMessageBox.question(self, APP_TITLE, tr('Удалить пресет «{0}»?', name)) != QMessageBox.Yes:
            return
        del self.cfg["user_presets"][name]
        self.cfg["preset"] = CUSTOM
        save_config(self.cfg)
        self._fill_presets()
        self._select_preset(CUSTOM)

    # ── команда ──
    def build_args(self):
        o = self.current_options()
        args = ["-s", os.path.join("ComfyUI", "main.py"), "--windows-standalone-build", "--disable-auto-launch"]
        flags = dict(self._flag_checks())
        for key, fl in LAUNCH_FLAGS:
            if flags[key].isChecked() and (key != "arg_manager_legacy" or flags["arg_manager"].isChecked()):
                args += fl
        if o["vram"]:
            args.append(o["vram"])
        if o["attention"]:
            args.append(o["attention"])
        if o["preview"]:
            args += ["--preview-method", o["preview"]]
        if o["fast"]:
            args.append("--fast")
        if o["fp8_unet"]:
            args.append("--fp8_e4m3fn-unet")
        if o["fp16_vae"]:
            args.append("--fp16-vae")
        if o["no_smart_mem"]:
            args.append("--disable-smart-memory")
        if o["reserve_vram"] and o["reserve_vram"] > 0:
            args += ["--reserve-vram", f"{o['reserve_vram']:g}"]
        if self.chk_listen.isChecked():
            args.append("--listen")
        if self.spin_port.value() != DEFAULT_PORT:
            args += ["--port", str(self.spin_port.value())]
        extra = self.edit_extra.text().strip()
        if extra:
            try:
                args += [t.strip('"') for t in shlex.split(extra, posix=False)]
            except ValueError:
                args += extra.split()
        return args

    def command_text(self):
        parts = [os.path.join("python_embeded", "python.exe")] + self.build_args()
        return " ".join(f'"{p}"' if " " in p else p for p in parts)

    def update_command(self):
        if hasattr(self, "lbl_cmd"):
            self.lbl_cmd.setText(self.command_text())

    # ── статус ──
    def set_status(self, state):
        port = self.spin_port.value()
        m = {
            "stopped": (C["MUTED"], tr('Остановлен')),
            "starting": (C["YELLOW"], tr('Запускается…')),
            "running": (C["GREEN"], tr('Работает · {0}', self._short_url() or f'127.0.0.1:{port}')),
            "updating": (C["PINK"], tr('Обновление…')),
            "transfer": (C["PINK"], tr('Перенос…')),
        }
        color, text = m[state]
        self.state = state
        self.status_label.setText(f'<span style="color:{color}; font-size:16px;">●</span>&nbsp; <b>{text}</b>')
        if getattr(self, "tray", None):
            self.tray.setToolTip(f"{APP_TITLE}\nComfyUI: {text}")
        self.update_controls()

    def _idle_status(self):
        self.set_status("running" if self.running and self.server_url else ("starting" if self.running else "stopped"))

    def _short_url(self):
        return (self.server_url or "").replace("http://", "").rstrip("/")

    def update_controls(self):
        if not hasattr(self, "btn_start"):
            return
        busy = self.tasks.busy or self.transferring
        self.btn_start.setEnabled(bool(self.root) and not self.running and not busy)
        self.btn_stop.setEnabled(self.running)
        self.btn_restart.setEnabled(self.running)
        self.btn_open.setEnabled(self.running and bool(self.server_url))
        self.btn_start.setText(tr('●   РАБОТАЕТ') if self.running else tr('▶   ЗАПУСТИТЬ'))
        if getattr(self, "tray", None):
            self.act_start.setEnabled(self.btn_start.isEnabled())
            self.act_stop.setEnabled(self.running)
            self.act_browser.setEnabled(self.running and bool(self.server_url))

    # ── ComfyUI ──
    def has_package(self, name):
        site = self.root / "python_embeded" / "Lib" / "site-packages"
        try:
            return any(site.glob(name + "*"))
        except Exception:
            return False

    def start_comfy(self):
        if not self.root:
            QMessageBox.warning(self, APP_TITLE, tr('Сначала укажи папку сборки ComfyUI в настройках.'))
            self.go("settings")
            return
        if self.running or self.tasks.busy or self.transferring:
            return
        o = self.current_options()
        if o["attention"] == "--use-sage-attention" and not self.has_package("sageattention"):
            self.console.system(tr('SageAttention не найден в python_embeded — ComfyUI может не запуститься. Поставь его или выбери другой Attention.'), error=True)
        if o["attention"] == "--use-flash-attention" and not self.has_package("flash_attn"):
            self.console.system(tr('flash_attn не найден в python_embeded — ComfyUI может не запуститься.'), error=True)
        self._ensure_example_image()
        self.console.system(tr('Запуск: ') + self.command_text())
        dec = codecs.getincrementaldecoder("utf-8")("replace")
        p = QProcess(self)
        p.setProgram(str(self.python_exe))
        p.setArguments(self.build_args())
        p.setWorkingDirectory(str(self.root))
        p.setProcessEnvironment(make_env())
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(lambda: self.console.feed(dec.decode(bytes(p.readAllStandardOutput())), "comfy"))
        p.finished.connect(self._on_comfy_finished)
        p.errorOccurred.connect(self._on_comfy_error)
        self.proc = p
        self.server_url = None
        p.start()
        self.set_status("starting")
        self.go("console")

    def stop_comfy(self):
        if self.running:
            self.console.system(tr('Останавливаю ComfyUI…'))
            self.proc.kill()

    def restart_comfy(self):
        if self.running:
            self._restart_pending = True
            self.stop_comfy()
        else:
            self.start_comfy()

    def open_browser(self):
        if self.server_url:
            self.open_url(self.server_url)

    def open_url(self, url):
        """Открывает ComfyUI в выбранном браузере; если он пропал — в системном."""
        exe = self.cfg.get("browser") or ""
        if exe and os.path.isfile(exe):
            try:
                flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0  # DETACHED_PROCESS | NEW_PROCESS_GROUP
                subprocess.Popen([exe] + browser_args(exe, url, bool(self.cfg.get("browser_app_mode"))),
                                 close_fds=True, creationflags=flags)
                return
            except Exception as e:
                self.console.system(tr("Не удалось открыть браузер {0}: {1}", exe, e), error=True)
        elif exe:
            self.console.system(tr("Браузер не найден: {0} — открываю системный.", exe), error=True)
        QDesktopServices.openUrl(QUrl(url))

    def _fill_browsers(self):
        if not hasattr(self, "cb_browser"):
            return
        cur = self.cfg.get("browser") or ""
        items = [(tr("Системный браузер по умолчанию"), "")] + detect_browsers()
        if cur and not any(e.lower() == cur.lower() for _, e in items):
            items.append((re.split(r"[\\/]", cur)[-1], cur))
        self.cb_browser.blockSignals(True)
        self.cb_browser.clear()
        for name, exe in items:
            self.cb_browser.addItem(name, exe)
            if exe:
                self.cb_browser.setItemData(self.cb_browser.count() - 1, exe, Qt.ToolTipRole)
        idx = next((i for i, (_, e) in enumerate(items) if e.lower() == cur.lower()), 0)
        self.cb_browser.setCurrentIndex(idx)
        self.cb_browser.blockSignals(False)
        self._update_app_mode()

    def _update_app_mode(self):
        exe = self.cb_browser.currentData() or ""
        ok = bool(exe) and re.split(r"[\\/]", exe)[-1].lower() in CHROMIUM_EXES
        self.chk_app_mode.setEnabled(ok)

    # ── example.png ──
    CUSTOM_EXAMPLE = "nd_example_custom.png"

    def _update_example_ui(self):
        custom = self.cfg.get("example_custom") or ""
        src = Path(custom) if custom and Path(custom).is_file() else brand_dir() / "example.png"
        pm = QPixmap(str(src))
        self.lbl_example_thumb.setPixmap(pm.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation) if not pm.isNull() else QPixmap())
        self.lbl_example_name.setText(tr("Своя картинка") if custom else tr("Встроенный логотип {0}", BRAND_NAME))
        on = self.chk_example.isChecked()
        for w in (self.lbl_example_thumb, self.lbl_example_name, self.btn_example_pick):
            w.setEnabled(on)
        self.btn_example_reset.setEnabled(on and bool(custom))

    def _on_example_toggled(self, on):
        self._set_cfg("example_replace", bool(on))
        self._update_example_ui()

    def pick_example_image(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("Картинка для example.png"), "",
                                           tr("Картинки") + " (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not f:
            return
        img = QImage(f)
        if img.isNull():
            QMessageBox.warning(self, APP_TITLE, tr("Не удалось открыть картинку."))
            return
        dst = app_dir() / self.CUSTOM_EXAMPLE  # копия в PNG рядом с лаунчером: исходник можно двигать и удалять
        if not img.save(str(dst), "PNG"):
            QMessageBox.warning(self, APP_TITLE, tr("Не удалось сохранить картинку: {0}", dst))
            return
        self._set_cfg("example_custom", str(dst))
        self._update_example_ui()
        if self.root:
            self.replace_example_image()

    def reset_example_image(self):
        self._set_cfg("example_custom", "")
        try:
            (app_dir() / self.CUSTOM_EXAMPLE).unlink()
        except OSError:
            pass
        self._update_example_ui()
        if self.root:
            self.replace_example_image()

    def _on_browser_chosen(self, _i):
        self._set_cfg("browser", self.cb_browser.currentData() or "")
        self._update_app_mode()

    def browse_browser(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("Браузер для ComfyUI"), "", tr("Программы (*.exe)") + ";;* (*)")
        if f:
            self._set_cfg("browser", os.path.normpath(f))
            self._fill_browsers()

    def _on_comfy_finished(self, code, _status=None):
        self.console.system(tr('ComfyUI остановлен (код {0})', code))
        self.proc = None
        self.server_url = None
        self.set_status("stopped")
        if self._restart_pending:
            self._restart_pending = False
            QTimer.singleShot(500, self.start_comfy)

    def _on_comfy_error(self, err):
        if err == QProcess.FailedToStart:
            self.console.system(tr('Не удалось запустить {0}', self.python_exe), error=True)
            self.proc = None
            self.set_status("stopped")

    def _on_line(self, line, source):
        if source != "comfy":
            return
        m = re.search(r"To see the GUI go to:\s*(\S+)", line)
        if m:
            url = m.group(1).replace("0.0.0.0", "127.0.0.1").replace("[::]", "127.0.0.1")
            if not url.startswith("http"):
                url = "http://" + url
            self.server_url = url
            self.set_status("running")
            if self.chk_browser.isChecked():
                self.open_browser()

    def _on_progress(self, pct, text):
        self.pbar.show()
        self.pbar.setValue(pct)
        self.lbl_progress.setText(text[-80:])
        self._progress_hide.start(4000 if pct < 100 else 1500)

    # ── обновления ──
    def _ensure_idle(self, what=None):
        what = what or tr("обновлять файлы")
        if not self.root:
            QMessageBox.warning(self, APP_TITLE, tr('Сборка ComfyUI не найдена.'))
            return False
        if self.running:
            QMessageBox.information(self, APP_TITLE, tr('Сначала останови ComfyUI — {0} на ходу нельзя.', what))
            return False
        if self.tasks.busy or self.transferring:
            QMessageBox.information(self, APP_TITLE, tr('Дождись окончания текущей операции.'))
            return False
        return True

    def update_comfy(self, with_deps):
        if not self._ensure_idle():
            return
        upd = self.root / "update"
        py = self.python_exe
        comfy_arg = str(self.comfy) + os.sep
        steps = []
        if (upd / "update.py").exists():
            steps.append((tr('Обновление ComfyUI'), py, [str(upd / "update.py"), comfy_arg], upd))

            def rerun():
                new = upd / "update_new.py"
                if new.exists():
                    os.replace(new, upd / "update.py")
                    return [(tr('Апдейтер обновился — запускаю ещё раз'), py,
                             [str(upd / "update.py"), comfy_arg, "--skip_self_update"], upd)]
                return None
            steps.append(rerun)
        else:
            git = find_git(self.root)
            if git and (self.comfy / ".git").exists():
                steps.append(("git pull ComfyUI", git, ["pull", "--ff-only"], self.comfy))
            else:
                QMessageBox.warning(self, APP_TITLE, tr('Не найден ни update/update.py, ни git-репозиторий ComfyUI.'))
                return
        if with_deps:
            steps.append((tr('Зависимости ComfyUI'), py, ["-s", "-m", "pip", "install", "-r",
                                                      str(self.comfy / "requirements.txt")], self.comfy))
        steps.append(self.replace_example_image)
        self.tasks.run(tr('Обновление ComfyUI'), steps)

    def example_source(self):
        """Картинка для подмены: своя (если выбрана и на месте) или встроенный логотип."""
        custom = self.cfg.get("example_custom") or ""
        if custom:
            if Path(custom).is_file():
                return Path(custom)
            self.console.system(tr("Своя картинка для example.png не найдена: {0} — использую встроенную.", custom), error=True)
        return brand_dir() / "example.png"

    def _ensure_example_image(self):
        # тихая проверка при запуске: если ComfyUI обновили мимо лаунчера (например, через Manager)
        if not self.cfg.get("example_replace", True):
            return
        try:
            src, dst = self.example_source(), self.comfy / "input" / "example.png"
            if src.exists() and dst.exists() and dst.read_bytes() != src.read_bytes():
                self.replace_example_image()
        except Exception:
            pass

    def replace_example_image(self):
        """После обновления ComfyUI кладёт в ComfyUI/input/example.png выбранную картинку (по умолчанию — встроенный логотип)."""
        if not self.cfg.get("example_replace", True):
            return None
        src = self.example_source()
        if not src.exists():
            self.console.system(tr('Логотип для example.png не найден в brand — пропускаю замену.'), error=True)
            return None
        dst = self.comfy / "input" / "example.png"
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                _make_writable(dst)
            shutil.copyfile(src, dst)
            self.console.system(tr("input/example.png заменён: {0}", src.name if self.cfg.get("example_custom") else BRAND_NAME))
        except Exception as e:
            self.console.system(tr('Не удалось заменить input/example.png: {0}', e), error=True)
        return None

    def refresh_nodes(self):
        self.tree.clear()
        git = find_git(self.root)
        self.lbl_git.setText(tr('<span style="color:{0}">● Git найден</span>', C["GREEN"]) if git
                             else tr('<span style="color:{0}">● Git не найден — обновление нод недоступно</span>', C["YELLOW"]))
        if hasattr(self, "lbl_install_git"):
            self.lbl_install_git.setText(
                tr('<span style="color:{0}">● Git найден — нода ставится через git clone и потом обновляется на вкладке «Обновления»</span>', C["GREEN"]) if git
                else tr('<span style="color:{0}">● Git не найден — ноды с GitHub скачаются архивом, но обновлять их через лаунчер не получится. Установи Git for Windows (git-scm.com).</span>', C["YELLOW"]))
            self._update_install_preview()
        if not self.root:
            self.lbl_nodes.setText(tr('Сборка не выбрана'))
            return
        dirs = list_node_dirs(self.comfy)
        off = 0
        for d in dirs:
            enabled = not d.name.endswith(".disabled")
            off += 0 if enabled else 1
            it = QTreeWidgetItem([node_base_name(d.name), tr('● вкл') if enabled else tr('○ выкл'),
                                  "git" if (d / ".git").exists() else "—",
                                  tr('есть') if (d / "requirements.txt").exists() else "—"])
            it.setData(0, Qt.UserRole, str(d))
            it.setForeground(1, QColor(C["GREEN"] if enabled else C["MUTED"]))
            if not enabled:
                it.setForeground(0, QColor(C["MUTED"]))
            self.tree.addTopLevelItem(it)
        self.lbl_nodes.setText(tr('{0} нод · отключено: {1}', len(dirs), off))

    def _selected_nodes(self):
        return [Path(it.data(0, Qt.UserRole)) for it in self.tree.selectedItems()]

    def update_nodes(self, all_nodes):
        if not self._ensure_idle():
            return
        git = find_git(self.root)
        if not git:
            QMessageBox.warning(self, APP_TITLE, tr('Git не найден. Установи Git for Windows (git-scm.com) и перезапусти лаунчер.'))
            return
        dirs = list_node_dirs(self.comfy) if all_nodes else self._selected_nodes()
        dirs = [d for d in dirs if (d / ".git").exists() and not d.name.endswith(".disabled")]
        if not dirs:
            QMessageBox.information(self, APP_TITLE, tr('Нет включённых нод с git для обновления.') if all_nodes
                                    else tr('Выбери в списке ноды для обновления.'))
            return
        steps = [(f"git pull · {d.name}", git, ["pull", "--ff-only"], d) for d in dirs]
        if self.chk_deps.isChecked():
            steps += self._deps_steps(dirs)
        self.tasks.run(tr('Обновление кастом-нод ({0})', len(dirs)), steps)

    def _deps_steps(self, dirs):
        return [(f"pip · {d.name}", self.python_exe, ["-s", "-m", "pip", "install", "-r", "requirements.txt"], d)
                for d in dirs if (d / "requirements.txt").exists() and not d.name.endswith(".disabled")]

    def install_node_deps(self):
        if not self._ensure_idle():
            return
        dirs = self._selected_nodes() or list_node_dirs(self.comfy)
        steps = self._deps_steps(dirs)
        if not steps:
            QMessageBox.information(self, APP_TITLE, tr('У выбранных нод нет requirements.txt.'))
            return
        self.tasks.run(tr('Установка зависимостей нод'), steps)

    def toggle_nodes(self):
        if self.running:
            QMessageBox.information(self, APP_TITLE, tr('Останови ComfyUI, чтобы включать и выключать ноды.'))
            return
        sel = self._selected_nodes()
        if not sel:
            QMessageBox.information(self, APP_TITLE, tr('Выбери ноды в списке.'))
            return
        for d in sel:
            target = d.with_name(node_base_name(d.name)) if d.name.endswith(".disabled") \
                else d.with_name(d.name + ".disabled")
            try:
                d.rename(target)
                state = tr('Отключена') if target.name.endswith(".disabled") else tr('Включена')
                self.console.system(f"{state}: {node_base_name(d.name)}")
            except Exception as e:
                self.console.system(tr('Не удалось переименовать {0}: {1}', d.name, e), error=True)
        self.refresh_nodes()
        self._refresh_src_status()

    def _on_task_started(self, title):
        self.console.system(f"━━ {title} ━━")
        self.set_status("updating")
        self.go("console")

    # ── установка нод ──
    def _update_install_preview(self):
        if not hasattr(self, "lbl_install_preview"):
            return
        urls = split_urls(self.edit_install.toPlainText())
        if not urls:
            self.lbl_install_preview.setText(tr('<span style="color:{0}">Нода установится в ComfyUI\\custom_nodes</span>', C["MUTED"]))
            return
        have = self._current_node_names()
        lines = []
        for u in urls[:12]:
            info = parse_repo_url(u)
            if not info:
                lines.append(tr('<span style="color:{0}">✗ {1} — не похоже на ссылку на репозиторий</span>', C["RED"], html.escape(u)))
            elif info["name"].lower() in have:
                lines.append(tr('<span style="color:{0}">● {1} — уже установлена (обновить можно на вкладке «Обновления»)</span>', C["YELLOW"], html.escape(info["name"])))
            else:
                br = tr(' · ветка {0}', html.escape(info["branch"])) if info["branch"] else ""
                lines.append(f'<span style="color:{C["GREEN"]}">✓ {html.escape(info["name"])}</span>'
                             f'<span style="color:{C["MUTED"]}"> → custom_nodes\\{html.escape(info["name"])}{br}</span>')
        if len(urls) > 12:
            lines.append(tr('<span style="color:{0}">…и ещё {1}</span>', C["MUTED"], len(urls) - 12))
        self.lbl_install_preview.setText("<br>".join(lines))

    def install_nodes(self):
        urls = split_urls(self.edit_install.toPlainText())
        if not urls:
            QMessageBox.information(self, APP_TITLE, tr('Вставь ссылку на репозиторий ноды.'))
            return
        if not self._ensure_idle(tr('устанавливать ноды')):
            return
        bad = [u for u in urls if not parse_repo_url(u)]
        if bad:
            QMessageBox.warning(self, APP_TITLE, tr('Эти строки не похожи на ссылки на репозиторий:\n\n') + "\n".join(bad))
            return
        git = find_git(self.root)
        cn = self.comfy / "custom_nodes"
        cn.mkdir(parents=True, exist_ok=True)
        have = self._current_node_names()
        steps, targets, skipped, seen = [], [], [], set()
        for u in urls:
            info = parse_repo_url(u)
            key = info["name"].lower()
            if key in seen:
                continue
            seen.add(key)
            dest = cn / info["name"]
            if key in have or dest.exists():
                skipped.append(info["name"])
                continue
            if git:
                args = ["clone", "--recursive"] + (["-b", info["branch"]] if info["branch"] else []) + [info["clone"], str(dest)]
                steps.append((f"git clone · {info['name']}", git, args, cn))
            elif info["zip"]:
                steps.append((tr('Скачивание архива · {0}', info['name']), self.python_exe,
                              ["-s", "-c", ZIP_INSTALL_SCRIPT, info["zip"], str(dest)], cn))
            else:
                skipped.append(tr('{0} (нужен Git — это не GitHub)', info['name']))
                continue
            if self.chk_install_deps.isChecked():
                steps.append(lambda d=dest: self._post_install_steps(d))
            targets.append((info, dest))
        if skipped:
            self.console.system(tr('Пропущено (уже установлено или нужен Git): ') + ", ".join(skipped))
        if not targets:
            QMessageBox.information(self, APP_TITLE, tr('Нечего устанавливать:\n') + "\n".join(skipped))
            return
        if not git:
            self.console.system(tr('Git не найден — ноды скачиваются архивом. Обновлять их через лаунчер не получится.'), error=True)
        steps.append(lambda t=targets: self._finish_install(t))
        self.tasks.run(tr('Установка нод ({0})', len(targets)), steps)

    def _post_install_steps(self, dest: Path):
        if not dest.is_dir():
            return None  # клонирование не удалось — ставить нечего
        steps = []
        if (dest / "requirements.txt").exists():
            steps.append((f"pip · {dest.name}", self.python_exe,
                          ["-s", "-m", "pip", "install", "-r", "requirements.txt"], dest))
        if (dest / "install.py").exists():
            steps.append((f"install.py · {dest.name}", self.python_exe, ["-s", "install.py"], dest))
        if not steps:
            self.console.system(tr('{0}: зависимостей нет', dest.name))
        return steps

    def _finish_install(self, targets):
        hist = self.cfg.get("install_history") or []
        ok_names = []
        for info, dest in targets:
            ok = dest.is_dir() and any(dest.iterdir())
            if ok:
                ok_names.append(info["name"])
            hist.insert(0, dict(name=info["name"], url=info["page"], path=str(dest), ok=ok,
                                when=time.strftime("%d.%m.%Y %H:%M")))
        self._set_cfg("install_history", hist[:40])
        self._fill_install_history()
        if ok_names:
            self.edit_install.clear()
            self.console.system(tr('Установлено: ') + ", ".join(ok_names) + tr('. Перезапусти ComfyUI, чтобы ноды подхватились.'))
        return None

    def _fill_install_history(self):
        self.tree_install.clear()
        for h in self.cfg.get("install_history") or []:
            it = QTreeWidgetItem([h.get("name", ""), tr('✓ установлена') if h.get("ok") else tr('✗ ошибка'),
                                  h.get("when", ""), h.get("url", "")])
            it.setForeground(1, QColor(C["GREEN"] if h.get("ok") else C["RED"]))
            it.setForeground(3, QColor(C["MUTED"]))
            it.setData(0, Qt.UserRole, h.get("path", ""))
            it.setData(3, Qt.UserRole, h.get("url", ""))
            self.tree_install.addTopLevelItem(it)

    def _open_install_item(self, it, folder):
        if not it:
            QMessageBox.information(self, APP_TITLE, tr('Выбери ноду в истории.'))
            return
        if folder:
            p = Path(it.data(0, Qt.UserRole) or "")
            if p.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
            else:
                QMessageBox.information(self, APP_TITLE, tr('Папки этой ноды уже нет.'))
        elif it.data(3, Qt.UserRole):
            QDesktopServices.openUrl(QUrl(it.data(3, Qt.UserRole)))

    def _clear_install_history(self):
        self._set_cfg("install_history", [])
        self._fill_install_history()

    def _on_task_finished(self, title, errors):
        if errors:
            self.console.system(tr('{0}: завершено с ошибками ({1}). Пролистай консоль выше.', title, errors), error=True)
        else:
            self.console.system(tr('{0}: готово ✓', title))
        self.refresh_nodes()
        self._refresh_src_status()
        self._update_install_preview()
        self._idle_status()

    # ── перенос ──
    def browse_source(self):
        d = QFileDialog.getExistingDirectory(self, tr('Другая сборка ComfyUI'), self.edit_src.text() or str(app_dir()))
        if d:
            self.edit_src.setText(d)
            self.scan_source()

    def scan_source(self):
        path = self.edit_src.text().strip()
        src = resolve_comfy(path) if path else None
        self.tree_src.clear()
        self.src_comfy = None
        if not src:
            self.lbl_src.setText(tr('<span style="color:{0}">✗ ComfyUI не найден — нужна папка с ComfyUI/main.py или сама папка ComfyUI.</span>', C["RED"]))
            self.lbl_src_nodes.setText(tr('Ноды появятся после сканирования.'))
            return
        if self.root and src.resolve() == self.comfy.resolve():
            self.lbl_src.setText(tr('<span style="color:{0}">✗ Это текущая сборка — выбери другую.</span>', C["RED"]))
            return
        self.src_comfy = src
        self._set_cfg("transfer_source", path)
        parts = []
        models = src / "models"
        if models.is_dir():
            parts.append(tr('папок моделей: {0}', sum(1 for d in models.iterdir() if d.is_dir())))
        for name in ("input", "output"):
            if (src / name).is_dir():
                parts.append(tr('{0}: есть', name))
        if (src / "user").is_dir():
            parts.append(tr('настройки: есть'))
        self.lbl_src.setText(f'<span style="color:{C["GREEN"]}">✓ {html.escape(str(src))}</span>'
                             f'<br><span style="color:{C["MUTED"]}">{" · ".join(parts)}</span>')
        self.tree_src.blockSignals(True)
        for d in list_node_dirs(src):
            it = QTreeWidgetItem([node_base_name(d.name) + (tr(' (выкл)') if d.name.endswith(".disabled") else ""), "", tr('есть') if (d / "requirements.txt").exists() else "—"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setData(0, Qt.UserRole, str(d))
            self.tree_src.addTopLevelItem(it)
        self.tree_src.blockSignals(False)
        self._refresh_src_status(auto_mark=True)

    def _current_node_names(self):
        return {node_base_name(d.name).lower() for d in list_node_dirs(self.comfy)} if self.root else set()

    def _refresh_src_status(self, auto_mark=False):
        if not hasattr(self, "tree_src") or not self.src_comfy:
            return
        have = self._current_node_names()
        self.tree_src.blockSignals(True)
        for i in range(self.tree_src.topLevelItemCount()):
            it = self.tree_src.topLevelItem(i)
            name = node_base_name(Path(it.data(0, Qt.UserRole)).name).lower()
            exists = name in have
            it.setData(1, Qt.UserRole, exists)
            it.setText(1, tr('✓ есть') if exists else tr('✗ нет'))
            it.setForeground(1, QColor(C["GREEN"] if exists else C["PINK"]))
            it.setForeground(0, QColor(C["MUTED"] if exists else C["PINK"]))
            if auto_mark:
                it.setCheckState(0, Qt.Unchecked if exists else Qt.Checked)
        self.tree_src.blockSignals(False)
        self._update_src_nodes_label()

    def _update_src_nodes_label(self):
        n = self.tree_src.topLevelItemCount()
        miss = sum(1 for i in range(n) if not self.tree_src.topLevelItem(i).data(1, Qt.UserRole))
        checked = sum(1 for i in range(n) if self.tree_src.topLevelItem(i).checkState(0) == Qt.Checked)
        self.lbl_src_nodes.setText(tr('В источнике нод: {0} · недостающих: {1} · отмечено: {2}', n, miss, checked))

    def _mark_src_nodes(self, mode):
        self.tree_src.blockSignals(True)
        for i in range(self.tree_src.topLevelItemCount()):
            it = self.tree_src.topLevelItem(i)
            on = mode == "all" or (mode == "missing" and not it.data(1, Qt.UserRole))
            it.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self.tree_src.blockSignals(False)
        self._update_src_nodes_label()

    def _need_source(self):
        if not self.src_comfy:
            QMessageBox.information(self, APP_TITLE, tr('Сначала укажи другую сборку и нажми «Сканировать».'))
            return False
        return True

    def transfer_selected_items(self):
        if not self._need_source() or not self._ensure_idle(tr('переносить файлы')):
            return
        src, dst = self.src_comfy, self.comfy
        jobs = []
        if self.chk_t_settings.isChecked():
            jobs.append(TransferJob(tr('настройки'), src / "user", dst / "user", exclude=("default/workflows",)))
        if self.chk_t_workflows.isChecked():
            jobs.append(TransferJob(tr('воркфлоу'), src / "user/default/workflows", dst / "user/default/workflows"))
        mode = self.cb_models_mode.currentData()
        data_jobs = []  # (режим, подпись, папка)
        if self.chk_t_models.isChecked() and mode != "link":
            data_jobs.append((mode, tr('модели'), "models"))
        if self.chk_t_input.isChecked():
            data_jobs.append((self.cb_input_mode.currentData(), "input", "input"))
        if self.chk_t_output.isChecked():
            data_jobs.append((self.cb_output_mode.currentData(), "output", "output"))
        moved = [label for m, label, _ in data_jobs if m == "move"]
        if moved and QMessageBox.question(
                self, APP_TITLE, tr("Будут ПЕРЕМЕЩЕНЫ: {0}. В исходной сборке их не останется. Продолжить?",
                                    ", ".join(moved))) != QMessageBox.Yes:
            return
        if self.chk_t_models.isChecked() and mode == "link":
            self.link_models(src)
        for m, label, folder in data_jobs:
            jobs.append(TransferJob(label, src / folder, dst / folder, move=(m == "move"), hardlink=(m == "hardlink")))
        if self.chk_t_yaml.isChecked():
            self.transfer_extra_yaml(src, alone=not jobs and not (self.chk_t_models.isChecked() and mode == "link"))
        if not jobs:
            if not (self.chk_t_models.isChecked() and mode == "link") and not self.chk_t_yaml.isChecked():
                QMessageBox.information(self, APP_TITLE, tr('Отметь, что переносить.'))
            return
        self.start_transfer(jobs, tr('Перенос: {0}', ', '.join(j.label for j in jobs)))

    def transfer_extra_yaml(self, src, alone=False):
        src_yaml = src / "extra_model_paths.yaml"
        if not src_yaml.is_file():
            self.console.system(tr("В исходной сборке нет extra_model_paths.yaml — переносить нечего."))
            if alone:
                QMessageBox.information(self, APP_TITLE, tr("В исходной сборке нет extra_model_paths.yaml — переносить нечего."))
            return False
        dst_yaml = self.comfy / "extra_model_paths.yaml"
        try:
            dst_text = dst_yaml.read_text("utf-8", errors="replace") if dst_yaml.exists() else ""
            text, added, skipped = merge_extra_model_paths(src_yaml.read_text("utf-8", errors="replace"),
                                                           str(src_yaml.parent), dst_text, self.comfy)
            if added:
                if dst_yaml.exists():
                    shutil.copy2(dst_yaml, dst_yaml.with_name("extra_model_paths.yaml.bak"))
                dst_yaml.write_text(text, "utf-8")
        except Exception as e:
            self.console.system(tr("Не удалось перенести extra_model_paths.yaml: {0}", e), error=True)
            return False
        msg = tr("extra_model_paths.yaml: добавлено секций {0}", len(added)) + (f" ({', '.join(added)})" if added else "")
        if skipped:
            msg += " · " + tr("пропущено (уже есть или указывают на эту сборку): {0}", ", ".join(skipped))
        self.console.system(msg)
        if alone:
            QMessageBox.information(self, APP_TITLE, msg)
        if added and hasattr(self, "cb_dl_root"):
            self.dl_roots = self._load_model_roots()
            self._fill_root_combo()
        return True

    def link_models(self, src):
        yaml = self.comfy / "extra_model_paths.yaml"
        text = yaml.read_text("utf-8") if yaml.exists() else ""
        block = build_extra_paths_block(src, text)
        if block is None:
            self.console.system(tr('Модели этой сборки уже подключены (или папка models пуста).'))
            QMessageBox.information(self, APP_TITLE, tr('Модели этой сборки уже подключены или папка models пуста.'))
            return
        try:
            with open(yaml, "a", encoding="utf-8") as f:
                f.write(block)
            self.console.system(tr('Модели подключены через extra_model_paths.yaml: {0}', src / 'models'))
            QMessageBox.information(self, APP_TITLE, tr('Модели подключены через extra_model_paths.yaml.\nComfyUI увидит их после перезапуска.'))
        except Exception as e:
            self.console.system(tr('Не удалось записать extra_model_paths.yaml: {0}', e), error=True)

    def transfer_nodes(self, only_missing):
        if not self._need_source() or not self._ensure_idle(tr('переносить ноды')):
            return
        items = [self.tree_src.topLevelItem(i) for i in range(self.tree_src.topLevelItemCount())]
        if only_missing:
            items = [it for it in items if not it.data(1, Qt.UserRole)]
        else:
            items = [it for it in items if it.checkState(0) == Qt.Checked]
        if not items:
            QMessageBox.information(self, APP_TITLE, tr('Недостающих нод нет — всё уже на месте.') if only_missing
                                    else tr('Отметь ноды в списке.'))
            return
        existing = [it for it in items if it.data(1, Qt.UserRole)]
        if existing and QMessageBox.question(
                self, APP_TITLE, tr('{0} из отмеченных нод уже есть в текущей сборке — их файлы будут заменены версией из источника. Продолжить?', len(existing))) != QMessageBox.Yes:
            return
        have = {node_base_name(d.name).lower(): d for d in list_node_dirs(self.comfy)}
        jobs, dsts = [], []
        for it in items:
            s = Path(it.data(0, Qt.UserRole))
            d = have.get(node_base_name(s.name).lower(), self.comfy / "custom_nodes" / s.name)
            jobs.append(TransferJob(tr('нода {0}', s.name), s, d, policy="replace"))
            dsts.append(d)
        self._xfer_nodes = dsts
        self.start_transfer(jobs, tr('Перенос кастом-нод ({0})', len(jobs)))

    def start_transfer(self, jobs, title):
        self.console.system(f"━━ {title} ━━")
        self.xfer_panel.show()
        self.xfer_bar.setValue(0)
        self.lbl_xfer.setText(tr('Подготовка…'))
        th = QThread(self)
        w = TransferWorker(jobs, self.cb_policy.currentData(), gentle=self.chk_gentle.isChecked())
        w.moveToThread(th)
        th.started.connect(w.run)
        w.progress.connect(self._on_xfer_progress)
        w.log.connect(self._on_xfer_log)  # метод окна → вызов в GUI-потоке (лямбда выполнилась бы в рабочем)
        w.done.connect(self._on_xfer_done)
        w.done.connect(th.quit)
        th.finished.connect(w.deleteLater)
        th.finished.connect(th.deleteLater)
        self._xfer_thread, self._xfer_worker = th, w
        self._xfer_title = title
        self.set_status("transfer")
        th.start()

    def _on_xfer_log(self, msg):
        self.console.system(msg, error=msg.startswith(tr('Ошибка')))

    def _on_xfer_progress(self, pct, text):
        self.xfer_bar.setValue(pct)
        self.lbl_xfer.setText(text[-90:])

    def cancel_transfer(self):
        if self._xfer_worker:
            self._xfer_worker.cancel()
            self.lbl_xfer.setText(tr('Отмена…'))

    def _on_xfer_done(self, st):
        self._xfer_thread = None
        self._xfer_worker = None
        msg = (tr('{0}: перенесено файлов {1} ({2}), пропущено {3}, ошибок {4}', self._xfer_title, st['copied'], fmt_size(st['bytes']), st['skipped'], st['errors']) + (tr(", из них жёсткими ссылками: {0}", st["linked"]) if st.get("linked") else "")
               + (tr(' — ОТМЕНЕНО') if st["cancelled"] else ""))
        self.console.system(msg, error=bool(st["errors"]))
        self.lbl_xfer.setText(msg)
        QTimer.singleShot(6000, lambda: None if self.transferring else self.xfer_panel.hide())
        nodes, self._xfer_nodes = self._xfer_nodes, []
        self.refresh_nodes()
        self._refresh_src_status()
        self.refresh_workflows()
        self._idle_status()
        if nodes and not st["cancelled"] and self.chk_t_deps.isChecked():
            steps = self._deps_steps(nodes)
            if steps:
                self.tasks.run(tr('Зависимости перенесённых нод'), steps)

    # ── воркфлоу ──
    def refresh_workflows(self):
        if not hasattr(self, "tree_wf"):
            return
        self.ndesc = NDescIndex.load(self.utils_dir) if self.root else NDescIndex()
        self._model_cache = {}
        for fname, err in self.ndesc.errors:
            self.console.system(tr('Файл описаний {0}: {1}', fname, err), error=True)
        self.tree_wf.clear()
        wdir = self.workflows_dir
        files = sorted(wdir.rglob("*.json"), key=lambda p: [s.lower() for s in p.relative_to(wdir).parts]) \
            if self.root and wdir.is_dir() else []
        folders = {}
        described = 0
        for f in files:
            rel = f.relative_to(wdir)
            parent = self.tree_wf.invisibleRootItem()
            acc = []
            for part in rel.parts[:-1]:
                acc.append(part)
                key = "/".join(acc)
                if key not in folders:
                    fi = QTreeWidgetItem([part])
                    fi.setIcon(0, QIcon(draw_icon("folder", 16, C["CYAN"])))
                    fi.setData(0, Qt.UserRole + 1, "folder")
                    parent.addChild(fi)
                    fi.setExpanded(True)
                    folders[key] = fi
                parent = folders[key]
            entry = self.ndesc.find(rel.as_posix())
            title = f.stem  # в списке всегда имя файла; title из .ndesc участвует только в поиске
            it = QTreeWidgetItem([title])
            it.setData(0, Qt.UserRole, str(f))
            it.setData(0, Qt.UserRole + 1, rel.as_posix())
            it.setToolTip(0, rel.as_posix())
            if entry:
                described += 1
                tags = " ".join(as_list(entry.get("tags")))
                it.setData(0, Qt.UserRole + 2, f"{title} {f.name} {entry.get('title', '')} {entry.get('category', '')} {tags} {entry.get('short', '')}".lower())
            else:
                it.setData(0, Qt.UserRole + 2, f"{title} {f.name}".lower())
                if self.ndesc.loaded:
                    it.setForeground(0, QColor(C["MUTED"]))
            parent.addChild(it)
        has_desc = self.ndesc.loaded and bool(self.ndesc.by_path)
        if has_desc:
            names = ", ".join(f.name for f in self.ndesc.files)
            self.lbl_wf.setText(tr('Воркфлоу: {0} · с описанием: {1} · файлы описаний: {2}', len(files), described, names))
        elif self.ndesc.loaded or self.ndesc.errors:
            self.lbl_wf.setText(tr("Воркфлоу: {0} · файл описаний пустой или повреждён — панель описаний скрыта", len(files)))
        else:
            self.lbl_wf.setText(tr('Воркфлоу: {0} · файл описаний в utils\\*.ndesc не найден', len(files)))
        # нет корректных описаний — показываем только список воркфлоу
        self.wf_desc_panel.setVisible(has_desc)
        self.filter_workflows(self.edit_wf_search.text())
        self.show_workflow(None)

    def filter_workflows(self, text):
        q = (text or "").strip().lower()

        def walk(item):
            visible_any = False
            for i in range(item.childCount()):
                ch = item.child(i)
                if ch.data(0, Qt.UserRole + 1) == "folder":
                    vis = walk(ch)
                else:
                    vis = not q or q in (ch.data(0, Qt.UserRole + 2) or "")
                ch.setHidden(not vis)
                visible_any = visible_any or vis
            return visible_any
        walk(self.tree_wf.invisibleRootItem())

    def _current_wf_path(self):
        it = self.tree_wf.currentItem()
        p = it.data(0, Qt.UserRole) if it else None
        return Path(p) if p else None

    def _model_present(self, folder, name):
        base = self.comfy / "models" / folder
        if (base / name).exists():
            return True
        key = folder.lower()
        if key not in self._model_cache:
            names = set()
            if base.is_dir():
                for dp, _d, fns in os.walk(base):
                    names.update(fn.lower() for fn in fns)
            self._model_cache[key] = names
        return Path(name).name.lower() in self._model_cache[key]

    def _empty_view(self, text):
        self.wf_view.setHtml(f'<div style="margin-top:60px; text-align:center; color:{C["MUTED"]}; font-size:15px;">'
                             f'{html.escape(text)}</div>')

    def show_workflow(self, item):
        path = item.data(0, Qt.UserRole) if item else None
        self.btn_wf_reveal.setEnabled(bool(path))
        self.btn_wf_copy.setEnabled(bool(path))
        if not self.ndesc.loaded:
            self._empty_view(tr(NDESC_NOT_FOUND))
            return
        if not path:
            self._empty_view(tr('Выбери воркфлоу слева.'))
            return
        rel = item.data(0, Qt.UserRole + 1)
        entry = self.ndesc.find(rel)
        if not entry:
            self._empty_view(tr('Для «{0}» описания пока нет.', rel))
            return
        self.wf_view.setHtml(self.render_entry(entry, rel))

    def render_entry(self, e, rel):
        esc = html.escape
        cyan, pink, muted_c, green, red = DESC["HEAD"], DESC["TAG"], C["MUTED"], DESC["OK"], DESC["BAD"]
        out = [f'<h2 style="margin:0 0 4px 0; color:{DESC["TEXT"]};">{esc(Path(rel).stem)}</h2>']
        meta = []
        if e.get("category"):
            meta.append(f'<span style="color:{cyan}; font-weight:700;">● {esc(str(e["category"]))}</span>')
        tags = as_list(e.get("tags"))
        if tags:
            meta.append(f'<span style="color:{pink};">{" ".join("#" + esc(str(t)) for t in tags)}</span>')
        if meta:
            out.append("<p>" + " &nbsp; ".join(meta) + "</p>")
        if e.get("short"):
            out.append(f'<p style="color:{muted_c}; font-size:14px;"><i>{esc(str(e["short"]))}</i></p>')
        prev = e.get("preview")
        if prev:
            base = self.ndesc.base_dir(e) or self.utils_dir
            pp = Path(prev) if Path(prev).is_absolute() else base / prev
            if pp.exists():
                pm = QPixmap(str(pp))
                if not pm.isNull():
                    w = min(pm.width(), max(200, self.wf_view.viewport().width() - 30))
                    out.append(f'<p><img src="{QUrl.fromLocalFile(str(pp)).toString()}" width="{w}"></p>')
        desc = e.get("description")
        if desc:
            if isinstance(desc, list):
                desc = "\n".join(str(x) for x in desc)
            doc = QTextDocument()
            doc.setMarkdown(str(desc))
            body = re.search(r"<body[^>]*>(.*)</body>", doc.toHtml(), re.S)
            out.append(body.group(1) if body else esc(str(desc)))
        steps = as_list(e.get("steps"))
        if steps:
            out.append(tr('<h3 style="color:{0};">Как пользоваться</h3><ol>', cyan))
            out += [f"<li>{esc(str(s))}</li>" for s in steps]
            out.append("</ol>")
        models = as_list(e.get("models"))
        if models:
            out.append(tr('<h3 style="color:{0};">Модели</h3><table cellspacing="0" cellpadding="3">', cyan))
            for m in models:
                m = m if isinstance(m, dict) else {"name": str(m)}
                name, folder = str(m.get("name", "")), str(m.get("folder", ""))
                ok = bool(folder) and self._model_present(folder, name)
                mark = f'<span style="color:{green};">✓</span>' if ok else (
                    f'<span style="color:{red};">✗</span>' if folder else f'<span style="color:{muted_c};">•</span>')
                extra = []
                if folder:
                    extra.append(f"models/{esc(folder)}")
                if m.get("size"):
                    extra.append(esc(str(m["size"])))
                if m.get("note"):
                    extra.append(esc(str(m["note"])))
                link = tr(' &nbsp;<a href="{0}">скачать</a>', esc(str(m["url"]))) if m.get("url") else ""
                out.append(f'<tr><td>{mark}</td><td><b>{esc(name)}</b> <span style="color:{muted_c};">'
                           f'{" · ".join(extra)}</span>{link}</td></tr>')
            out.append("</table>")
        req = []
        if e.get("vram"):
            req.append(f"<b>VRAM:</b> {esc(str(e['vram']))}")
        if e.get("time"):
            req.append(tr('<b>Время генерации:</b> {0}', esc(str(e['time']))))
        if req:
            out.append(tr('<h3 style="color:{0};">Требования</h3><p>', cyan) + "<br>".join(req) + "</p>")
        links = []
        if e.get("video"):
            links.append(tr('<a href="{0}">▶ Видео-разбор</a>', esc(str(e["video"]))))
        for l in as_list(e.get("links")):
            if isinstance(l, dict) and l.get("url"):
                links.append(f'<a href="{esc(str(l["url"]))}">{esc(str(l.get("title") or l["url"]))}</a>')
        if links:
            out.append("<p>" + " &nbsp;·&nbsp; ".join(links) + "</p>")
        foot = [esc(rel)]
        for key, lbl in (("version", "v"), ("updated", tr('обновлено ')), ("author", tr('автор: '))):
            if e.get(key):
                foot.append(f"{lbl}{esc(str(e[key]))}")
        out.append(f'<p style="color:{muted_c}; font-size:11px; margin-top:14px;">{" · ".join(foot)}</p>')
        return "".join(out)

    # ── папки / ссылки ──
    def open_rel(self, rel):
        if not self.root:
            QMessageBox.warning(self, APP_TITLE, tr('Сначала укажи папку сборки в настройках.'))
            return
        path = self.root / Path(rel)
        if rel.endswith(".yaml"):
            if not path.exists():
                ex = path.with_name("extra_model_paths.yaml.example")
                if ex.exists():
                    shutil.copy(ex, path)
                    self.console.system(tr('Создан extra_model_paths.yaml из примера'))
                else:
                    QMessageBox.information(self, APP_TITLE, tr('Файл extra_model_paths.yaml не найден.'))
                    return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return
        self._open_dir(path)

    def rebuild_links(self):
        while self.links_grid.count():
            it = self.links_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        links = load_links()
        if not links:
            self.links_grid.addWidget(muted(tr('Ссылки не заданы.'), False), 0, 0)
            return
        cols = 4
        bdir = brand_dir()
        for i, l in enumerate(links):
            url = str(l["url"]).strip()
            if not re.match(r"^[a-z]+://", url):
                url = "https://" + url
            b = button(l.get("title") or link_host(url), lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)), "Link")
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(url)
            b.setIconSize(QSize(22, 22))
            pm = QPixmap(str(bdir / l["icon"])) if l.get("icon") else QPixmap()
            b.setIcon(QIcon(pm) if not pm.isNull() else QIcon(draw_icon("link", 22, gradient=True)))
            self.links_grid.addWidget(b, i // cols, i % cols)
        for c in range(cols):
            self.links_grid.setColumnStretch(c, 1)

    # ── сборка ──
    def set_root(self, path, quiet=False):
        if not path:
            return
        if not is_root(path):
            if not quiet:
                QMessageBox.warning(self, APP_TITLE, tr('В этой папке должны быть python_embeded\\python.exe и ComfyUI\\main.py.'))
            self.refresh_root_state()
            return
        self.root = Path(path)
        self._set_cfg("root", str(self.root))
        self.edit_root.setText(str(self.root))
        self.console.system(tr('Сборка: {0}', self.root))
        self.refresh_root_state()

    def browse_root(self):
        d = QFileDialog.getExistingDirectory(self, tr('Папка сборки ComfyUI'), str(self.root or app_dir()))
        if d:
            self.set_root(d)

    def auto_root(self):
        r = detect_root()
        if r:
            self.set_root(str(r))
        else:
            QMessageBox.information(self, APP_TITLE, tr('Не нашёл сборку рядом с лаунчером. Укажи папку вручную.'))

    def refresh_root_state(self):
        ok = bool(self.root) and is_root(self.root)
        if ok:
            self.lbl_root.setText(tr('<span style="color:{0}">✓ Найдены python_embeded и ComfyUI</span>', C["GREEN"]))
        else:
            self.lbl_root.setText(tr('<span style="color:{0}">✗ Сборка не найдена</span>', C["RED"]))
        for c in self.folder_cards:
            c.setEnabled(ok)
        self.refresh_nodes()
        self.refresh_workflows()
        self._refresh_src_status()
        self.update_controls()

    # ── профиль из ярлыка ──
    def current_profile(self):
        return dict(preset=self.cb_preset.currentData(), options=self.current_options(),
                    listen=self.chk_listen.isChecked(), port=self.spin_port.value(), extra=self.edit_extra.text(),
                    flags={k: c.isChecked() for k, c in self._flag_checks()})

    def apply_profile(self, prof):
        """Настройки из ярлыка действуют на этот запуск и не перезаписывают сохранённые настройки лаунчера."""
        if not isinstance(prof, dict):
            return
        self._restore_profile(prof)
        self.console.system(tr('Настройки из ярлыка: пресет «{0}»', tr(prof.get('preset') or CUSTOM)))

    def _restore_profile(self, prof):
        """Выставляет виджеты по профилю, не трогая сохранённый конфиг."""
        saved = json.dumps(self.cfg)
        try:
            self.apply_options(prof.get("options") or {})
            self.chk_listen.setChecked(bool(prof.get("listen")))
            self.spin_port.setValue(int(prof.get("port") or DEFAULT_PORT))
            self.edit_extra.setText(str(prof.get("extra") or ""))
            for k, c in self._flag_checks():  # старые ярлыки без flags — все флаги включены, как раньше
                c.setChecked(bool((prof.get("flags") or {}).get(k, True)))
            name = prof.get("preset")
            known = name in BUILTIN_PRESETS or name in self.cfg.get("user_presets", {})
            self._select_preset(name if known else CUSTOM)
        finally:
            self.cfg = json.loads(saved)
            save_config(self.cfg)
        self.update_command()

    # ── смена языка ──
    def _sync_lang_buttons(self):
        for code, b in getattr(self, "lang_buttons", {}).items():
            b.setChecked(code == get_lang())

    def set_language(self, code):
        if code == get_lang():
            self._sync_lang_buttons()
            return
        if self.tasks.busy or self.transferring or self.dl_tasks.busy:
            QMessageBox.information(self, APP_TITLE, tr("Сменить язык можно после окончания текущей операции."))
            self._sync_lang_buttons()
            return
        self._set_cfg("lang", code)
        set_lang(code)
        install_qt_translator(code)
        self.rebuild_ui()

    def set_theme(self, tid):
        if tid == get_theme():
            return
        if self.tasks.busy or self.transferring or self.dl_tasks.busy:
            QMessageBox.information(self, APP_TITLE, tr("Сменить тему можно после окончания текущей операции."))
            for t, b in getattr(self, "theme_buttons", {}).items():
                b.setChecked(t == get_theme())
            return
        self._set_cfg("theme", tid)
        apply_theme(tid)
        icon = make_icon()
        self.setWindowIcon(icon)
        QApplication.instance().setWindowIcon(icon)
        self.rebuild_ui()

    def rebuild_ui(self):
        """Пересобирает интерфейс на новом языке. ComfyUI, консоль и введённые данные сохраняются."""
        page = next((k for k, i in self.page_index.items() if i == self.stack.currentIndex()), "launch")
        prof = self.current_profile()
        keep = dict(install=self.edit_install.toPlainText(), search=self.edit_wf_search.text(),
                    model_url=self.edit_model_url.text(), file_filter=self.edit_file_filter.text(),
                    src=self.edit_src.text(), state=getattr(self, "state", "stopped"))
        had_src = self.src_comfy is not None
        self.console.setParent(None)  # консоль не удаляем вместе со старым интерфейсом
        old = self.centralWidget()
        self._build_ui()
        if old is not None:
            old.deleteLater()
        self._restore_profile(prof)
        self.edit_install.setPlainText(keep["install"])
        self.edit_wf_search.setText(keep["search"])
        self.edit_src.setText(keep["src"])
        self.edit_model_url.setText(keep["model_url"])
        self.edit_file_filter.setText(keep["file_filter"])
        self.refresh_root_state()
        if had_src:
            self.scan_source()
        if self.tray:
            self.tray.hide()
            self.tray.deleteLater()
            self.tray = None
        self._setup_tray()
        self.set_status(keep["state"])
        QTimer.singleShot(0, self._fit_min_width)
        self.go(page)

    # ── ярлык на рабочий стол ──
    def open_shortcut_dialog(self):
        if sys.platform != "win32":
            QMessageBox.information(self, APP_TITLE, tr('Ярлыки создаются только в Windows.'))
            return
        if not self.root:
            QMessageBox.warning(self, APP_TITLE, tr('Сначала укажи папку сборки ComfyUI в настройках.'))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr('Ярлык на рабочий стол'))
        dlg.setMinimumWidth(520)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)
        t = QLabel(tr('Ярлык быстрого запуска ComfyUI'))
        t.setObjectName("PanelTitle")
        lay.addWidget(t)
        lay.addWidget(muted(tr('Пресет: {0}. Аргументы запуска сохранятся в ярлыке такими, какие они сейчас на вкладке «Запуск».', self.cb_preset.currentText())))
        lay.addWidget(muted(tr('Название ярлыка'), False))
        name = QLineEdit(self.cfg.get("shortcut_name") or "ComfyUI Neural Dreamer")
        lay.addWidget(name)
        chk_min = QCheckBox(tr('Запускать лаунчер в свёрнутом виде'))
        chk_min.setChecked(bool(self.cfg.get("shortcut_minimized")))
        lay.addWidget(chk_min)
        hint = muted("")
        lay.addWidget(hint)

        def upd_hint():
            if not chk_min.isChecked():
                hint.setText(tr('Лаунчер откроется как обычно и сразу запустит ComfyUI.'))
            elif self.cfg.get("minimize_to_tray") and self.tray:
                hint.setText(tr('Лаунчер стартует в трее (у часов) и запустит ComfyUI, окно открывать не нужно.'))
            else:
                hint.setText(tr('Лаунчер свернётся на панель задач. Чтобы он прятался в трей, включи «Сворачивать в трей» в настройках лаунчера.'))
        chk_min.toggled.connect(upd_hint)
        upd_hint()
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button(tr('Отмена'), dlg.reject))
        row.addWidget(button(tr('Создать ярлык'), dlg.accept, "Accent"))
        lay.addLayout(row)
        if dlg.exec() != QDialog.Accepted:
            return
        self.cfg["shortcut_name"] = name.text().strip() or "ComfyUI Neural Dreamer"
        self.cfg["shortcut_minimized"] = chk_min.isChecked()
        save_config(self.cfg)
        self.create_shortcut(self.cfg["shortcut_name"], chk_min.isChecked())

    def create_shortcut(self, name, minimized):
        args = ["--autostart"] + (["--minimized"] if minimized else []) + ["--profile=" + encode_profile(self.current_profile())]
        if getattr(sys, "frozen", False):
            target, argstr, icon = sys.executable, " ".join(args), f"{sys.executable},0"
        else:
            pyw = self.root / "python_embeded" / "pythonw.exe"
            target = str(pyw if pyw.exists() else Path(sys.executable).with_name("pythonw.exe"))
            argstr = f'-s "{Path(__file__).resolve()}" ' + " ".join(args)
            ico = app_dir() / "nd_icon.ico"
            icon = f"{ico},0" if ico.exists() else f"{target},0"
        safe = re.sub(r'[\\/:*?"<>|]+', "", name).strip() or "ComfyUI"
        ps = ("$d=[Environment]::GetFolderPath('Desktop');"
              "$p=Join-Path $d ($env:ND_NAME + '.lnk');"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($p);"
              "$s.TargetPath=$env:ND_TARGET;$s.Arguments=$env:ND_ARGS;$s.WorkingDirectory=$env:ND_WORKDIR;"
              "$s.IconLocation=$env:ND_ICON;$s.Description=$env:ND_DESC;$s.WindowStyle=1;$s.Save();"
              "[Console]::OutputEncoding=[Text.Encoding]::UTF8;Write-Output $p")
        env = os.environ.copy()
        env.update(ND_NAME=safe, ND_TARGET=str(target), ND_ARGS=argstr, ND_WORKDIR=str(app_dir()),
                   ND_ICON=icon, ND_DESC=tr('Запуск ComfyUI · {0}', BRAND_NAME))
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                               env=env, capture_output=True, timeout=30, creationflags=0x08000000)
            out = r.stdout.decode("utf-8", "replace").strip()
            if r.returncode != 0:
                raise RuntimeError(r.stderr.decode("utf-8", "replace").strip() or tr('код {0}', r.returncode))
            self.console.system(tr('Ярлык создан: {0}', out or safe))
            QMessageBox.information(self, APP_TITLE, tr('Ярлык «{0}» создан на рабочем столе.', safe))
        except Exception as e:
            self.console.system(tr('Не удалось создать ярлык: {0}', e), error=True)
            QMessageBox.warning(self, APP_TITLE, tr('Не удалось создать ярлык:\n{0}', e))

    # ── трей ──
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(make_icon(), self)
        menu = QMenu(self)

        def act(text, fn):
            a = menu.addAction(text)
            a.triggered.connect(fn)
            return a
        act(tr('Открыть лаунчер'), self.bring_to_front)
        menu.addSeparator()
        self.act_start = act(tr('Запустить ComfyUI'), self.start_comfy)
        self.act_stop = act(tr('Остановить ComfyUI'), self.stop_comfy)
        self.act_browser = act(tr('Открыть ComfyUI в браузере'), self.open_browser)
        menu.addSeparator()
        act(tr('Выход'), self.quit_from_tray)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.setToolTip(APP_TITLE)
        self.tray.setVisible(bool(self.cfg.get("minimize_to_tray")))
        self.update_controls()

    def _tray_enabled(self):
        return bool(self.tray) and bool(self.cfg.get("minimize_to_tray"))

    def _on_tray_toggled(self, on):
        self._set_cfg("minimize_to_tray", bool(on))
        if self.tray:
            self.tray.setVisible(bool(on))
        elif on:
            QMessageBox.information(self, APP_TITLE, tr('Системный трей недоступен — лаунчер будет сворачиваться на панель задач.'))

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                self.hide_to_tray(notify=False)
            else:
                self.bring_to_front()

    def hide_to_tray(self, notify=True):
        if not self._tray_enabled():
            self.showMinimized()
            return
        self.tray.setVisible(True)
        self.hide()
        if notify and not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.showMessage(APP_TITLE, tr('Лаунчер свёрнут в трей. ComfyUI продолжает работать.'),
                                  make_icon(), 3000)

    def bring_to_front(self):
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.ShowWindow(int(self.winId()), 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
            except Exception:
                pass

    def quit_from_tray(self):
        self.bring_to_front()
        self.close()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange and self.isMinimized() and self._tray_enabled():
            QTimer.singleShot(0, self.hide_to_tray)

    # ── повторный запуск лаунчера ──
    def handle_remote(self, argv):
        cli = parse_cli(argv)
        if not cli["autostart"]:
            self.bring_to_front()
            return
        if self.running:  # ComfyUI уже работает — просто откроем его
            if self.server_url:
                self.open_browser()
            if not cli["minimized"]:
                self.bring_to_front()
            return
        if cli["profile"] and not self.tasks.busy and not self.transferring:
            self.apply_profile(cli["profile"])
        if not cli["minimized"]:
            self.bring_to_front()
        QTimer.singleShot(200, self.start_comfy)

    # ── окно ──
    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_fitted", False):
            self._fitted = True
            QTimer.singleShot(0, self._fit_min_width)
        if sys.platform == "win32" and not self._dark_applied:
            self._dark_applied = True
            try:
                import ctypes
                v = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(v), ctypes.sizeof(v))
            except Exception:
                pass

    def closeEvent(self, e):
        if self.running or self.tasks.busy or self.transferring or self.dl_tasks.busy:
            what = (tr('ComfyUI ещё работает') if self.running else
                    tr('Идёт перенос файлов') if self.transferring else
                    tr("Идёт загрузка моделей") if self.dl_tasks.busy else tr('Идёт обновление'))
            if QMessageBox.question(self, APP_TITLE, tr('{0}. Остановить и выйти?', what)) != QMessageBox.Yes:
                e.ignore()
                return
            self.tasks.kill()
            if self.dl_tasks.busy:
                self.cancel_downloads()
            if self._xfer_worker:
                self._xfer_worker.cancel()
                self._xfer_thread.quit()
                self._xfer_thread.wait(5000)
            if self.running:
                self.proc.kill()
                self.proc.waitForFinished(3000)
        e.accept()
        if self.tray:
            self.tray.hide()
        QApplication.quit()


# ───────────────────── редактор ссылок (только для автора сборки) ─────────────

class LinksEditor(QDialog):
    """Открывается через ND_Links_Editor.bat (nd_launcher.py --edit-links).
    Правит brand/links.json рядом с исходником; build_exe.bat зашивает brand внутрь .exe."""

    def __init__(self, bdir: Path):
        super().__init__()
        self.bdir = Path(bdir)
        self.setWindowTitle(f"{APP_TITLE} · ссылки для сборки")
        self.setWindowIcon(make_icon())
        self.resize(900, 560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)
        t = QLabel("Ссылки, которые будут зашиты в ND_Launcher.exe")
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        lay.addWidget(muted("Пользователи сборки их не увидят в настройках и не смогут изменить. "
                            "Иконки скачиваются с сайтов автоматически при сохранении; можно выбрать и свою картинку."))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Название", "URL", "Иконка"])
        self.table.verticalHeader().hide()
        self.table.setIconSize(QSize(20, 20))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(button("+  Добавить", lambda: self._add_row({})))
        row.addWidget(button("−  Удалить", self._remove, "Danger"))
        row.addWidget(button("↑", lambda: self._move(-1)))
        row.addWidget(button("↓", lambda: self._move(1)))
        row.addWidget(button("Своя иконка…", self._pick_icon))
        row.addWidget(button("Перекачать иконки", lambda: self._save(force_icons=True, close=False)))
        row.addStretch()
        row.addWidget(button("Сохранить", lambda: self._save(close=True), "Accent"))
        lay.addLayout(row)
        self.status = muted("", False)
        lay.addWidget(self.status)
        for l in load_links(self.bdir):
            self._add_row(l)

    def _add_row(self, l):
        r = self.table.rowCount()
        self.table.insertRow(r)
        title = QTableWidgetItem(str(l.get("title", "")))
        self.table.setItem(r, 0, title)
        self.table.setItem(r, 1, QTableWidgetItem(str(l.get("url", ""))))
        ic = QTableWidgetItem(str(l.get("icon", "")))
        ic.setFlags(ic.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, 2, ic)
        self._refresh_icon(r)

    def _refresh_icon(self, r):
        rel = self.table.item(r, 2).text()
        pm = QPixmap(str(self.bdir / rel)) if rel else QPixmap()
        self.table.item(r, 0).setIcon(QIcon(pm) if not pm.isNull() else QIcon(draw_icon("link", 20, gradient=True)))

    def _rows(self):
        out = []
        for r in range(self.table.rowCount()):
            get = lambda c: (self.table.item(r, c).text().strip() if self.table.item(r, c) else "")
            if get(1):
                d = {"title": get(0) or link_host(get(1)), "url": get(1)}
                if get(2):
                    d["icon"] = get(2)
                out.append(d)
        return out

    def _remove(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _move(self, delta):
        r = self.table.currentRow()
        n = r + delta
        if r < 0 or n < 0 or n >= self.table.rowCount():
            return
        rows = self._rows_raw()
        rows[r], rows[n] = rows[n], rows[r]
        self.table.setRowCount(0)
        for l in rows:
            self._add_row(l)
        self.table.selectRow(n)

    def _rows_raw(self):
        return [{"title": self.table.item(r, 0).text(), "url": self.table.item(r, 1).text(),
                 "icon": self.table.item(r, 2).text()} for r in range(self.table.rowCount())]

    def _pick_icon(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.information(self, APP_TITLE, "Выбери строку со ссылкой.")
            return
        f, _ = QFileDialog.getOpenFileName(self, "Иконка", "", "Картинки (*.png *.ico *.jpg *.jpeg *.webp *.svg)")
        if not f:
            return
        url = self.table.item(r, 1).text().strip()
        dst = self.bdir / "icons" / (link_slug(url) + Path(f).suffix.lower())
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        self.table.item(r, 2).setText(dst.relative_to(self.bdir).as_posix())
        self._refresh_icon(r)

    def _save(self, close=True, force_icons=False):
        links = self._rows()
        self.status.setText("Скачиваю иконки…")
        QApplication.processEvents()
        msgs = []
        fetch_link_icons(self.bdir, links, force=force_icons, log=msgs.append)
        self.bdir.mkdir(parents=True, exist_ok=True)
        (self.bdir / "links.json").write_text(json.dumps({"links": links}, ensure_ascii=False, indent=2) + "\n", "utf-8")
        self.table.setRowCount(0)
        for l in links:
            self._add_row(l)
        fails = [m for m in msgs if m.startswith("не удалось")]
        self.status.setText(f"Сохранено ссылок: {len(links)}" + (f" · {'; '.join(fails)}" if fails else ""))
        if close and not fails:
            self.accept()


def main():
    if "--fetch-icons" in sys.argv:  # вызывается из build_exe.bat перед сборкой
        bdir = app_dir() / "brand"
        links = load_links(bdir)
        if fetch_link_icons(bdir, links, log=print):
            (bdir / "links.json").write_text(json.dumps({"links": links}, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ND.ComfyUILauncher")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyle("Fusion")
    app.setStyleSheet(build_qss())
    app.setWindowIcon(make_icon())
    if "--edit-links" in sys.argv:
        if getattr(sys, "frozen", False):
            QMessageBox.information(None, APP_TITLE, tr('Ссылки зашиты в эту сборку и не редактируются.'))
            return
        LinksEditor(app_dir() / "brand").exec()
        return
    # уже запущен? — передаём ему аргументы (он развернётся / запустит ComfyUI) и выходим
    key = instance_key()
    sock = QLocalSocket()
    sock.connectToServer(key)
    if sock.waitForConnected(700):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: разрешаем первому окну выйти на передний план
            except Exception:
                pass
        sock.write(json.dumps({"argv": sys.argv[1:]}).encode("utf-8"))
        sock.flush()
        sock.waitForBytesWritten(1500)
        sock.disconnectFromServer()
        return
    server = QLocalServer()
    if not server.listen(key):
        QLocalServer.removeServer(key)  # хвост от аварийно закрытого лаунчера
        server.listen(key)

    app.setQuitOnLastWindowClosed(False)  # окно может быть спрятано в трей; выход — только через closeEvent
    cli = parse_cli(sys.argv[1:])
    w = MainWindow(cli)

    def on_conn():
        conn = server.nextPendingConnection()
        if not conn:
            return
        buf = bytearray()

        def done():
            try:
                argv = json.loads(bytes(buf).decode("utf-8") or "{}").get("argv", [])
            except Exception:
                argv = []
            w.handle_remote(argv)
            conn.deleteLater()

        def read():
            buf.extend(bytes(conn.readAll()))
        conn.readyRead.connect(read)
        conn.disconnected.connect(lambda: (read(), done()))
    server.newConnection.connect(on_conn)
    w._instance_server = server

    if cli["minimized"]:
        if w._tray_enabled():
            w.hide_to_tray(notify=False)
        else:
            w.showMinimized()
    else:
        w.show()
    if cli["autostart"]:
        QTimer.singleShot(400, w.start_comfy)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

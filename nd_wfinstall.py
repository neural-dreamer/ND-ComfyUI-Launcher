# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Установка воркфлоу «под ключ»: разбор воркфлоу и архива, поиск репозиториев нод и ссылок на модели.

Модуль без Qt и без обращений в сеть по умолчанию: поиск по Comfy Registry и базе ComfyUI-Manager передаётся
функциями-параметрами (см. fetch_registry_repo / fetch_manager_index), поэтому всё проверяется тестами офлайн.
Интерфейс и сама установка (git clone, pip, копирование) — в nd_launcher.py.
"""
import io
import json
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

MAX_JSON = 80 * 1024 * 1024            # воркфлоу больше этого не читаем
MAX_MEMBER = 200 * 1024 * 1024         # один файл из архива
MAX_TOTAL = 600 * 1024 * 1024          # весь архив после распаковки
MAX_ENTRIES = 2000

# Типы узлов, которые есть только во фронтенде: ноды и репозитории им не нужны.
FRONTEND_TYPES = {"Reroute", "Note", "MarkdownNote", "PrimitiveNode", "GetNode", "SetNode", "Group"}
NOTE_TYPES = {"Note", "MarkdownNote"}
REPO_HOSTS = ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org")
MODEL_EXT = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx", ".sft", ".pkl")
MODEL_DIRS = ("diffusion_models", "text_encoders", "vae", "loras", "checkpoints", "clip", "clip_vision", "controlnet",
              "upscale_models", "unet", "embeddings", "vae_approx", "style_models", "gligen", "hypernetworks",
              "model_patches", "audio_encoders", "latent_upscale_models", "LLM", "sams", "ultralytics", "depthanything")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
HEX_RE = re.compile(r"^[0-9a-f]{7,40}$", re.I)
SEMVER_RE = re.compile(r"^v?\d+(?:\.\d+){1,3}(?:[-+][\w.]+)?$")


# ───────────────────────── воркфлоу: узлы ─────────────────────────

def is_ui_workflow(data):
    return isinstance(data, dict) and isinstance(data.get("nodes"), list)


def is_api_workflow(data):
    return (isinstance(data, dict) and data and not is_ui_workflow(data)
            and all(isinstance(v, dict) and "class_type" in v for v in data.values()))


def walk_nodes(wf):
    """Все узлы воркфлоу, включая сабграфы (definitions.subgraphs[*].nodes) — в них часто лежит большая часть нод."""
    out = list(wf.get("nodes") or [])
    for sg in ((wf.get("definitions") or {}).get("subgraphs") or []):
        out.extend(sg.get("nodes") or [])
    return [n for n in out if isinstance(n, dict)]


def subgraph_ids(wf):
    return {sg.get("id") for sg in ((wf.get("definitions") or {}).get("subgraphs") or []) if sg.get("id")}


def norm(name):
    """Имя для сравнения репозиториев и cnr_id: нижний регистр, только буквы и цифры."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _loose(name):
    n = norm(name)
    return n[len("comfyui"):] if n.startswith("comfyui") else n


def ver_kind(ver):
    """'commit' | 'tag' | None — что записано в properties.ver."""
    if not isinstance(ver, str) or not ver or ver in ("unknown", "nightly", "latest"):
        return None
    if re.fullmatch(r"[0-9a-f]{40}", ver, re.I) or (HEX_RE.match(ver) and len(ver) >= 7 and not SEMVER_RE.match(ver)):
        return "commit"
    if SEMVER_RE.match(ver):
        return "tag"
    return None


class Package:
    """Один репозиторий, который нужен воркфлоу (узлы с одним cnr_id/aux_id сводятся вместе)."""

    def __init__(self):
        self.cnr = set()
        self.aux = {}          # 'owner/repo' (в исходном регистре) → сколько узлов
        self.vers = {}         # ver → сколько узлов
        self.vers_aux = {}     # 'owner/repo' (в нижнем регистре) → {ver: сколько узлов}
        self.vers_noaux = {}   # версии узлов, у которых нет aux_id (только cnr_id)
        self.types = set()
        self.nodes = 0
        self.groups = set()

    def add(self, node_type, cnr, aux, ver):
        if cnr:
            self.cnr.add(cnr)
        if aux:
            self.aux[aux] = self.aux.get(aux, 0) + 1
        if ver:
            self.vers[ver] = self.vers.get(ver, 0) + 1
            if aux:
                d = self.vers_aux.setdefault(aux.lower(), {})
                d[ver] = d.get(ver, 0) + 1
            else:
                self.vers_noaux[ver] = self.vers_noaux.get(ver, 0) + 1
        self.types.add(node_type)
        self.nodes += 1

    def all_vers(self, aux=None):
        """Все версии, записанные в воркфлоу, от самой частой. С aux — только узлы именно этого репозитория (важно для форков);
        узлы без aux_id относятся к нему, если форков нет. Разные версии одного пакета — обычное дело:
        автор обновил часть узлов, а остальные остались со старой записью."""
        d = dict(self.vers_aux.get((aux or "").lower()) or {})
        if not aux or len(self.aux) <= 1:
            for v, n in self.vers_noaux.items():
                d[v] = d.get(v, 0) + n
        if not d and not aux:
            d = dict(self.vers)
        return sorted(d, key=lambda v: -d[v])

    def top_ver(self, aux=None):
        v = self.all_vers(aux)
        return v[0] if v else None


def collect_packages(wf):
    """Узлы воркфлоу → ([Package], [типы без каких-либо сведений об источнике]).
    Сводим по aux_id (owner/repo) и по cnr_id: cnr_id бывает ошибочным, но если у узла есть и aux_id, они связываются."""
    sg_ids = subgraph_ids(wf)
    rows = []
    for n in walk_nodes(wf):
        t = str(n.get("type") or "")
        if not t or t in FRONTEND_TYPES or t in sg_ids or UUID_RE.match(t):
            continue
        p = n.get("properties") or {}
        cnr, aux, ver = p.get("cnr_id"), p.get("aux_id"), p.get("ver")
        if cnr == "comfy-core":
            continue
        rows.append((t, cnr or None, aux or None, str(ver) if ver else None))
    # союзы: узлы с одинаковым cnr или одинаковым aux (без учёта регистра) относятся к одному пакету
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)
    for t, cnr, aux, ver in rows:
        keys = []
        if cnr:
            keys.append("c:" + cnr.lower())
        if aux:
            keys.append("a:" + aux.lower())
        for k in keys:
            find(k)
        if len(keys) == 2 and _loose(cnr) == _loose(aux.split("/")[-1]):
            union(*keys)   # cnr совпал с именем репозитория aux — это один пакет
    # узел с обоими ключами, где cnr «чужой» (как comfyui-workflow-encrypt у форка), остаётся с aux: cnr не объединяем
    groups = {}
    unknown = set()
    for t, cnr, aux, ver in rows:
        if aux:
            key = find("a:" + aux.lower())
        elif cnr:
            key = find("c:" + cnr.lower())
        else:
            unknown.add(t)
            continue
        groups.setdefault(key, Package()).add(t, cnr, aux, ver)
    # cnr-only пакеты, совпавшие по имени с aux-пакетом, присоединяем к нему
    pkgs = list(groups.values())
    aux_pkgs = [p for p in pkgs if p.aux]
    merged = []
    for p in pkgs:
        if not p.aux and p.cnr:
            host = next((a for a in aux_pkgs if any(_loose(c) == _loose(x.split("/")[-1]) for c in p.cnr for x in a.aux)), None)
            if host:
                host.cnr |= p.cnr
                host.types |= p.types
                host.nodes += p.nodes
                for v, c in p.vers.items():
                    host.vers[v] = host.vers.get(v, 0) + c
                continue
        merged.append(p)
    merged.sort(key=lambda p: (-p.nodes, sorted(p.aux) or sorted(p.cnr)))
    return merged, sorted(unknown)


# ───────────────────────── заметки: ссылки на репозитории ─────────────────────────

URL_RE = re.compile(r"https?://[^\s)\]>\"'<]+", re.I)


def note_texts(wf):
    texts = []
    for n in walk_nodes(wf):
        if n.get("type") in NOTE_TYPES:
            for v in (n.get("widgets_values") or []):
                if isinstance(v, str) and v.strip():
                    texts.append(v)
    return texts


def parse_repo(url):
    """Ссылка → {'owner','repo','host','branch','clone','page'} или None (не репозиторий: соцсети, модели, документы)."""
    m = re.match(r"^(?:git\+)?(?:https?://(?:www\.)?|git@)([^/:\s]+)[/:]([^/\s?#]+)/([^/\s?#]+?)(?:\.git)?"
                 r"(?:/(?:tree|-/tree)/([^?#\s]+))?/?(?:[?#].*)?$", url.strip().rstrip(".,;"), re.I)
    if not m:
        return None
    host, owner, repo, branch = m.groups()
    host = host.lower()
    if host not in REPO_HOSTS or repo.lower() in ("releases", "issues", "pulls", "wiki", "archive"):
        return None
    if re.search(r"/(?:blob|raw|releases|issues|pull|wiki|actions|commit)/", url):
        return None
    return dict(owner=owner, repo=repo, host=host, branch=(branch or "").split("/")[0] or None,
                clone=f"https://{host}/{owner}/{repo}.git", page=f"https://{host}/{owner}/{repo}")


def note_repos(wf):
    """Репозитории, перечисленные в заметках воркфлоу, без повторов, в порядке появления."""
    seen, out = set(), []
    for text in note_texts(wf):
        for u in URL_RE.findall(text):
            info = parse_repo(u)
            if info:
                k = f"{info['owner']}/{info['repo']}".lower()
                if k not in seen:
                    seen.add(k)
                    out.append(info)
    return out


# ───────────────────────── установленные ноды ─────────────────────────

def _git_remote(folder):
    cfg = Path(folder) / ".git" / "config"
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r'\[remote "origin"\][^\[]*?url\s*=\s*(\S+)', text)
    if not m:
        return None
    info = parse_repo(m.group(1).replace("git@github.com:", "https://github.com/"))
    return f"{info['owner']}/{info['repo']}".lower() if info else None


def _pyproject_name(folder):
    try:
        text = (Path(folder) / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return m.group(1) if m else None


def scan_installed(custom_nodes):
    """Папки custom_nodes → [{'folder', 'remote', 'cnr', 'disabled'}]."""
    out = []
    root = Path(custom_nodes)
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir() or d.name.startswith((".", "__")):
            continue
        disabled = d.name.endswith(".disabled")
        out.append(dict(folder=d.name[:-9] if disabled else d.name, remote=_git_remote(d),
                        cnr=_pyproject_name(d), disabled=disabled))
    return out


def find_installed(installed, repo_key, cnr_ids=(), folder=None):
    """Установлена ли нода: по remote (точное совпадение owner/repo), по имени в pyproject и по имени папки.
    Возвращает (запись, 'same'|'other') или (None, None). 'other' — папка с тем же именем, но из другого репозитория."""
    key = (repo_key or "").lower()
    cn = {norm(c) for c in cnr_ids if c}
    for it in installed:
        if key and it["remote"] == key:
            return it, "same"
    for it in installed:
        if it["cnr"] and norm(it["cnr"]) in cn:
            return it, "same" if not key or not it["remote"] or it["remote"] == key else "other"
    name = norm(folder or (key.split("/")[-1] if key else ""))
    for it in installed:
        if name and norm(it["folder"]) == name:
            if key and it["remote"] and it["remote"] != key:
                return it, "other"
            return it, "same"
    return None, None


# ───────────────────────── поиск репозитория для пакета ─────────────────────────

def _note_match(pkg, notes):
    """Репозитории из заметок, подходящие пакету: совпадение имени с cnr_id или с именем репозитория из aux_id."""
    names = {_loose(c) for c in pkg.cnr} | {_loose(a.split("/")[-1]) for a in pkg.aux}
    names.discard("")
    full = {a.lower() for a in pkg.aux}
    res = []
    for n in notes:
        if f"{n['owner']}/{n['repo']}".lower() in full or _loose(n["repo"]) in names:
            res.append(n)
    return res


def resolve_package(pkg, notes, installed=(), registry=None, manager=None):
    """Определяет репозиторий пакета. Порядок: заметки автора → aux_id → Comfy Registry → база ComfyUI-Manager.
    Возвращает dict(name, repo, clone, page, source, ver, ver_kind, status, alternatives, types, installed, installed_kind).
    status: 'installed' | 'install' | 'choose' (несколько форков) | 'notfound'."""
    cands = []   # (info, source)

    def add(info, source):
        key = f"{info['owner']}/{info['repo']}".lower()
        if all(f"{c['owner']}/{c['repo']}".lower() != key for c, _ in cands):
            cands.append((info, source))
    from_notes = _note_match(pkg, notes)
    aux_infos = [parse_repo(f"https://github.com/{a}") for a in sorted(pkg.aux, key=lambda a: -pkg.aux[a])]
    aux_infos = [a for a in aux_infos if a]
    aux_keys = {f"{a['owner']}/{a['repo']}".lower() for a in aux_infos}
    for n in from_notes:
        k = f"{n['owner']}/{n['repo']}".lower()
        add(n, "заметка + aux_id" if k in aux_keys else "заметка")
    for a in aux_infos:
        add(a, "aux_id")
    if not cands and registry:
        for c in sorted(pkg.cnr):
            url = registry(c)
            info = parse_repo(url) if url else None
            if info:
                add(info, "Comfy Registry")
    if not cands and manager:
        for t in sorted(pkg.types):
            for url in manager(t) or []:
                info = parse_repo(url)
                if info:
                    add(info, "база ComfyUI-Manager")
            if cands:
                break
    ver = pkg.top_ver(f"{cands[0][0]['owner']}/{cands[0][0]['repo']}") if cands else pkg.top_ver()
    res = dict(types=sorted(pkg.types), nodes=pkg.nodes, ver=ver, ver_kind=ver_kind(ver), cnr=sorted(pkg.cnr),
               alternatives=[], installed=None, installed_kind=None,
               vers_by_repo={k: pkg.all_vers(k) for k in pkg.vers_aux},
               vers=pkg.all_vers(f"{cands[0][0]['owner']}/{cands[0][0]['repo']}") if cands else pkg.all_vers())
    if not cands:
        res.update(name=(sorted(pkg.cnr) or sorted(pkg.types))[0], repo=None, clone=None, page=None, source=None,
                   status="notfound")
        return res
    best, source = cands[0]
    # несколько разных владельцев одного и того же имени репозитория — это форки: просим выбрать, по умолчанию берём первый
    forks = [c for c, _ in cands if norm(c["repo"]) == norm(best["repo"]) and c["owner"].lower() != best["owner"].lower()]
    res.update(name=best["repo"], repo=f"{best['owner']}/{best['repo']}", clone=best["clone"], page=best["page"],
               source=source, branch=best.get("branch"),
               alternatives=[f"{c['owner']}/{c['repo']}" for c in forks])
    it, kind = find_installed(list(installed), res["repo"], pkg.cnr, best["repo"])
    if it:
        res.update(installed=it["folder"], installed_kind=kind)
        res["status"] = "installed" if kind == "same" else "install"   # 'other' — предупреждаем в интерфейсе
    else:
        res["status"] = "choose" if forks else "install"
    if forks and res["status"] == "install" and not it:
        res["status"] = "choose"
    return res


def analyze_workflow(wf, installed=(), registry=None, manager=None):
    """Полный разбор воркфлоу: {'packages': [...], 'unknown_types': [...], 'extra_notes': [репозитории из заметок без узлов]}."""
    pkgs, unknown = collect_packages(wf)
    notes = note_repos(wf)
    resolved = [resolve_package(p, notes, installed, registry, manager) for p in pkgs]
    used = set()
    for p, r in zip(pkgs, resolved):
        for n in _note_match(p, notes):
            used.add(f"{n['owner']}/{n['repo']}".lower())
    extra = []
    for n in notes:
        k = f"{n['owner']}/{n['repo']}".lower()
        if k in used:
            continue
        it, kind = find_installed(list(installed), k, (), n["repo"])
        extra.append(dict(name=n["repo"], repo=f"{n['owner']}/{n['repo']}", clone=n["clone"], page=n["page"],
                          installed=bool(it and kind == "same")))
    return dict(packages=resolved, unknown_types=unknown, extra_notes=extra)


def merge_analyses(analyses):
    """Несколько воркфлоу → общий список пакетов (одинаковые репозитории сводятся, версия — самая частая)."""
    merged = {}
    for a in analyses:
        for p in a["packages"]:
            key = (p["repo"] or "").lower() or "?" + p["name"].lower()
            cur = merged.get(key)
            if cur is None:
                merged[key] = dict(p, types=list(p["types"]))
            else:
                cur["types"] = sorted(set(cur["types"]) | set(p["types"]))
                cur["nodes"] += p["nodes"]
                if not cur["ver"] and p["ver"]:
                    cur.update(ver=p["ver"], ver_kind=p["ver_kind"])
                cur["vers"] = list(dict.fromkeys(list(cur.get("vers") or []) + list(p.get("vers") or [])))
                for k, v in p.get("vers_by_repo", {}).items():
                    cur.setdefault("vers_by_repo", {}).setdefault(k, v)
    extras = {}
    for a in analyses:
        for e in a["extra_notes"]:
            if e["repo"].lower() not in merged:
                extras.setdefault(e["repo"].lower(), e)
    unknown = sorted({t for a in analyses for t in a["unknown_types"]})
    return dict(packages=list(merged.values()), extra_notes=list(extras.values()), unknown_types=unknown)


# ───────────────────────── версии ─────────────────────────

def checkout_ref(ver):
    """Что делать после клонирования, чтобы получить версию из воркфлоу: ('commit'|'tag', ref) или None (ставить последнюю)."""
    kind = ver_kind(ver)
    if kind == "commit":
        return ("commit", ver)
    if kind == "tag":
        return ("tag", ver if ver.startswith("v") else ver)   # тег пробуем как есть, затем с «v»
    return None


# ───────────────────────── модели ─────────────────────────

def _model_dir_from_text(heading):
    h = (heading or "").strip().strip("*#:` ").lower()
    for d in MODEL_DIRS:
        if h == d.lower():
            return d
    return None


def _hf_direct(url):
    """https://huggingface.co/<o>/<r>/resolve/<rev>/<path> → (путь внутри репозитория) или None."""
    p = urlparse(url)
    if p.netloc.lower() not in ("huggingface.co", "www.huggingface.co", "hf-mirror.com"):
        return None
    m = re.match(r"^/[^/]+/[^/]+/resolve/[^/]+/(.+)$", unquote(p.path))
    return m.group(1) if m else None


def collect_models(wf):
    """Модели воркфлоу: [{'name','folder','url','source','manual'}].
    Источники: properties.models у узлов (name/url/directory) и ссылки в заметках; папка берётся из заголовка
    вида **diffusion_models** выше по тексту или из пути ссылки Hugging Face. Страницы Civitai — manual=True."""
    out, seen = [], set()

    def add(name, folder, url, source, manual=False):
        key = (name.lower(), (folder or "").lower())
        if key not in seen:
            seen.add(key)
            out.append(dict(name=name, folder=folder, url=url, source=source, manual=manual))
    for n in walk_nodes(wf):
        for m in ((n.get("properties") or {}).get("models") or []):
            if isinstance(m, dict) and m.get("name"):
                add(str(m["name"]), m.get("directory"), m.get("url"), "node")
    for text in note_texts(wf):
        folder = None
        for line in text.splitlines():
            st = line.strip()
            if st.startswith("#") or re.fullmatch(r"\*\*[^*]+\*\*:?", st):
                folder = _model_dir_from_text(re.sub(r"^#+\s*", "", st))   # любой другой заголовок сбрасывает папку
                continue
            for title, url in re.findall(r"\[([^\]]*)\]\((https?://[^)\s]+)\)", line):
                path = _hf_direct(url)
                if path and path.lower().endswith(MODEL_EXT):
                    first = path.split("/")[0]
                    f = folder or (first if first in MODEL_DIRS else None)
                    if not f and path.lower().endswith(".gguf"):
                        f = "LLM"
                    add(path.split("/")[-1], f, url.replace("/blob/", "/resolve/"), "note")
                elif "civitai" in url.lower() and "/models/" in url.lower():
                    add(title.strip() or url, folder, url, "note", manual=True)
    return out


def model_present(model, roots):
    """Есть ли файл модели в одном из корней моделей (папка/имя; имя может содержать подпапки)."""
    if model.get("manual") or not model.get("folder"):
        return False
    rel = model["name"].replace("\\", "/")
    return any((Path(r) / model["folder"] / rel).is_file() for r in roots)


# ───────────────────────── файлы и архивы ─────────────────────────

class Bundle:
    """Что принесли на установку: воркфлоу (имя → сырые байты и разобранный JSON) и файлы prompts."""

    def __init__(self):
        self.workflows = []   # dict(rel, raw, data, api)
        self.prompts = []     # dict(rel, raw)
        self.ignored = []     # (имя, причина)
        self.errors = []


def _safe_rel(name):
    name = name.replace("\\", "/")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return None
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def _add_json(bundle, rel, raw):
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        bundle.ignored.append((rel, "не JSON"))
        return
    if is_ui_workflow(data):
        bundle.workflows.append(dict(rel=rel, raw=raw, data=data, api=False))
    elif is_api_workflow(data):
        bundle.workflows.append(dict(rel=rel, raw=raw, data=data, api=True))
    else:
        bundle.ignored.append((rel, "не воркфлоу ComfyUI"))


def _prompt_rel(rel):
    """Путь внутри папки prompts (на любой глубине вложенности архива) или None."""
    parts = rel.split("/")
    for i, p in enumerate(parts[:-1]):
        if p.lower() == "prompts":
            return "/".join(parts[i + 1:]) or None
    return None


def read_zip(bundle, source, label=None):
    """Читает .zip (путь или файловый объект). Из архива берутся только .json-воркфлоу и файлы из папки prompts;
    остальное, включая любой код, игнорируется. Защита: пути вне папки, слишком большие и слишком многочисленные файлы."""
    label = label or str(source)
    try:
        z = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as e:
        bundle.errors.append(f"{label}: не удалось открыть архив ({e})")
        return
    with z:
        infos = z.infolist()
        if len(infos) > MAX_ENTRIES:
            bundle.errors.append(f"{label}: слишком много файлов в архиве ({len(infos)})")
            return
        if sum(i.file_size for i in infos) > MAX_TOTAL:
            bundle.errors.append(f"{label}: архив слишком большой после распаковки")
            return
        for info in infos:
            if info.is_dir():
                continue
            rel = _safe_rel(info.filename)
            if rel is None:
                bundle.ignored.append((info.filename, "небезопасный путь"))
                continue
            if rel.startswith("__MACOSX/") or rel.split("/")[-1].startswith("."):
                continue
            if info.file_size > MAX_MEMBER:
                bundle.ignored.append((rel, "слишком большой файл"))
                continue
            pr = _prompt_rel(rel)
            if pr is not None:
                if _safe_rel(pr):
                    bundle.prompts.append(dict(rel=_safe_rel(pr), raw=z.read(info)))
                continue
            if rel.lower().endswith(".json"):
                if info.file_size > MAX_JSON:
                    bundle.ignored.append((rel, "слишком большой файл"))
                    continue
                _add_json(bundle, rel, z.read(info))
            else:
                bundle.ignored.append((rel, "не воркфлоу и не prompts"))


def read_inputs(paths):
    """Список путей (.json / .zip) → Bundle. Отдельные .json кладутся в корень папки воркфлоу."""
    bundle = Bundle()
    for p in paths:
        p = Path(p)
        low = p.name.lower()
        try:
            if low.endswith(".zip"):
                read_zip(bundle, str(p), p.name)
            elif low.endswith(".json"):
                if p.stat().st_size > MAX_JSON:
                    bundle.errors.append(f"{p.name}: файл слишком большой")
                else:
                    _add_json(bundle, p.name, p.read_bytes())
            else:
                bundle.ignored.append((p.name, "поддерживаются .json и .zip"))
        except OSError as e:
            bundle.errors.append(f"{p.name}: {e}")
    return bundle


# ───────────────────────── план копирования файлов ─────────────────────────

def numbered_name(path):
    """Свободное имя рядом: 'x.json' → 'x (2).json', 'x (3).json'…"""
    path = Path(path)
    for i in range(2, 1000):
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not cand.exists():
            return cand
    raise OSError("не удалось подобрать имя")


def plan_files(bundle, workflows_dir, prompts_dir):
    """[{'kind': 'workflow'|'prompt', 'rel', 'dest', 'exists', 'action': 'write'|'ask'}]. Конфликты решает пользователь:
    'replace' / 'keep' / 'both' (apply_plan)."""
    plan = []
    for w in bundle.workflows:
        dest = Path(workflows_dir) / w["rel"]
        plan.append(dict(kind="workflow", rel=w["rel"], dest=dest, raw=w["raw"], exists=dest.exists()))
    for p in bundle.prompts:
        dest = Path(prompts_dir) / p["rel"]
        plan.append(dict(kind="prompt", rel=p["rel"], dest=dest, raw=p["raw"], exists=dest.exists()))
    for it in plan:
        it["action"] = "ask" if it["exists"] else "write"
    return plan


def apply_plan(plan, choices=None, default="keep"):
    """Записывает файлы. choices: {dest: 'replace'|'keep'|'both'} для конфликтов. Возвращает {'written','kept','errors'}."""
    choices = choices or {}
    res = dict(written=[], kept=[], errors=[])
    for it in plan:
        dest = Path(it["dest"])
        action = "write" if not dest.exists() else choices.get(str(dest), choices.get(dest, default))
        try:
            if action == "keep":
                res["kept"].append(str(dest))
                continue
            if action == "both":
                dest = numbered_name(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".nd_tmp")
            tmp.write_bytes(it["raw"])
            os.replace(tmp, dest)
            res["written"].append(str(dest))
        except OSError as e:
            res["errors"].append(f"{dest}: {e}")
    return res


# ───────────────────────── сеть (необязательный поиск) ─────────────────────────

def fetch_registry_repo(cnr_id, timeout=10):
    """Адрес репозитория по cnr_id через Comfy Registry (api.comfy.org). None при любой ошибке."""
    import urllib.request
    from urllib.parse import quote
    try:
        req = urllib.request.Request("https://api.comfy.org/nodes/" + quote(cnr_id, safe=""), headers={"User-Agent": "ND-Launcher"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (json.loads(r.read().decode("utf-8", "replace")) or {}).get("repository") or None
    except Exception:
        return None


MANAGER_MAP_URL = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/extension-node-map.json"


def fetch_manager_index(timeout=30):
    """База ComfyUI-Manager → функция type → [url репозитория]. None, если база недоступна."""
    import urllib.request
    try:
        req = urllib.request.Request(MANAGER_MAP_URL, headers={"User-Agent": "ND-Launcher"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None
    index = {}
    for url, val in data.items():
        types = val[0] if isinstance(val, list) and val else []
        for t in types:
            index.setdefault(t, []).append(url)
    return lambda t: index.get(t, [])

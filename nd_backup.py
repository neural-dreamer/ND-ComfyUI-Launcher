# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Neural Dreamer
"""Точки восстановления портативной сборки ComfyUI (без Qt).

Что сохраняется (области):
  comfy   — код ComfyUI (вместе с .git) и папка update сборки;
  nodes   — ComfyUI/custom_nodes целиком, включая ноды без git;
  python  — python_embeded (все пакеты);
  user    — ComfyUI/user: настройки, воркфлоу, конфиги Manager.
Модели, input, output и temp не сохраняются; крупные файлы моделей (> 50 МБ) внутри нод и пакетов тоже.

Хранилище:
  <store>/objects/ab/<sha256>   — содержимое файлов; одинаковый файл хранится один раз
  <store>/points/<id>.json.gz    — точка: список файлов (путь → sha256, размер, время изменения) и сводка
  <store>/trash/<id>/...         — файлы, которых не было в точке: при восстановлении их не удаляем, а переносим сюда
Первая точка — полная копия, следующие добавляют только изменившиеся файлы.
Файлы в objects сжаты zlib (<sha256>.z; sha — от исходного содержимого). Уже сжатые форматы (zip, whl, png…)
лежат как есть (<sha256>). Несжатые объекты из старых версий читаются и при следующей точке пережимаются.
Для коммитов git отдельно записываются хеш и адрес репозитория — это только для сравнения точек:
восстановление идёт из файлов и не требует ни git, ни интернета.
"""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

FORMAT = "nd-backup"
FORMAT_VERSION = 1
AREAS = ("comfy", "nodes", "python", "user")
MODEL_EXT = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".onnx", ".gguf", ".pkl", ".sft", ".pb", ".h5",
             ".msgpack", ".npz", ".engine", ".trt"}
BIG_MODEL = 50 * 1024 * 1024
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = (".pyc", ".ndpart", ".ndpart.json", ".tmp")
CHUNK = 4 * 1024 * 1024
LEVEL = 1   # zlib: на бинарниках почти как 6 (≈35% против 31% исходного), но в 3 раза быстрее
# Сжимать бессмысленно: внутри уже сжатые данные
NO_COMPRESS = {".zip", ".whl", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".zst", ".lzma", ".png", ".jpg", ".jpeg",
               ".webp", ".gif", ".mp4", ".webm", ".mp3", ".ogg", ".flac", ".woff", ".woff2", ".jar", ".egg", ".pack"}
WORKERS = max(1, min(4, (os.cpu_count() or 2)))


class Cancelled(Exception):
    pass


def default_store(root):
    return Path(root) / "Backups"


def area_roots(root):
    """(область, папка относительно корня сборки)."""
    return [("comfy", "ComfyUI"), ("comfy", "update"), ("nodes", "ComfyUI/custom_nodes"),
            ("python", "python_embeded"), ("user", "ComfyUI/user")]


# Внутри ComfyUI эти папки не код: модели, данные пользователя и то, что сохраняется отдельной областью.
COMFY_EXCLUDE = {"ComfyUI/models", "ComfyUI/input", "ComfyUI/output", "ComfyUI/temp",
                 "ComfyUI/custom_nodes", "ComfyUI/user"}


def _skip_file(name, size):
    low = name.lower()
    if low.endswith(SKIP_SUFFIXES):
        return True
    return os.path.splitext(low)[1] in MODEL_EXT and size > BIG_MODEL


def scan(root, areas=AREAS, store=None, cancel=None):
    """Файлы сборки по областям: {область: {путь: (размер, mtime_ns)}}. Пути — относительно корня, через '/'."""
    root = Path(root)
    store_real = os.path.normcase(os.path.realpath(store)) if store else None
    result = {a: {} for a in areas}
    for area, rel in area_roots(root):
        if area not in areas:
            continue
        base = root / rel
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            if cancel and cancel():
                raise Cancelled()
            rel_dir = Path(dirpath).relative_to(root).as_posix()
            keep = []
            for d in dirnames:
                sub = f"{rel_dir}/{d}"
                if d in SKIP_DIRS or d.startswith(".nd_hf_") or (area == "comfy" and sub in COMFY_EXCLUDE):
                    continue
                full = os.path.join(dirpath, d)
                if os.path.islink(full):
                    continue
                if store_real and os.path.normcase(os.path.realpath(full)) == store_real:
                    continue
                keep.append(d)
            dirnames[:] = keep
            for f in filenames:
                full = os.path.join(dirpath, f)
                try:
                    st = os.stat(full, follow_symlinks=False)
                except OSError:
                    continue
                if not os.path.isfile(full) or os.path.islink(full) or _skip_file(f, st.st_size):
                    continue
                result[area][f"{rel_dir}/{f}"] = (st.st_size, st.st_mtime_ns)
    return result


# ───────────────────────── сводка: версии и коммиты ─────────────────────────

def _git_info(repo):
    """Коммит, ветка и адрес origin из папки .git — без запуска git."""
    g = Path(repo) / ".git"
    if g.is_file():  # .git-файл со ссылкой на настоящую папку (worktree / submodule)
        m = re.match(r"gitdir:\s*(.+)", g.read_text(encoding="utf-8", errors="replace").strip())
        g = (Path(repo) / m.group(1)).resolve() if m else g
    if not g.is_dir():
        return None
    info = {}
    try:
        head = (g / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        if head.startswith("ref:"):
            ref = head[4:].strip()
            info["branch"] = ref.rsplit("/", 1)[-1]
            ref_file = g / ref
            if ref_file.is_file():
                info["commit"] = ref_file.read_text(encoding="utf-8").strip()
            elif (g / "packed-refs").is_file():
                for line in (g / "packed-refs").read_text(encoding="utf-8", errors="replace").splitlines():
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref:
                        info["commit"] = parts[0]
        else:
            info["commit"] = head
    except OSError:
        pass
    try:
        cfg = (g / "config").read_text(encoding="utf-8", errors="replace")
        m = re.search(r'\[remote "origin"\][^\[]*?url\s*=\s*(\S+)', cfg)
        if m:
            info["remote"] = m.group(1)
    except OSError:
        pass
    return info


def _comfy_version(root):
    p = Path(root) / "ComfyUI" / "comfyui_version.py"
    try:
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)', p.read_text(encoding="utf-8", errors="replace"))
        return m.group(1) if m else ""
    except OSError:
        return ""


def _packages(root):
    site = Path(root) / "python_embeded" / "Lib" / "site-packages"
    out = {}
    try:
        for d in site.iterdir():
            if d.is_dir() and d.name.endswith(".dist-info"):
                name, _, ver = d.name[:-10].rpartition("-")
                if name:
                    out[re.sub(r"[-_.]+", "-", name).lower()] = ver
    except OSError:
        pass
    return out


def summary(root):
    """Версия ComfyUI, коммиты нод, версии пакетов — для списка точек и сравнения."""
    root = Path(root)
    comfy = _git_info(root / "ComfyUI") or {}
    comfy["version"] = _comfy_version(root)
    nodes = {}
    cn = root / "ComfyUI" / "custom_nodes"
    try:
        for d in sorted(cn.iterdir(), key=lambda p: p.name.lower()):
            if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith("."):
                name = d.name[:-9] if d.name.endswith(".disabled") else d.name
                nodes[name] = dict(enabled=not d.name.endswith(".disabled"), **(_git_info(d) or {}))
    except OSError:
        pass
    return {"comfy": comfy, "nodes": nodes, "packages": _packages(root)}


# ───────────────────────────── хранилище ─────────────────────────────

def _obj(store, sha):
    """Путь к содержимому файла в хранилище (сжатому .z или как есть) или None, если его нет."""
    base = Path(store) / "objects" / sha[:2] / sha
    z = base.with_name(sha + ".z")
    if z.is_file():
        return z
    return base if base.is_file() else None


def _compressible(name):
    return os.path.splitext(name.lower())[1] not in NO_COMPRESS


def _read_obj(path):
    """Поток кусков исходного содержимого объекта."""
    with open(path, "rb") as f:
        if path.suffix == ".z":
            d = zlib.decompressobj()
            for b in iter(lambda: f.read(CHUNK), b""):
                out = d.decompress(b)
                if out:
                    yield out
            tail = d.flush()
            if tail:
                yield tail
        else:
            yield from iter(lambda: f.read(CHUNK), b"")


def _norm_root(root):
    return os.path.normcase(os.path.abspath(str(root)))


def load_point(store, point_id):
    with gzip.open(Path(store) / "points" / f"{point_id}.json.gz", "rt", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("format") != FORMAT:
        raise ValueError("Not an ND backup point")
    return data


def _write_json(path, data, compress=False):
    tmp = Path(str(path) + ".tmp")
    opener = gzip.open if compress else open
    with opener(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def list_points(store, root=None):
    """Точки (без списков файлов), новые сверху. С root — только точки этой сборки.
    Читает короткие <id>.info.json; полный манифест открывается, только если сводки нет."""
    pts = []
    folder = Path(store) / "points"
    if not folder.is_dir():
        return pts
    for p in folder.glob("*.json.gz"):
        pid = p.name[:-8]
        try:
            info = folder / f"{pid}.info.json"
            if info.is_file():
                data = json.loads(info.read_text(encoding="utf-8"))
            else:
                data = load_point(store, pid)
        except Exception:
            continue
        if root is not None and _norm_root(data.get("root", "")) != _norm_root(root):
            continue
        data.pop("files", None)
        pts.append(data)
    pts.sort(key=lambda d: (d.get("created", ""), d.get("created_ns", 0)), reverse=True)
    return pts


def _hash_cache(store, root):
    """Путь → (размер, mtime_ns, sha) из последней точки этой сборки: неизменённые файлы не перечитываем."""
    pts = list_points(store, root)
    if not pts:
        return {}
    try:
        files = load_point(store, pts[0]["id"])["files"]
    except Exception:
        return {}
    return {rel: tuple(v[1:3]) + (v[0],) for area in files.values() for rel, v in area.items()}


def estimate(root, store, areas=AREAS, cancel=None):
    """Сколько займёт новая точка: всего в сборке и сколько новых данных придётся записать."""
    files = scan(root, areas, store, cancel)
    cache = _hash_cache(store, root)
    total = new = count = new_count = 0
    for area in files.values():
        for rel, (size, mtime) in area.items():
            total += size
            count += 1
            c = cache.get(rel)
            if not (c and c[0] == size and c[1] == mtime and _obj(store, c[2])):
                new += size
                new_count += 1
    return {"files": count, "bytes": total, "new_files": new_count, "new_bytes": new}


_tmp_seq = iter(range(1 << 62))
_tmp_lock = threading.Lock()


def _tmp_name(tmp_dir):
    with _tmp_lock:
        n = next(_tmp_seq)
    return tmp_dir / f"{os.getpid()}_{threading.get_ident()}_{n}"


def _put(chunks, store, tmp_dir, compress):
    """Пишет поток кусков в хранилище (сжимая по пути) и считает SHA-256 исходных данных.
    Возвращает (sha, байт на диске; 0 — такой объект уже был)."""
    h = hashlib.sha256()
    tmp = _tmp_name(tmp_dir)
    c = zlib.compressobj(LEVEL) if compress else None
    with open(tmp, "wb") as fo:
        for b in chunks:
            h.update(b)
            fo.write(c.compress(b) if c else b)
        if c:
            fo.write(c.flush())
    sha = h.hexdigest()
    if _obj(store, sha):
        tmp.unlink()
        return sha, 0
    dst = Path(store) / "objects" / sha[:2] / (sha + (".z" if compress else ""))
    dst.parent.mkdir(parents=True, exist_ok=True)
    stored = tmp.stat().st_size
    os.replace(tmp, dst)
    return sha, stored


def _file_chunks(path):
    with open(path, "rb") as f:
        yield from iter(lambda: f.read(CHUNK), b"")


def _store_file(src, store, tmp_dir):
    """Копирует файл в хранилище (сжатым, если есть смысл). Возвращает (sha, байт на диске)."""
    return _put(_file_chunks(src), store, tmp_dir, _compressible(str(src)))


_recompressing = set()


def _recompress(store, sha, name, tmp_dir):
    """Старый несжатый объект → сжатый. Необязательная операция: при любой ошибке объект остаётся как был."""
    with _tmp_lock:
        if sha in _recompressing:
            return 0
        _recompressing.add(sha)
    try:
        return _recompress_one(store, sha, name, tmp_dir)
    except OSError:
        return 0
    finally:
        with _tmp_lock:
            _recompressing.discard(sha)


def _recompress_one(store, sha, name, tmp_dir):
    raw = Path(store) / "objects" / sha[:2] / sha
    if raw.is_file() and raw.with_name(sha + ".z").is_file():   # прошлое пережатие не успело убрать оригинал
        raw.unlink()
        return 0
    raw = _obj(store, sha)
    if not raw or raw.suffix == ".z" or not _compressible(name):
        return 0
    tmp = _tmp_name(tmp_dir)
    c = zlib.compressobj(LEVEL)
    with open(raw, "rb") as fi, open(tmp, "wb") as fo:
        for b in iter(lambda: fi.read(CHUNK), b""):
            fo.write(c.compress(b))
        fo.write(c.flush())
    before, after = raw.stat().st_size, tmp.stat().st_size
    os.replace(tmp, raw.with_name(sha + ".z"))   # сначала появляется сжатый, потом исчезает старый
    raw.unlink()
    return max(0, before - after)


def _new_id():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + os.urandom(3).hex()


def create(root, store, label="", reason="manual", areas=AREAS, keep=0, progress=None, cancel=None, extra=None):
    """Создаёт точку восстановления. progress(доля 0..1, текст). Возвращает сводку точки."""
    root, store = Path(root), Path(store)
    say = progress or (lambda *_: None)
    say(0.0, "scan")
    files = scan(root, areas, store, cancel)
    cache = _hash_cache(store, root)
    tmp_dir = store / "objects" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    total = sum(s for a in files.values() for s, _ in a.values()) or 1
    progress_state = {"done": 0, "last": 0.0}
    lock = threading.Lock()

    def tick(size, rel):
        with lock:
            progress_state["done"] += size
            now = time.monotonic()
            if now - progress_state["last"] > 0.3:
                progress_state["last"] = now
                say(progress_state["done"] / total, rel)

    def work(rel, size, mtime):
        """→ (sha | None, новые байты, байты на диске, ошибка). Выполняется в потоках: zlib и чтение отпускают GIL."""
        if cancel and cancel():
            raise Cancelled()
        c = cache.get(rel)
        try:
            if c and c[0] == size and c[1] == mtime and _obj(store, c[2]):
                _recompress(store, c[2], rel, tmp_dir)   # объекты прежних версий пережимаются заодно
                return c[2], 0, 0, None
            sha, stored = _store_file(root / rel, store, tmp_dir)
            return sha, size, stored, None
        except OSError as e:
            return None, 0, 0, f"{rel}: {e}"
        finally:
            tick(size, rel)

    new_bytes = new_files = stored_bytes = 0
    manifest_files, errors = {}, []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        try:
            for area, entries in files.items():
                out = manifest_files[area] = {}
                jobs = [(rel, size, mtime, pool.submit(work, rel, size, mtime)) for rel, (size, mtime) in entries.items()]
                for rel, size, mtime, fut in jobs:
                    sha, new, stored, err = fut.result()
                    if err:
                        errors.append(err)
                        continue
                    out[rel] = [sha, size, mtime]
                    if new:
                        new_bytes += new
                        new_files += 1
                        stored_bytes += stored
        except BaseException:
            pool.shutdown(wait=True, cancel_futures=True)
            raise
    say(1.0, "summary")
    pid = _new_id()
    data = {"format": FORMAT, "version": FORMAT_VERSION, "id": pid,
            "created": datetime.datetime.now().isoformat(timespec="seconds"), "created_ns": time.time_ns(),
            "label": label, "reason": reason, "root": str(root.resolve()), "areas": list(areas),
            "summary": summary(root),
            "stats": {"files": sum(len(v) for v in manifest_files.values()),
                      "bytes": sum(v[1] for a in manifest_files.values() for v in a.values()),
                      "new_files": new_files, "new_bytes": new_bytes, "stored_bytes": stored_bytes,
                      "disk_bytes": _disk_bytes(store, manifest_files), "errors": len(errors)},
            "errors": errors[:200], "files": manifest_files}
    if extra:
        data.update(extra)
    pdir = store / "points"
    pdir.mkdir(parents=True, exist_ok=True)
    info = {k: v for k, v in data.items() if k not in ("files", "errors")}
    _write_json(pdir / f"{pid}.info.json", info)
    _write_json(pdir / f"{pid}.json.gz", data, compress=True)   # точка появляется только целиком
    if keep and keep > 0:
        prune(store, root, keep)
    data.pop("files")
    return data


def _disk_bytes(store, files):
    """Сколько точка занимает на диске сама по себе: каждый её файл один раз, в том виде, как он лежит в хранилище."""
    total = 0
    for sha in {v[0] for area in files.values() for v in area.values()}:
        path = _obj(store, sha)
        if path:
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def fill_disk_sizes(store, points):
    """Для точек из прежних тестовых версий без stats.disk_bytes досчитывает его и сохраняет в <id>.info.json."""
    for p in points:
        st = p.setdefault("stats", {})
        if "disk_bytes" in st:
            continue
        try:
            st["disk_bytes"] = _disk_bytes(store, load_point(store, p["id"])["files"])
            info = Path(store) / "points" / f"{p['id']}.info.json"
            if info.is_file():
                data = json.loads(info.read_text(encoding="utf-8"))
                data.setdefault("stats", {})["disk_bytes"] = st["disk_bytes"]
                _write_json(info, data)
        except Exception:
            pass
    return points


def delete_point(store, point_id, collect=True):
    for p in (Path(store) / "points" / f"{point_id}.json.gz", Path(store) / "points" / f"{point_id}.info.json"):
        if p.is_file():
            p.unlink()
    if collect:
        return gc(store)
    return 0


def prune(store, root, keep):
    """Оставляет keep новейших точек этой сборки, остальные удаляет вместе с ненужными файлами."""
    pts = list_points(store, root)
    for p in pts[keep:]:
        delete_point(store, p["id"], collect=False)
    return gc(store) if len(pts) > keep else 0


def gc(store):
    """Удаляет из хранилища файлы, на которые не ссылается ни одна точка (любой сборки). Возвращает байты."""
    store = Path(store)
    used = set()
    for p in (store / "points").glob("*.json.gz"):
        try:
            for area in load_point(store, p.name[:-8])["files"].values():
                used.update(v[0] for v in area.values())
        except Exception:
            return 0   # не смогли прочитать точку — ничего не удаляем, чтобы её не повредить
    freed = 0
    objects = store / "objects"
    if not objects.is_dir():
        return 0
    for sub in objects.iterdir():
        if not sub.is_dir():
            continue
        for f in sub.iterdir():
            if sub.name == "tmp" or f.name.removesuffix(".z") not in used:
                try:
                    freed += f.stat().st_size
                    f.unlink()
                except OSError:
                    pass
    return freed


def store_size(store):
    total = 0
    for dirpath, _d, filenames in os.walk(Path(store) / "objects"):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


# ───────────────────────────── восстановление ─────────────────────────────

def _same(path, sha, size, mtime):
    try:
        st = os.stat(path)
    except OSError:
        return False
    if st.st_size != size:
        return False
    if st.st_mtime_ns == mtime:
        return True
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest() == sha


def restore(root, store, point_id, areas=AREAS, progress=None, cancel=None):
    """Приводит выбранные области сборки к состоянию точки.
    Лишние файлы (которых не было в точке) переносятся в <store>/trash/<время>/, а не удаляются.
    Возвращает dict(written, moved, errors, trash)."""
    root, store = Path(root), Path(store)
    say = progress or (lambda *_: None)
    point = load_point(store, point_id)
    areas = [a for a in areas if a in point.get("files", {})]
    say(0.0, "scan")
    current = scan(root, areas, store, cancel)
    missing = [v[0] for a in areas for v in point["files"][a].values() if not _obj(store, v[0])]
    if missing:
        raise FileNotFoundError(f"Backup store is incomplete: {len(missing)} files are missing")
    trash = store / "trash" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    total = sum(v[1] for a in areas for v in point["files"][a].values()) or 1
    done = written = moved = 0
    errors = []
    last = 0.0
    for area in areas:
        want = point["files"][area]
        for rel, (sha, size, mtime) in want.items():
            if cancel and cancel():
                raise Cancelled()
            dst = root / rel
            try:
                if not _same(dst, sha, size, mtime):
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dst.with_name(dst.name + ".ndrestore")
                    h = hashlib.sha256()
                    try:
                        with open(tmp, "wb") as fo:
                            for b in _read_obj(_obj(store, sha)):
                                h.update(b)
                                fo.write(b)
                    except zlib.error:
                        h = None
                    if h is None or h.hexdigest() != sha:   # повреждённый объект в хранилище не должен попасть в сборку
                        os.remove(tmp)
                        raise OSError("damaged in backup storage")
                    os.replace(tmp, dst)
                    os.utime(dst, ns=(mtime, mtime))
                    written += 1
            except OSError as e:
                errors.append(f"{rel}: {e}")
            done += size
            now = time.monotonic()
            if now - last > 0.3:
                last = now
                say(done / total, rel)
        for rel in current.get(area, {}):
            if rel in want:
                continue
            try:
                target = trash / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(root / rel), str(target))
                moved += 1
            except OSError as e:
                errors.append(f"{rel}: {e}")
    # пустые папки, оставшиеся после переноса лишних файлов
    for area, rel_base in area_roots(root):
        if area not in areas or not (root / rel_base).is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root / rel_base, topdown=False):
            rel_dir = Path(dirpath).relative_to(root).as_posix()
            if rel_dir == rel_base or (area == "comfy" and any(rel_dir == x or rel_dir.startswith(x + "/") for x in COMFY_EXCLUDE)):
                continue
            try:
                entries = os.listdir(dirpath)
                # папка, от которой остался только кэш Python, иначе стала бы «пустым пакетом» для import
                if entries == ["__pycache__"]:
                    shutil.rmtree(os.path.join(dirpath, "__pycache__"), ignore_errors=True)
                    entries = os.listdir(dirpath)
                if not entries:
                    os.rmdir(dirpath)
            except OSError:
                pass
    say(1.0, "done")
    return {"written": written, "moved": moved, "errors": errors, "trash": str(trash) if moved else ""}


# ───────────────────────────── сравнение ─────────────────────────────

def diff(old, new):
    """Разница сводок двух точек (или точки и текущего состояния — summary(root)).
    old/new — dict с ключами comfy, nodes, packages."""
    def short(c):
        return (c or "")[:8]
    res = {"comfy": None, "nodes": {"added": [], "removed": [], "changed": [], "toggled": []},
           "packages": {"added": [], "removed": [], "changed": []}}
    oc, nc = old.get("comfy", {}), new.get("comfy", {})
    if (oc.get("commit"), oc.get("version")) != (nc.get("commit"), nc.get("version")):
        res["comfy"] = {"old": f"{oc.get('version', '')} {short(oc.get('commit'))}".strip(),
                        "new": f"{nc.get('version', '')} {short(nc.get('commit'))}".strip()}
    on, nn = old.get("nodes", {}), new.get("nodes", {})
    for name in sorted(set(on) | set(nn), key=str.lower):
        a, b = on.get(name), nn.get(name)
        if a is None:
            res["nodes"]["added"].append(name)
        elif b is None:
            res["nodes"]["removed"].append(name)
        else:
            if a.get("commit") != b.get("commit"):
                res["nodes"]["changed"].append((name, short(a.get("commit")), short(b.get("commit"))))
            if a.get("enabled") != b.get("enabled"):
                res["nodes"]["toggled"].append((name, b.get("enabled")))
    op, np_ = old.get("packages", {}), new.get("packages", {})
    for name in sorted(set(op) | set(np_)):
        a, b = op.get(name), np_.get(name)
        if a is None:
            res["packages"]["added"].append((name, b))
        elif b is None:
            res["packages"]["removed"].append((name, a))
        elif a != b:
            res["packages"]["changed"].append((name, a, b))
    return res

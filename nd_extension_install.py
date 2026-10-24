"""Browser selection and stable unpacked-extension preparation (no browser policies)."""
import json
import os
from pathlib import Path
import re
import shutil


def load_catalog(source):
    return json.loads((Path(source) / 'browsers.json').read_text(encoding='utf-8-sig'))


def browser_spec(exe, label, catalog):
    basename = re.split(r'[\\/]', str(exe))[-1].lower()
    context = str(exe) + ' ' + label
    # Specific paths/names beat generic chrome.exe.
    for spec in sorted(catalog, key=lambda s: not bool(s.get('hint'))):
        if basename not in spec['exe']:
            continue
        if spec.get('hint') and not re.search(spec['hint'], context, re.I):
            continue
        return spec
    return None


def extension_browsers(detected, preferred, catalog, environ=None):
    environ = os.environ if environ is None else environ
    candidates = list(detected)
    if preferred:
        candidates.append(('', preferred))
    for spec in catalog:
        for env_key in ('LOCALAPPDATA', 'ProgramFiles', 'ProgramFiles(x86)'):
            base = environ.get(env_key)
            if base:
                candidates.extend((spec['name'], str(Path(base) / rel)) for rel in spec['paths'])
    result, seen = [], set()
    for label, exe in candidates:
        key = os.path.normpath(str(exe)).casefold()
        if key in seen or not Path(exe).is_file():
            continue
        spec = browser_spec(exe, label, catalog)
        if spec:
            seen.add(key)
            result.append((label or spec['name'], str(exe), spec['url']))
    return sorted(result, key=lambda row: row[0].casefold())


def prepare_extension(source, local_appdata):
    source = Path(source)
    if not local_appdata:
        raise OSError('LOCALAPPDATA is unavailable')
    if not (source / 'manifest.json').is_file():
        raise FileNotFoundError('chrome_extension/manifest.json')
    # Keep the path used by earlier Chrome builds: unpacked IDs/settings depend on it.
    target = Path(local_appdata) / 'NDLauncher' / 'ChromeExtension'
    if source.resolve() != target.resolve():
        shutil.copytree(source, target, dirs_exist_ok=True)
    return target

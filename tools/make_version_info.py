# SPDX-License-Identifier: GPL-3.0-or-later
"""Пишет version_info.txt для PyInstaller (--version-file).

Сведения о версии видны в свойствах exe (Подробно) и снижают число ложных
срабатываний антивирусов: exe без метаданных выглядит подозрительнее.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "nd_launcher.py").read_text(encoding="utf-8")
version = re.search(r'^VERSION = "([^"]+)"', src, re.M).group(1)
nums = [int(x) for x in re.findall(r"\d+", version)][:4]
nums += [0] * (4 - len(nums))
vt = tuple(nums)

TEMPLATE = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={vt}, prodvers={vt}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Neural Dreamer'),
        StringStruct('FileDescription', 'ND ComfyUI Launcher'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'ND_Launcher'),
        StringStruct('LegalCopyright', 'Copyright (C) 2026 Neural Dreamer. GPL-3.0-or-later'),
        StringStruct('OriginalFilename', 'ND_Launcher.exe'),
        StringStruct('ProductName', 'ND ComfyUI Launcher'),
        StringStruct('ProductVersion', '{version}'),
        StringStruct('Comments', 'https://github.com/neural-dreamer/ND-ComfyUI-Launcher')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

out = ROOT / "version_info.txt"
out.write_text(TEMPLATE, encoding="utf-8")
print(f"[ND] version_info.txt: {version}")

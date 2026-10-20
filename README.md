<div align="center">

<img src="brand/example.png" width="120" alt="Neural Dreamer">

# ND · ComfyUI Launcher

**A one-window launcher for any portable ComfyUI build on Windows**

[![Release](https://img.shields.io/github/v/release/neural-dreamer/ND-ComfyUI-Launcher?color=00c8e0)](https://github.com/neural-dreamer/ND-ComfyUI-Launcher/releases/latest)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-ff2bd6)](LICENSE)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-555)

**English** · [Русский](README.ru.md) · [中文](README.zh-CN.md)

</div>

No more `.bat` files and launch flags to remember. ND Launcher starts ComfyUI with the right settings, updates it and your custom nodes, installs new nodes and models, moves everything over from an old build, and keeps the console, GPU stats and your workflows in one place.

![ND Launcher](docs/screenshots/launch.png)

## Features

- **Launch** — ready-made presets (Standard, Save VRAM, Maximum speed, Video & large models, CPU only) plus your own. VRAM mode, attention (SageAttention, FlashAttention), fp8 / fp16, reserved VRAM, LAN access and port as simple controls. One-click desktop shortcut that starts ComfyUI right away, optionally minimized to the tray.
- **Console** — ComfyUI output inside the window with errors highlighted, generation progress, and a GPU monitor (VRAM, load, temperature).
- **Workflows** — every workflow in the build, searchable, with a description panel: what it does, how to use it, and which models and custom nodes it needs, checked against what you actually have installed.
- **Updates** — update ComfyUI (with or without dependencies) and all custom nodes in one click; enable or disable nodes without deleting them.
- **Install nodes** — paste one or more repository links (GitHub, GitLab, a branch, or the short `author/repo` form); the node is cloned and its dependencies installed.
- **Model downloads** — paste a Hugging Face or Civitai link, pick files and destination folders, and see free disk space before you start.
  - Hugging Face uses the official `hf download` with Xet acceleration.
  - Civitai downloads use up to 16 parallel connections, with no extra tools needed.
  - Destination roots can come from your `extra_model_paths.yaml`.
- **Transfer** — move settings, workflows, models, Input / Output, `extra_model_paths.yaml` and custom nodes from another ComfyUI build. Missing nodes are detected automatically. Models can be copied, moved, hard-linked instantly, or linked without copying.
- **Comfort** — 3 themes (Neon, Foggy Night, Classic), 3 languages (English, Russian, Chinese), your browser of choice (or app mode), minimize to tray, single instance.

<p align="center">
  <img src="docs/screenshots/workflows.png" width="49%" alt="Workflows">
  <img src="docs/screenshots/models.png" width="49%" alt="Model downloads">
</p>

## Installation

1. Download `ND_Launcher_vX.Y.Z.zip` from the [latest release](https://github.com/neural-dreamer/ND-ComfyUI-Launcher/releases/latest) and unpack it.
2. Put `ND_Launcher.exe` into the root of your portable ComfyUI build, next to the `python_embeded` and `ComfyUI` folders:
   ```
   ComfyUI_windows_portable\
   ├── ComfyUI\
   ├── python_embeded\
   └── ND_Launcher.exe
   ```
3. Run it. Nothing else needs to be installed.

**Requirements:** Windows 10 / 11 (64-bit) and any portable ComfyUI build with `python_embeded`. Optional: [Git for Windows](https://git-scm.com) for updating custom nodes, an NVIDIA GPU for the GPU monitor.

> **Windows SmartScreen.** The exe is not code-signed, so Windows may show “Windows protected your PC”. Click **More info → Run anyway**. Every release is built from this source code by [GitHub Actions](.github/workflows/release.yml), so you can check exactly what went into it.

## Good to know

- **Launch flags.** `--enable-manager`, `--enable-manager-legacy-ui` and `--max-upload-size 999` are on by default and can be turned off on the Launch tab. `--enable-manager` needs a recent ComfyUI with the pip version of ComfyUI-Manager: turn it off for older builds.
- **Settings** are stored in `nd_launcher.json` next to the launcher.
- **API tokens** are encrypted with Windows DPAPI: only your Windows user on this PC can decrypt them.
- **Network access.** The launcher sends no telemetry. It goes online only for features you use: downloads, node installs and updates.
- **Example image.** After every ComfyUI update, the launcher replaces `ComfyUI/input/example.png` with the Neural Dreamer logo. In Settings you can choose your own image or turn this off.
- **Workflow descriptions** live in `utils/*.ndesc` (plain JSON). See the [format spec](docs/NDESC_FORMAT.md) (in Russian) and the [example](utils/workflows.ndesc.example).

## Running from source & building

- **Run from source.** Copy `nd_launcher.py`, `nd_i18n.py`, `nd_icon.ico`, `brand\` and `ND_Launcher.bat` into the build root and run `ND_Launcher.bat`. It installs PySide6 into `python_embeded` on first start.
- **Build the exe locally.** Install Python 3.10+, then run `build_exe.bat`. The result is `dist\ND_Launcher.exe` with `brand\` (links, icons, logo) embedded.
- **Release.** Bump `VERSION` in `nd_launcher.py`, add a section to [CHANGELOG.md](CHANGELOG.md) and push a tag such as `v1.1.0`. GitHub Actions builds the exe and publishes the release.
- **Fork branding.** Run `ND_Links_Editor.bat` to change the links shown in the launcher, and replace `brand\example.png` with your own logo.

## License

[GPL-3.0-or-later](LICENSE) © 2026 Neural Dreamer. You may use, study, share and modify the launcher; modified versions must stay open under the same license.

ND Launcher is an independent project and is not affiliated with ComfyUI or Comfy Org.

## Links

[YouTube](https://www.youtube.com/@neural_dreamer) · [VK Video](https://vkvideo.ru/@neural_dreamer) · [Boosty](https://boosty.to/neural_dreamer) · [Patreon](https://www.patreon.com/cw/neural_dreamer) · [Civitai](https://civitai.red/user/Neural_Dreamer) · [Hugging Face](https://huggingface.co/NeuralDreamer)

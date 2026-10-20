# Changelog

All notable changes to ND · ComfyUI Launcher. Versions follow [Semantic Versioning](https://semver.org).
The release workflow publishes the section matching the pushed tag as the release notes.

## [1.1.0] — 2026-10-20

First public release.

### Added
- **Model downloads** tab: Hugging Face (repository, folder or file links; official `hf download` with Xet acceleration) and Civitai (civitai.com and civitai.red; parallel multi-connection downloads). Per-file destination folders with automatic suggestions, free disk space check, download queue that runs alongside ComfyUI.
- Model roots from `extra_model_paths.yaml` as download destinations.
- Encrypted storage for Hugging Face and Civitai API tokens (Windows DPAPI).
- Browser choice for opening ComfyUI, including app mode for Chromium-based browsers.
- Transfer of `extra_model_paths.yaml` from another build: relative paths are recalculated, an existing file is extended rather than overwritten (a `.bak` copy is kept).
- `models\LLM` quick folder.
- License notice and repository link in Settings → About.
- Launch flags `--enable-manager`, `--enable-manager-legacy-ui` and `--max-upload-size 999` are now checkboxes on the Launch tab (on by default; previously always added).
- `example.png` replacement can be turned off or use your own image (Settings).

### Changed
- Folder pickers open downwards, start at “Other folder…” and ignore the mouse wheel when closed.
- Table headers follow the rounded panel corners.

## [1.0.1]

### Added
- Hard-link transfer mode (instant, no extra space on the same drive).
- Transfer mode choice (copy / hard links / move) for Input and Output.

### Fixed
- Transfers no longer saturate the SSD: large files are copied unbuffered via the Windows copy engine; optional gentle mode with background I/O priority and a speed cap.

## [1.0.0]

Initial private release: launch presets, console, GPU monitor, workflow descriptions (`.ndesc`), ComfyUI and custom node updates, node installation from links, transfer from another build, desktop shortcut and tray, 3 themes, 3 languages.

# Changelog

All notable changes to ND · ComfyUI Launcher. Versions follow [Semantic Versioning](https://semver.org).
Each version's section is used as the notes of its GitHub release.

## [1.1.2] — 2026-10-21

### Added
- **Pause / Resume** for model downloads (Hugging Face and Civitai). Progress is saved next to the file (`.ndpart` + `.ndpart.json`), so a paused, interrupted or network-failed download continues from the same place — also after restarting the launcher: just start the same file again. Closing the launcher during a download pauses it instead of deleting what was downloaded.
- Civitai downloads are checked against the SHA-256 published by Civitai.

### Changed
- Hugging Face files now download the same way as Civitai: directly into the destination folder over several parallel connections (the “Connections” setting), with no temporary folder and no move at the end. After the download the file is checked against the SHA-256 published on Hugging Face; a corrupted file is deleted.
- The official `hf download` (Xet) is still available as the “Hugging Face via hf CLI (Xet)” option, off by default. In this mode the launcher forces progress output, disables the Xet chunk cache and shows its own progress from the size on disk.

### Fixed
- Hugging Face downloads showed no progress and could seem stuck with a recent `huggingface_hub`.
- The download status line flickered between two progress sources.
- Expired storage links are renewed automatically during long downloads (Hugging Face and Civitai).
- The “file already exists” prompt shows the size of the existing file.

## [1.1.1] — 2026-10-20

### Fixed
- Hugging Face downloads failed with `ModuleNotFoundError: No module named 'venv'` on builds with a recent `huggingface_hub`: its CLI imports `venv`, which the portable `python_embeded` does not include.
- Cancelling a download now deletes the partial `.ndpart` file (and the Hugging Face temp folder): the launcher waits for the download process to exit and retries if the file is still locked.

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
- `ndesc-writer` skill (`skills/ndesc-writer/SKILL.md`) for generating workflow descriptions with Claude, ChatGPT and other LLMs.

### Changed
- The launcher is distributed as source code: build `ND_Launcher.exe` yourself with `build_exe.bat` (one click, needs Python 3.10+; everything is installed into a local `.build_venv`). A locally built exe is not blocked by Windows SmartScreen. The exe now carries version and publisher info.
- Language buttons are labelled in their own language: РУ, EN, 中文.
- Folder pickers open downwards, start at “Other folder…” and ignore the mouse wheel when closed.
- Table headers follow the rounded panel corners.
- “Reserved VRAM” is now a drop-down list like the other launch options.
- Workflow descriptions no longer list custom nodes (`custom_nodes` is ignored).
- The description panel on the Workflows tab is hidden when there is no valid `.ndesc` file.

### Fixed
- “&” was shown as an underscore in some English labels (“Folders & links”, “Settings & Manager”).

## [1.0.1]

### Added
- Hard-link transfer mode (instant, no extra space on the same drive).
- Transfer mode choice (copy / hard links / move) for Input and Output.

### Fixed
- Transfers no longer saturate the SSD: large files are copied unbuffered via the Windows copy engine; optional gentle mode with background I/O priority and a speed cap.

## [1.0.0]

Initial private release: launch presets, console, GPU monitor, workflow descriptions (`.ndesc`), ComfyUI and custom node updates, node installation from links, transfer from another build, desktop shortcut and tray, 3 themes, 3 languages.

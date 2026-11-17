# Changelog

All notable changes to ND · ComfyUI Launcher. Versions follow [Semantic Versioning](https://semver.org).
Each version's section is used as the notes of its GitHub release.

## [Unreleased]

### Changed
- **Install workflow:** missing custom nodes are now installed at the latest version by default. The version recorded in the workflow is still one click away (per node or with **From workflow** for all checked nodes).

### Fixed
- **Model downloads (Civitai):** when Civitai limited downloads (HTTP 429) or answered with a temporary server error, the download stopped at once and every retry failed the same way. The launcher now waits (using the server's Retry-After) and tries again, shows a clear message if the limit persists, and keeps the downloaded part so the next attempt resumes instead of starting over. The console now shows which server returned the error. Downloads sent from the browser whose link has expired get a clear hint to add a Civitai API token or restart the download in the browser.

## [1.3.1] — 2026-11-10

Fix: PyTorch could lose CUDA after “ComfyUI + dependencies”.

### Fixed
- **Update tab → ComfyUI + dependencies** could leave PyTorch without CUDA (a CPU-only build, ComfyUI then stops with "Torch not compiled with CUDA enabled"). The stock batch file installs PyTorch from PyPI together with the CUDA index, and pip may pick the PyPI build. The launcher now remembers the CUDA tag of the installed PyTorch, checks it after the update and, if CUDA is gone, reinstalls the build with the same CUDA from the pytorch.org index. Can be switched off with a checkbox on the Updates tab.

## [1.3.0] — 2026-11-10

Install a workflow together with its nodes and models, a progress bar with reconnect for installs, and an experimental NVIDIA ⇄ AMD platform switch.

### Added
- **Install a workflow with everything it needs.** On the Workflows tab, drop `.json` files (several at once) or a `.zip` archive onto the new area, click it, or press **Install workflow…**. The launcher reads every node in the workflow, including nodes inside subgraphs, finds the repository of each custom node (links in `Note` / `MarkdownNote` nodes first, then `aux_id`, Comfy Registry and the ComfyUI-Manager node map) and lists the files, nodes and models in one dialog.
  - Nodes are installed at the version recorded in the workflow by default. If different nodes of one package record different versions, the newest of them is used. “Latest” can be chosen per node or for all checked nodes at once and is marked as not verified with the workflow. A version that does not exist in the repository falls back to the latest one with a note in the console.
  - When the workflow mentions several forks of one repository you pick the fork. A node with no known source does not block the rest, and you can paste its link.
  - Missing models with direct links are sent to Model downloads (optional, remembered). A `prompts` folder in an archive goes to `models\LLM\prompts` (with a choice of model root when extra model paths are connected). Existing files can be replaced, skipped or kept side by side. Archives are checked for unsafe paths and size.
  - The dialog also checks the `requirements.txt` of nodes that are already installed and offers to install the missing packages, for example after an interrupted install.
- **Install and update progress bar** under the Console: the current step, download progress and speed (pip and git), step time, retries, and a warning when no data has arrived for a while. Pip shows done / total, git shows the amount received. Buttons: **Reconnect** (aborts the current download and starts the step again on a fresh connection — handy right after turning on a VPN), **Skip step** and **Cancel**. Partially cloned folders are removed on reconnect, skip and cancel, and child processes are stopped together with the step.
- **Install** button next to the ComfyUI-Manager option on the Launch tab: shown while the built-in Manager (Extensions) is not installed; installs it with its dependencies from `ComfyUI\manager_requirements.txt`.
- **Platform switch (experimental): NVIDIA ⇄ AMD (ROCm)** on the Launch tab. The launcher keeps two `python_embeded` environments side by side: the inactive one is prepared once from the official ComfyUI portable archive (downloaded from GitHub, unpacked with 7-Zip if installed or with `py7zr`), its dependencies are synced from ComfyUI and your enabled custom nodes, then the two folders are swapped by a helper script and the launcher restarts. Models, custom nodes, workflows, input and output are never touched. Optional restore point first (on by default), automatic rollback if `import torch` fails after the swap. On AMD, Sage/Flash Attention are replaced with PyTorch attention, and your previous launch options come back when you switch back. Settings → Platform: unpacking method, prepared environments, delete an inactive one. Windows only; not tested on a real Radeon yet.

### Changed
- **Classic Manager interface** (`--enable-manager-legacy-ui`) is now off by default (it is switched off once for existing settings).
- **Browser extension** is now an official Chrome Web Store extension. **Settings → Browser downloads → Install browser extension** opens the store page in the chosen Chromium browser (plus **Copy link**); manual installation from the launcher folder remains as a fallback. README and extension guides updated.

### Fixed
- **Backups** tab: every restore point showed the size of the whole build. Now each point shows what it takes itself (new compressed data; the full size is in the tooltip), and the list appears at once with a loading indicator while sizes are being calculated.

## [1.2.0] — 2026-10-25

Restore points for the build, a visual editor for model paths, and Focus mode.

### Added
- **Backups** tab: restore points for the build — ComfyUI code (with `.git` and the `update` folder), custom nodes, Python packages in `python_embeded` and `ComfyUI/user`. Works offline. Files are stored once by SHA-256 and compressed (already compressed formats such as `.zip`, `.whl`, `.png` are kept as is), so only the first point is a full copy. Shows the estimated size of a new point and the free space on the target disk; points can be compared (ComfyUI version, node commits, package versions) and restored fully or by area. Restore verifies every file's SHA-256; files that were not in the point are moved to the storage `trash` folder, not deleted. Storage defaults to `Backups` inside the build and can be changed; old points are pruned automatically (10 kept by default). Models, input and output are not included.
- “Create a restore point before updating” option on the Updates tab (off by default).
- **Model paths** tab: visual editor for `extra_model_paths.yaml` — connect another ComfyUI build or any model folder, choose model types (including node folders such as LLM, TTS, sam3) and how each is connected: yaml, a folder link (junction, no admin rights) for nodes that only look in `ComfyUI\models`, or both. Sources can be disabled, edited and removed; hand-written sections are kept, a `.bak` copy is saved before every write, and the tab shows where ComfyUI will look for each model type.
- **Focus mode** switch in the header: shows only the tabs chosen in Settings → Focus mode (by default Console, Workflows and Model downloads); Settings always stay visible, and launch stays on the sidebar button. Styled like the browser extension switch; remembered between runs.
- **Check for updates** button in Settings → Launcher behavior: checks GitHub right away and reports the result (works even with automatic checks turned off).

### Fixed
- The launcher update check no longer reports an error when one of its two sources (latest release or `VERSION` in `main`) fails but the other answers.
- README: the “Run without an exe” instructions list all required files.
- Browser extension: **Check connection** now runs from the extension page, so Chrome can ask for local network access, and a failed connection shows what to check instead of “Failed to fetch”.

## [1.1.3] — 2026-10-24

Browser model downloads, optional post-update commands, and clearer download progress.

### Added
- **Browser extension** for Hugging Face, Civitai.com, Civitai.red and ModelScope.cn. Downloads go to the launcher with the folder selected in the browser; the launcher can automatically come to the foreground.
- Extension setup from launcher settings for Chrome, Yandex Browser, Edge and other supported Chromium browsers. The extension includes three languages, three themes and matching logo and toolbar icon colors.
- **Post-update commands** run through the selected build’s portable Python after ComfyUI and/or custom node updates. The optional panel is collapsed by default.
- Automatic checks for new launcher versions, with an option to disable them.

### Changed
- Model downloads now use one destination folder for all selected files. The queue shows per-file progress and speed with resizable columns.

### Fixed
- ComfyUI updates now use the build’s own batch files and finish on the stable channel, including when updating dependencies.
- Large direct downloads start without preallocating the entire file; cancelling downloads no longer blocks the interface.
- Generation progress stays visible between steps, and cancelling a paused download clears its progress bar.

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

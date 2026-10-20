<div align="center">

<img src="docs/logo.png" width="180" alt="ND · ComfyUI Launcher">

# ND · ComfyUI Launcher

**适用于 Windows 上任意便携版 ComfyUI 的一站式启动器**

[![Release](https://img.shields.io/github/v/release/neural-dreamer/ND-ComfyUI-Launcher?color=00c8e0)](https://github.com/neural-dreamer/ND-ComfyUI-Launcher/releases/latest)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-ff2bd6)](LICENSE)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-555)

[English](README.md) · [Русский](README.ru.md) · **中文**

</div>

不再需要编辑 `.bat` 文件，也不用记住启动参数。ND Launcher 会用合适的设置启动 ComfyUI，更新 ComfyUI 和自定义节点，安装新节点和模型，从旧整合包迁移全部内容，并把控制台、显卡监控和工作流集中在一个窗口里。

![ND Launcher](docs/screenshots/launch.png)

## 功能

- **启动** — 内置预设（标准、节省显存、最高速度、视频与大模型、仅 CPU），也可保存自己的预设。显存模式、attention（SageAttention、FlashAttention）、fp8 / fp16、预留显存、局域网访问和端口都以简单选项呈现。一键创建桌面快捷方式，可直接启动 ComfyUI，也可最小化到托盘启动。
- **控制台** — 在窗口内显示 ComfyUI 输出并高亮错误，显示生成进度，以及显卡监控（显存、占用、温度）。
- **工作流** — 整合包中的全部工作流，支持搜索，并有描述面板：用途、使用方法、所需模型，并检查哪些模型已经存在。
- **更新** — 一键更新 ComfyUI（可选是否安装依赖）和全部自定义节点；无需删除即可启用或禁用节点。
- **安装节点** — 粘贴一个或多个仓库链接（GitHub、GitLab、分支，或简写 `作者/仓库`），节点会被克隆，依赖会自动安装。
- **模型下载** — 粘贴 Hugging Face 或 Civitai 链接，选择文件和目标文件夹，开始前即可查看磁盘剩余空间。
  - Hugging Face 使用官方的 `hf download` 及 Xet 加速。
  - Civitai 最多 16 个并行连接，无需额外工具。
  - 目标根目录可读取自 `extra_model_paths.yaml`。
- **迁移** — 从另一个 ComfyUI 整合包迁移设置、工作流、模型、Input / Output、`extra_model_paths.yaml` 和自定义节点。缺少的节点会被自动识别。模型可复制、移动、瞬间建立硬链接，或不复制直接链接。
- **便捷** — 3 种主题（霓虹、雾夜、经典）、3 种语言（中文、英文、俄文）、自选浏览器（含应用模式）、最小化到托盘、防止重复启动。

<p align="center">
  <img src="docs/screenshots/transfer.png" width="49%" alt="迁移">
  <img src="docs/screenshots/models.png" width="49%" alt="模型下载">
</p>

## 安装

启动器以源代码形式发布：在你自己的电脑上一键构建 `ND_Launcher.exe`。在本机构建的文件不会被标记为来自互联网，因此 Windows SmartScreen 不会拦截它。

### 构建 exe（推荐）

1. 安装 [Python 3.10 或更高版本](https://www.python.org/downloads/windows/)。在安装程序中勾选 **Add python.exe to PATH**。
2. 下载源代码：[最新版本](https://github.com/neural-dreamer/ND-ComfyUI-Launcher/releases/latest) → **Source code (zip)**，或在本页点击 **Code → Download ZIP**。解压前打开压缩包的 **属性** 并勾选 **解除锁定**，这样 Windows 不会对 `.bat` 文件发出警告。
3. 解压到任意文件夹并运行 `build_exe.bat`。需要联网，首次构建需要几分钟；它安装的所有内容都只保存在旁边的 `.build_venv` 文件夹中。
4. 将 `dist\ND_Launcher.exe` 放到 ComfyUI 便携版的根目录，与 `python_embeded` 和 `ComfyUI` 文件夹并列：
   ```
   ComfyUI_windows_portable\
   ├── ComfyUI\
   ├── python_embeded\
   └── ND_Launcher.exe
   ```
5. 运行即可。构建好的 exe 无需安装其他任何东西，可以复制到其他整合包和电脑上使用。

> 部分杀毒软件不信任用 PyInstaller 打包的 exe，无论其内容如何。如果你的杀毒软件删除了 `ND_Launcher.exe`，请将其加入排除项，或使用下面的方式。

### 不使用 exe 运行

将 `nd_launcher.py`、`nd_i18n.py`、`nd_icon.ico`、`brand\` 文件夹和 `ND_Launcher.bat` 复制到整合包根目录，然后运行 `ND_Launcher.bat`。首次启动时它会把 PySide6 安装到 `python_embeded`。

**系统要求：** Windows 10 / 11（64 位）以及任何带 `python_embeded` 的 ComfyUI 便携版。可选：用于更新自定义节点的 [Git for Windows](https://git-scm.com)，以及用于 GPU 监控的 NVIDIA 显卡。

## 须知

- **启动参数。** `--enable-manager`、`--enable-manager-legacy-ui` 和 `--max-upload-size 999` 默认开启，可在“启动”选项卡中关闭。`--enable-manager` 需要较新的 ComfyUI 以及 pip 版 ComfyUI-Manager，旧版整合包请关闭它。
- **设置**保存在启动器旁的 `nd_launcher.json` 中。
- **API 令牌**使用 Windows DPAPI 加密，只有本机上你的 Windows 用户才能解密。
- **网络访问。** 启动器不发送任何遥测数据，只在你使用相应功能时联网：下载、安装和更新节点。
- **示例图片。** 每次更新 ComfyUI 后，启动器会把 `ComfyUI/input/example.png` 替换为 Neural Dreamer 徽标。可在“设置”中选择自己的图片或关闭此功能。
- **工作流描述**存放在 `utils/*.ndesc`（纯 JSON）。如果没有描述，“工作流”选项卡只显示列表。可使用 [ndesc-writer 技能](skills/ndesc-writer/SKILL.md)让 AI 模型（Claude、ChatGPT 等）生成描述。另见[格式说明](docs/NDESC_FORMAT.md)（俄文）和[示例](utils/workflows.ndesc.example)。

## 开发者

- **发布：** 修改 `nd_launcher.py` 中的 `VERSION`，在 [CHANGELOG.md](CHANGELOG.md) 中添加对应章节，然后在 GitHub 上发布带有 `v1.1.0` 这类标签的版本，并将该章节作为发布说明。
- **分支自定义品牌：** 运行 `ND_Links_Editor.bat` 修改启动器中显示的链接，并可用自己的徽标替换 `brand\example.png`。然后使用 `build_exe.bat` 构建。

## 许可证

[GPL-3.0-or-later](LICENSE) © 2026 Neural Dreamer。你可以使用、研究、分享和修改本启动器；修改后的版本必须以相同许可证保持开源。

ND Launcher 是独立项目，与 ComfyUI 或 Comfy Org 无关。

## 链接

[YouTube](https://www.youtube.com/@neural_dreamer) · [VK Video](https://vkvideo.ru/@neural_dreamer) · [Boosty](https://boosty.to/neural_dreamer) · [Patreon](https://www.patreon.com/cw/neural_dreamer) · [Civitai](https://civitai.red/user/Neural_Dreamer) · [Hugging Face](https://huggingface.co/NeuralDreamer)

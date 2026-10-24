# ND Launcher 浏览器扩展

[English](INSTALL.md) · [Русский](INSTALL_RU.md) · [中文](INSTALL.zh-CN.md)

扩展将 **Hugging Face、Civitai.com、Civitai.red 和 ModelScope.cn** 的模型下载交给 ND Launcher，并保留在浏览器中选择的目标文件夹。接收下载时启动器必须保持运行，但 ComfyUI 本身可以不启动。

## 安装与连接

1. 在启动器中打开 **设置 → 浏览器下载 → 安装浏览器扩展**。
2. 选择检测到的浏览器，或通过 **浏览…** 指定便携浏览器。此选择独立于打开 ComfyUI 所用的浏览器保存。
3. 点击 **准备并打开文件夹**。启动器会准备固定文件夹，并在资源管理器中选中它；路径也会显示在对话框中并复制到剪贴板。
4. 自行打开该浏览器的扩展管理页面。启用开发者模式，点击 **加载已解压的扩展程序**，选择准备好的文件夹。如果浏览器支持拖放安装，也可以将文件夹拖到该页面。
5. 在启动器中启用接收浏览器模型下载，并复制连接密钥。
6. 打开扩展，展开 **连接**，粘贴密钥，点击 **保存**，然后点击 **测试连接**。打开接管下载开关。
7. 在浏览器下载设置中启用询问保存位置，以便下载模型时选择目标文件夹。

| 浏览器 | 扩展管理页面 |
|---|---|
| Chrome / Chromium / Thorium | `chrome://extensions/` |
| Yandex Browser | `browser://extensions/` |
| Microsoft Edge | `edge://extensions/` |
| Brave | `brave://extensions/` |
| Opera / Opera GX | `opera://extensions/` |
| Vivaldi | `vivaldi://extensions/` |

安装助手支持上述 Chromium 浏览器，不支持 Firefox。最后一步需要手动添加扩展，无需管理员权限。

另一种准备方式：运行 [INSTALL_BROWSER.bat](INSTALL_BROWSER.bat)。它会提供浏览器选择、准备文件夹并打开浏览器。此助手不需要 Python，但下载时仍需运行启动器。

## 界面

- 右上角语言菜单提供 **РУ / EN / 中文**。
- 大开关控制是否接管下载，切换后立即保存。
- **连接**和**使用入门**默认折叠。
- 底部彩色胶囊按钮切换 **霓虹 / 雾夜 / 经典**。主题和语言保存在浏览器配置文件中。徽标和工具栏图标随主题变色；扩展管理页面上的图标保持不变。

## 更新

使用新版启动器重新准备扩展，然后在每个已安装的浏览器中点击扩展卡片上的**重新加载**。固定目录为 `%LOCALAPPDATA%\NDLauncher\ChromeExtension`，请勿删除。文件共用，设置按浏览器配置文件保存。如果直接从 `chrome_extension` 加载扩展，请更新原文件夹中的文件。

## 下载支持

支持 `.safetensors`、`.ckpt`、`.pt`、`.pth`、`.bin`、`.gguf` 和 `.zip`。通过原始网址或下载来源识别网站，需要本地 Windows 目标路径。不支持无痕模式。

Hugging Face 和 Civitai 的受限模型可能需要在启动器中配置 API 令牌。不会传输浏览器 Cookie。ModelScope 支持公开文件和可访问的签名链接。如果交接前启动器不可用，下载会留在浏览器中。对于待传输任务，可使用连接面板中的**重试传输**。

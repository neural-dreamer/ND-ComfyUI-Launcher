# ND Launcher browser extension

[English](INSTALL.md) · [Русский](INSTALL_RU.md) · [中文](INSTALL.zh-CN.md)

The extension hands model downloads from **Hugging Face, Civitai.com, Civitai.red and ModelScope.cn** to ND Launcher, keeping the destination folder selected in the browser. The launcher must be running to receive downloads; ComfyUI itself can remain stopped.

## Installation and connection

1. In the launcher, open **Settings → Browser downloads → Install browser extension**.
2. Choose a detected browser, or use **Browse…** to select a portable browser. This choice is saved separately from the browser used for ComfyUI.
3. Click **Prepare and open folder**. The launcher prepares a permanent folder and selects it in Explorer; its path is also shown in the dialog and copied to the clipboard.
4. Open that browser’s extensions page yourself. Enable developer mode, choose **Load unpacked**, and select the prepared folder. If your browser supports folder drag-and-drop installation, you can drag it onto that page instead.
5. Enable browser model downloads in the launcher and copy the connection key.
6. Open the extension, expand **Connection**, paste the key, click **Save**, then **Test connection**. Turn on the interception switch.
7. Enable your browser’s option to ask where each download should be saved, so you can select the model’s destination folder.

| Browser | Extensions page |
|---|---|
| Chrome / Chromium / Thorium | `chrome://extensions/` |
| Yandex Browser | `browser://extensions/` |
| Microsoft Edge | `edge://extensions/` |
| Brave | `brave://extensions/` |
| Opera / Opera GX | `opera://extensions/` |
| Vivaldi | `vivaldi://extensions/` |

The setup helper supports the Chromium browsers listed above. Firefox is not supported. The final installation step is manual; administrator rights are not required.

Alternative setup: run [INSTALL_BROWSER.bat](INSTALL_BROWSER.bat). It offers a browser selection, prepares the folder and opens the browser. This helper does not require Python. Downloads still require a running launcher.

## Interface

- Select **РУ / EN / 中文** from the top-right language menu.
- The large switch enables or disables interception and saves the change immediately.
- **Connection** and **Getting started** are collapsed by default.
- The colored capsules at the bottom select **Neon / Foggy Night / Classic**. Theme and language are saved in the browser profile. The logo and toolbar icon follow the theme; the icon on the browser’s extension management page remains unchanged.

## Updating

Prepare the extension again from the updated launcher, then click **Reload** on its card in each browser where it is installed. The permanent folder is `%LOCALAPPDATA%\NDLauncher\ChromeExtension`; do not delete it. Files are shared, while settings belong to the browser profile. If you loaded the extension directly from `chrome_extension`, update the files in that original folder instead.

## Download support

Formats: `.safetensors`, `.ckpt`, `.pt`, `.pth`, `.bin`, `.gguf`, `.zip`. Interception identifies the site using the original URL or download referrer and requires a local Windows destination path. Incognito is not supported.

Restricted Hugging Face and Civitai models may require API tokens in the launcher. Browser cookies are not forwarded. ModelScope supports public files and accessible signed links. If the launcher is unavailable before handoff, the download stays in the browser. Use **Retry transfer** in the connection panel for pending transfers.

# ND Launcher browser extension

[English](INSTALL.md) · [Русский](INSTALL_RU.md) · [中文](INSTALL.zh-CN.md)

The extension hands model downloads from **Hugging Face, Civitai.com, Civitai.red and ModelScope.cn** to ND Launcher, keeping the destination folder selected in the browser. The launcher must be running to receive downloads; ComfyUI itself can remain stopped.

## Installation and connection

The extension is published in the [Chrome Web Store](https://chromewebstore.google.com/detail/ikiegihpjhkejmbbbdiiombnaihannca).

1. In the launcher, open **Settings → Browser downloads → Install browser extension**.
2. Choose a detected browser, or use **Browse…** to select a portable browser. This choice is saved separately from the browser used for ComfyUI.
3. Click **Open page in Chrome Web Store**. The launcher opens the extension page in that browser; click **Add to Chrome** (or the equivalent button). You can also open the [store page](https://chromewebstore.google.com/detail/ikiegihpjhkejmbbbdiiombnaihannca) yourself in any Chromium browser, or use **Copy link**.
4. Enable browser model downloads in the launcher and copy the connection key.
5. Open the extension, expand **Connection**, paste the key, click **Save**, then **Test connection**. Turn on the interception switch.
6. Enable your browser’s option to ask where each download should be saved, so you can select the model’s destination folder.

Opera does not install from the Chrome Web Store by itself: add the “Install Chrome Extensions” add-on first. Firefox is not supported.

### Manual installation (fallback)

If the store is unavailable, use **Install manually from folder** in the same dialog. The launcher prepares a permanent folder and selects it in Explorer. Open your browser’s extensions page, enable developer mode, choose **Load unpacked** and select that folder. Alternatively run [INSTALL_BROWSER.bat](INSTALL_BROWSER.bat). Browsers such as Yandex Browser may disable unpacked extensions on every start, so prefer the store version.

| Browser | Extensions page |
|---|---|
| Chrome / Chromium / Thorium | `chrome://extensions/` |
| Yandex Browser | `browser://extensions/` |
| Microsoft Edge | `edge://extensions/` |
| Brave | `brave://extensions/` |
| Opera / Opera GX | `opera://extensions/` |
| Vivaldi | `vivaldi://extensions/` |

The launcher can open the store page in the Chromium browsers listed above. Administrator rights are not required. Downloads still require a running launcher.

## Interface

- Select **РУ / EN / 中文** from the top-right language menu.
- The large switch enables or disables interception and saves the change immediately.
- **Connection** and **Getting started** are collapsed by default.
- The colored capsules at the bottom select **Neon / Foggy Night / Classic**. Theme and language are saved in the browser profile. The logo and toolbar icon follow the theme; the icon on the browser’s extension management page remains unchanged.

## Updating

The store version updates automatically. If you installed manually, prepare the extension again from the updated launcher, then click **Reload** on its card in each browser where it is installed. The permanent folder is `%LOCALAPPDATA%\NDLauncher\ChromeExtension`; do not delete it. Files are shared, while settings belong to the browser profile. If you loaded the extension directly from `chrome_extension`, update the files in that original folder instead.

## Download support

Formats: `.safetensors`, `.ckpt`, `.pt`, `.pth`, `.bin`, `.gguf`, `.zip`. Interception identifies the site using the original URL or download referrer and requires a local Windows destination path. Incognito is not supported.

Restricted Hugging Face and Civitai models may require API tokens in the launcher. Browser cookies are not forwarded. ModelScope supports public files and accessible signed links. If the launcher is unavailable before handoff, the download stays in the browser. Use **Retry transfer** in the connection panel for pending transfers.

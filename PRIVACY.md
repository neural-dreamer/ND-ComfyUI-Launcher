# Privacy policy — ND Launcher browser extension

**English** · [Русский](#политика-конфиденциальности--расширение-nd-launcher) · [中文](#隐私政策--nd-launcher-浏览器扩展)

Last updated: 2026-10-25

The **ND Launcher — Model Downloads** browser extension is a companion to the free, open-source desktop app [ND · ComfyUI Launcher](https://github.com/neural-dreamer/ND-ComfyUI-Launcher). It hands model downloads from Hugging Face, Civitai.com, Civitai.red and ModelScope.cn over to the launcher running on the same computer.

## Short version

The extension **does not collect, sell or share any personal data**, has no analytics or telemetry, and **never contacts any server on the internet**. Everything it does stays on your computer.

## What the extension processes

- **Download details**: for a download that starts from a supported site (Hugging Face, Civitai, ModelScope) and is a model file (`.safetensors`, `.ckpt`, `.pt`, `.pth`, `.bin`, `.gguf`, `.zip`), the extension reads its address (URL), the page it came from, the local file name chosen in the browser and the file size. It pauses the download, sends these details to the launcher, and then cancels the browser download so that the launcher can download the file. Downloads from other sites, and downloads in Incognito windows, are ignored.
- **Where it sends them**: only to `http://127.0.0.1:17863` — the ND Launcher application on your own computer. Nothing is sent to the developer or to any other party.
- **What it stores** (in the browser's local extension storage, on your computer only): the connection key you pasted from the launcher, the on/off switch, the interface language and theme, the last status message, and a short-lived record of a handoff in progress so it can be finished after a restart. Removing the extension deletes this data.
- **What it does not do**: it does not read page contents, browsing history, cookies or passwords, and does not forward cookies to the launcher. It does not load or run remote code.

## Third parties

The extension itself talks to no third parties. After the handoff, the launcher application (not the extension) downloads the file directly from the original site, using an API token only if you have entered one in the launcher; that is governed by the launcher, which also sends no telemetry.

## Your control

You can turn interception off with the switch in the extension, or remove the extension at any time. Source code of both the extension and the launcher is public under GPL-3.0.

## Contact

Questions: <https://github.com/neural-dreamer/ND-ComfyUI-Launcher/issues>

---

## Политика конфиденциальности — расширение ND Launcher

Дата обновления: 25.10.2026

Расширение **ND Launcher — Model Downloads** работает вместе с бесплатным приложением с открытым исходным кодом [ND · ComfyUI Launcher](https://github.com/neural-dreamer/ND-ComfyUI-Launcher). Оно передаёт загрузки моделей с Hugging Face, Civitai.com, Civitai.red и ModelScope.cn в лаунчер, запущенный на том же компьютере.

**Коротко.** Расширение **не собирает, не продаёт и не передаёт персональные данные**, не содержит аналитики и телеметрии и **не обращается ни к одному серверу в интернете**. Всё происходит на вашем компьютере.

**Что обрабатывает расширение.** Для загрузки модельного файла (`.safetensors`, `.ckpt`, `.pt`, `.pth`, `.bin`, `.gguf`, `.zip`) с поддерживаемого сайта оно читает адрес файла, страницу-источник, выбранное в браузере имя файла на диске и размер. Затем ставит загрузку на паузу, отправляет эти сведения лаунчеру и отменяет загрузку в браузере, чтобы файл скачал лаунчер. Загрузки с других сайтов и в режиме инкогнито игнорируются.

**Куда отправляются данные.** Только на `http://127.0.0.1:17863` — приложение ND Launcher на вашем компьютере. Разработчику и третьим лицам ничего не передаётся.

**Что хранится** (локально в хранилище расширения): ключ подключения из лаунчера, переключатель, язык и тема интерфейса, последнее сообщение о состоянии и временная запись о передаче, чтобы завершить её после перезапуска. При удалении расширения эти данные удаляются.

**Чего расширение не делает.** Не читает содержимое страниц, историю, cookies и пароли, не передаёт cookies лаунчеру, не загружает и не выполняет удалённый код.

**Третьи лица.** Само расширение ни с кем не взаимодействует. После передачи файл скачивает лаунчер (не расширение) напрямую с исходного сайта; API-токен используется, только если вы сами ввели его в лаунчере. Лаунчер тоже не отправляет телеметрию.

**Ваш контроль.** Перехват можно выключить переключателем в расширении или удалить расширение. Исходный код расширения и лаунчера открыт (GPL-3.0).

Вопросы: <https://github.com/neural-dreamer/ND-ComfyUI-Launcher/issues>

---

## 隐私政策 — ND Launcher 浏览器扩展

更新日期：2026-10-25

**ND Launcher — Model Downloads** 扩展是免费开源桌面应用 [ND · ComfyUI Launcher](https://github.com/neural-dreamer/ND-ComfyUI-Launcher) 的配套工具，用于把 Hugging Face、Civitai.com、Civitai.red 和 ModelScope.cn 上的模型下载交给本机运行的启动器。

**简述。** 本扩展**不收集、不出售、不分享任何个人数据**，没有统计或遥测，也**不会连接互联网上的任何服务器**。所有操作都只在你的电脑上完成。

**处理的内容。** 当从受支持网站开始下载模型文件（`.safetensors`、`.ckpt`、`.pt`、`.pth`、`.bin`、`.gguf`、`.zip`）时，扩展会读取文件地址、来源页面、浏览器中选定的本地文件名和文件大小，暂停下载，把这些信息发送给启动器，然后取消浏览器下载，由启动器接手。其他网站的下载和无痕窗口中的下载会被忽略。

**发送到哪里。** 仅发送到 `http://127.0.0.1:17863`，即你电脑上的 ND Launcher。不会向开发者或任何第三方发送任何内容。

**存储的内容**（仅保存在本机扩展存储中）：从启动器复制的连接密钥、开关状态、界面语言和主题、最近一次状态消息，以及用于重启后继续完成的临时传递记录。卸载扩展后这些数据会被删除。

**不会做的事。** 不读取网页内容、浏览历史、Cookie 或密码，不向启动器转发 Cookie，不加载或运行远程代码。

**第三方。** 扩展本身不与任何第三方通信。传递之后由启动器（而非扩展）直接从原网站下载文件；仅当你在启动器中填写了 API 令牌时才会使用。启动器同样不发送遥测数据。

**你的控制权。** 可随时用扩展中的开关关闭接管，或卸载扩展。扩展和启动器的源代码均以 GPL-3.0 公开。

问题反馈：<https://github.com/neural-dreamer/ND-ComfyUI-Launcher/issues>

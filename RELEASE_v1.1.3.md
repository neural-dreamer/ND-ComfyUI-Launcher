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

**Update:** download **Source code (zip)** below, run `build_exe.bat` again and replace `ND_Launcher.exe` in your build. Settings are kept. Set up the optional browser extension under **Settings → Browser downloads**. First install? See the [README](https://github.com/neural-dreamer/ND-ComfyUI-Launcher#installation).

<details>
<summary><b>Русский</b></summary>

Загрузки моделей из браузера, команды после обновления и более наглядный прогресс загрузок.

- **Расширение браузера** для Hugging Face, Civitai.com, Civitai.red и ModelScope.cn: передаёт загрузку лаунчеру, сохраняя выбранную в браузере папку. Лаунчер может автоматически выходить на передний план.
- Подготовка расширения из настроек лаунчера для Chrome, Яндекс Браузера, Edge и других поддерживаемых Chromium-браузеров. Три языка, три темы и цвета логотипа и значка под выбранную тему.
- **Команды после обновления** ComfyUI и/или кастом-нод выполняются через portable Python выбранной сборки. Опциональный блок свёрнут по умолчанию.
- Автоматическая проверка новых версий лаунчера с возможностью отключения.
- Общая папка назначения для выбранных файлов; прогресс и скорость каждого файла в очереди, изменяемая ширина столбцов.
- Обновление ComfyUI через штатные батники сборки с переходом на stable, в том числе после обновления зависимостей.
- Большие прямые загрузки запускаются без предварительного выделения места под весь файл; отмена не блокирует интерфейс.
- Прогресс генерации не пропадает между шагами; отмена загрузки из паузы убирает её прогресс-бар.

**Как обновиться:** скачай **Source code (zip)** ниже, снова запусти `build_exe.bat` и замени `ND_Launcher.exe` в сборке. Настройки сохранятся. Необязательное расширение подключается через **Настройки → Загрузки из браузера**.

</details>

<details>
<summary><b>中文</b></summary>

新增浏览器模型下载、更新后命令，并改进下载进度显示。

- **浏览器扩展**支持 Hugging Face、Civitai.com、Civitai.red 和 ModelScope.cn：将下载交给启动器，保留在浏览器中选择的保存文件夹，并可自动将启动器置于前台。
- 可在启动器设置中为 Chrome、Yandex Browser、Edge 等受支持的 Chromium 浏览器准备扩展。扩展支持三种语言、三种主题，徽标和工具栏图标随主题变色。
- **更新后命令**：在更新 ComfyUI 和/或自定义节点后，通过所选整合包的便携 Python 执行。此可选面板默认折叠。
- 自动检查启动器新版本，可在设置中关闭。
- 所选文件使用统一的目标文件夹；队列显示每个文件的进度和速度，列宽可调整。
- 使用整合包自带的批处理文件更新 ComfyUI，最终切换到 stable，包括更新依赖项的情况。
- 大文件直接下载不再预先分配整个文件的空间，取消下载不会阻塞界面。
- 生成进度在步骤之间保持显示；取消已暂停的下载后，其进度条会消失。

**更新方法：**下载下方的 **Source code (zip)**，重新运行 `build_exe.bat`，替换整合包中的 `ND_Launcher.exe`。设置会保留。可在 **设置 → 浏览器下载** 中配置可选扩展。

</details>

<div align="center">

<img src="docs/logo.png" width="180" alt="ND · ComfyUI Launcher">

# ND · ComfyUI Launcher

**Лаунчер в одном окне для любой портативной сборки ComfyUI под Windows**

[![Release](https://img.shields.io/github/v/release/neural-dreamer/ND-ComfyUI-Launcher?color=00c8e0)](https://github.com/neural-dreamer/ND-ComfyUI-Launcher/releases/latest)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-ff2bd6)](LICENSE)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-555)

[English](README.md) · **Русский** · [中文](README.zh-CN.md)

</div>

Больше никаких батников и аргументов запуска по памяти. ND Launcher запускает ComfyUI с нужными настройками, обновляет его и кастом-ноды, ставит новые ноды и модели, переносит всё из старой сборки. Консоль, монитор видеокарты и воркфлоу собраны в одном месте.

![ND Launcher](docs/screenshots/launch.png)

## Возможности

- **Запуск** — готовые пресеты («Стандарт», «Экономия VRAM», «Максимум скорости», «Видео и большие модели», «Только CPU») и свои. Режим VRAM, attention (SageAttention, FlashAttention), fp8 / fp16, резерв VRAM, доступ по сети и порт — обычными настройками. Ярлык на рабочий стол в один клик: сразу запускает ComfyUI, при желании — свёрнутым в трей.
- **Консоль** — вывод ComfyUI прямо в окне с подсветкой ошибок, прогресс генерации и монитор видеокарты (VRAM, загрузка, температура).
- **Воркфлоу** — все воркфлоу сборки с поиском и панелью описания: что делает, как пользоваться, какие модели нужны — с проверкой, какие из них уже есть в сборке.
- **Обновления** — ComfyUI (с зависимостями или без) и все кастом-ноды в один клик; включение и отключение нод без удаления.
- **Установка нод** — вставь одну или несколько ссылок на репозитории (GitHub, GitLab, ветка или короткая запись `автор/репозиторий`): нода клонируется, зависимости ставятся сами.
- **Загрузка моделей** — вставь ссылку Hugging Face или Civitai, выбери файлы и папки назначения, перед стартом видно свободное место на диске.
  - Hugging Face качается официальной командой `hf download` с ускорением Xet.
  - Civitai качается до 16 потоками, без дополнительных программ.
  - Корни папок можно брать из `extra_model_paths.yaml`.
- **Перенос** — настройки, воркфлоу, модели, Input / Output, `extra_model_paths.yaml` и кастом-ноды из другой сборки ComfyUI. Недостающие ноды определяются автоматически. Модели можно скопировать, переместить, мгновенно связать жёсткими ссылками или подключить без копирования.
- **Удобство** — 3 темы («Неон», «Туманная ночь», «Классик»), 3 языка (русский, английский, китайский), выбор браузера (в том числе режим отдельного приложения), сворачивание в трей, защита от повторного запуска.

<p align="center">
  <img src="docs/screenshots/transfer.png" width="49%" alt="Перенос">
  <img src="docs/screenshots/models.png" width="49%" alt="Загрузка моделей">
</p>

## Установка

Лаунчер распространяется исходным кодом: `ND_Launcher.exe` собирается на твоём компьютере одним кликом. Файл, собранный у тебя, Windows не считает скачанным из интернета, поэтому SmartScreen его не блокирует.

### Сборка exe (рекомендуется)

1. Установи [Python 3.10 или новее](https://www.python.org/downloads/windows/). В установщике отметь **Add python.exe to PATH**.
2. Скачай исходники: [последний релиз](https://github.com/neural-dreamer/ND-ComfyUI-Launcher/releases/latest) → **Source code (zip)** или **Code → Download ZIP** на этой странице. Перед распаковкой открой **Свойства** архива и отметь **Разблокировать**, чтобы Windows не предупреждала о `.bat`-файлах.
3. Распакуй в любую папку и запусти `build_exe.bat`. Нужен интернет, первая сборка занимает несколько минут; всё, что он ставит, остаётся в папке `.build_venv` рядом с ним.
4. Возьми `dist\ND_Launcher.exe` и положи в корень портативной сборки ComfyUI, рядом с папками `python_embeded` и `ComfyUI`:
   ```
   ComfyUI_windows_portable\
   ├── ComfyUI\
   ├── python_embeded\
   └── ND_Launcher.exe
   ```
5. Запусти. Готовому exe больше ничего не нужно, его можно копировать в другие сборки и на другие компьютеры.

> Некоторые антивирусы не доверяют exe, собранным через PyInstaller, независимо от содержимого. Если твой удалит `ND_Launcher.exe`, добавь его в исключения или используй вариант ниже.

### Запуск без exe

Скопируй в корень сборки `nd_launcher.py`, `nd_i18n.py`, `nd_icon.ico`, папку `brand\` и `ND_Launcher.bat`, затем запусти `ND_Launcher.bat`. При первом запуске он поставит PySide6 в `python_embeded`.

**Требования:** Windows 10 / 11 (64-бит) и любая портативная сборка ComfyUI с `python_embeded`. По желанию: [Git for Windows](https://git-scm.com) для обновления кастом-нод и видеокарта NVIDIA для монитора GPU.

## Полезно знать

- **Аргументы запуска.** `--enable-manager`, `--enable-manager-legacy-ui` и `--max-upload-size 999` включены по умолчанию и отключаются галочками на вкладке «Запуск». Для `--enable-manager` нужен свежий ComfyUI с pip-версией ComfyUI-Manager: в старых сборках его лучше выключить.
- **Настройки** хранятся в `nd_launcher.json` рядом с лаунчером.
- **API-токены** зашифрованы средствами Windows (DPAPI): расшифровать их может только твой пользователь Windows на этом компьютере.
- **Сеть.** Лаунчер не отправляет телеметрию. В сеть он выходит только для функций, которыми ты пользуешься: загрузки, установка и обновление нод.
- **Картинка-пример.** После каждого обновления ComfyUI лаунчер заменяет `ComfyUI/input/example.png` логотипом Neural Dreamer. В «Настройках» можно выбрать свою картинку или отключить замену.
- **Описания воркфлоу** лежат в `utils/*.ndesc` (обычный JSON). Если их нет, на вкладке «Воркфлоу» остаётся только список. Чтобы сгенерировать описания нейросетью (Claude, ChatGPT и другими), используй [скилл ndesc-writer](skills/ndesc-writer/SKILL.md). См. также [описание формата](docs/NDESC_FORMAT.md) и [пример](utils/workflows.ndesc.example).

## Для разработчиков

- **Релиз.** Подними `VERSION` в `nd_launcher.py`, добавь раздел в [CHANGELOG.md](CHANGELOG.md) и опубликуй релиз на GitHub с тегом вида `v1.1.0`, а в описание вставь раздел из CHANGELOG.
- **Свой брендинг в форке.** `ND_Links_Editor.bat` меняет ссылки, которые показывает лаунчер, а `brand\example.png` можно заменить своим логотипом. Затем собери exe через `build_exe.bat`.

## Лицензия

[GPL-3.0-or-later](LICENSE) © 2026 Neural Dreamer. Лаунчер можно использовать, изучать, распространять и изменять; изменённые версии должны оставаться открытыми под той же лицензией.

ND Launcher — независимый проект, он не связан с ComfyUI или Comfy Org.

## Ссылки

[YouTube](https://www.youtube.com/@neural_dreamer) · [VK Видео](https://vkvideo.ru/@neural_dreamer) · [Boosty](https://boosty.to/neural_dreamer) · [Patreon](https://www.patreon.com/cw/neural_dreamer) · [Civitai](https://civitai.red/user/Neural_Dreamer) · [Hugging Face](https://huggingface.co/NeuralDreamer)

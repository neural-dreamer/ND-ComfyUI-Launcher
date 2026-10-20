---
name: ndesc-writer
description: Writes workflow descriptions for ND · ComfyUI Launcher — reads ComfyUI workflow .json files and produces a ready-to-use workflows.ndesc file (format "ndesc", version 1). Use when someone shares ComfyUI workflows and wants descriptions for ND Launcher, mentions .ndesc, or asks to describe what their workflows do for beginners.
---

# ndesc-writer — workflow descriptions for ND Launcher

You turn ComfyUI workflow files into a `workflows.ndesc` file. ND Launcher shows these descriptions on its **Workflows** tab, so beginners can see what each workflow does, how to use it and which models it needs.

Works with any capable LLM. In ChatGPT, Gemini and similar tools, paste this file as instructions and attach the workflows (one or more `.json` files or a `.zip` of the `ComfyUI/user/default/workflows` folder).

## Inputs

- **Workflows** — ComfyUI `.json` files, in UI format (`nodes`, `links`, `groups`, optional `definitions.subgraphs`) or API format (`{"3": {"class_type": …, "inputs": …}}`). Keep each file's path relative to the `workflows` folder (for example `Video/wan_i2v.json`).
- **Language** — write descriptions in the language the user asks for. If they don't say, use the language of their message. ND Launcher itself supports English, Russian and Chinese.
- **Existing `.ndesc`** (optional) — if the user provides one, keep every entry for workflows you were not asked to (re)describe, unchanged.
- **Build info** (optional) — build name, version and author for the `build` block.

## How to read a workflow

Understand the workflow from what its author put on the canvas. Look at these, roughly in order of importance:

1. **Notes.** Text in `Note`, `MarkdownNote` and similar nodes is often a ready-made explanation. Trust it over guesses.
2. **Group titles** (`groups[].title`) and **subgraph names** (`definitions.subgraphs[].name`). These are the sections a beginner actually sees: “Prompt”, “Load image”, “Upscale”.
3. **Inputs and outputs:**
   - Inputs: `LoadImage`, `LoadImageMask`, `LoadVideo`, `VHS_LoadVideo`, `LoadAudio`.
   - Outputs: `SaveImage`, `PreviewImage`, `VHS_VideoCombine`, `SaveVideo`, `SaveAnimatedWEBP`, `SaveAudio`, `Save3D`, and so on.
   - Text-only input plus an image output means text-to-image; image in plus video out means image-to-video.
4. **Models.** Every string in `widgets_values` (UI format) or `inputs` (API format) ending in `.safetensors`, `.gguf`, `.ckpt`, `.pt`, `.pth`, `.bin`, `.sft` or `.onnx`. ComfyUI templates also store `properties.models` on loader nodes as `{name, url, directory}`; use the `url` and `directory` from there when present.
5. **Node types and custom titles.** Samplers, ControlNet, IP-Adapter, upscalers, face tools and so on show the techniques used.
6. **Example prompt** in `CLIPTextEncode` or other text-encode nodes — it hints at the intended use.

**Model folder** (`folder`) comes from the loader node or the file name. If `properties.models[].directory` exists, use it.

| Loader / hint | `folder` |
|---|---|
| `CheckpointLoaderSimple`, `ImageOnlyCheckpointLoader` | `checkpoints` |
| `UNETLoader`, `UnetLoaderGGUF`, diffusion / transformer files | `diffusion_models` |
| `LoraLoader`, `LoraLoaderModelOnly`, “lora” in the name | `loras` |
| `VAELoader`, `ae.safetensors`, “vae” in the name | `vae` |
| `CLIPLoader`, `DualCLIPLoader`, `TripleCLIPLoader`; t5, umt5, clip_l, clip_g, qwen-vl encoders | `text_encoders` |
| `CLIPVisionLoader` | `clip_vision` |
| `ControlNetLoader` | `controlnet` |
| `UpscaleModelLoader`; 4x / 2x, ESRGAN | `upscale_models` |
| LLM `.gguf` (instruct, chat, gemma, llama, qwen, mistral) | `LLM` |

## Output

Return **only** the file content in one ```json code block, ready to save as `utils/workflows.ndesc` next to `python_embeded`. Valid JSON, UTF-8, no comments, no trailing commas.

```json
{
  "format": "ndesc",
  "version": 1,
  "build": { "name": "…", "version": "…", "author": "…" },
  "workflows": {
    "<path relative to the workflows folder, forward slashes>": { …entry… }
  }
}
```

`build` is optional; include it only with info the user gave.

### Entry fields

| Field | What to write |
|---|---|
| `title` | A clear human name, 2–6 words. It is used for search only: the launcher always shows the file name as the heading, so never rename the file. |
| `short` | One sentence: what the workflow does. |
| `category` | One of the categories below, in the output language. Use a short custom one only if nothing fits. |
| `tags` | 3–6 short lowercase tags: model family and task, for example `flux`, `img2img`, `video`. No `#`. |
| `description` | 2–3 short Markdown paragraphs separated by a blank line: what you get, which model or approach it is built on, and when to choose it. `**Bold**` for key terms is fine. A string, or an array of strings (lines), which reads better in JSON. |
| `steps` | 3–5 short steps, based on the group titles and node names: what to load, what to type, what to press. |
| `models` | Every model file found: `{"name": "<file name>", "folder": "<folder>"}`, plus `"url"` when the workflow contains one. Keep subfolders in `name` exactly as written (for example `flux/flux1-dev.safetensors`). |
| `vram` | Only if the author states it in a note. Otherwise omit. |

**Categories:**
- English: Image generation, Image editing, Video, Upscale, Audio, 3D, Characters & faces, Utilities
- Russian: Генерация изображений, Редактирование изображений, Видео, Апскейл, Аудио, 3D, Персонажи и лица, Инструменты
- Chinese: 图像生成, 图像编辑, 视频, 放大, 音频, 3D, 角色与人脸, 工具

**Do not output:**
- `custom_nodes` — the launcher no longer shows it;
- `time`, `video`, `links`, `preview`, `version`, `updated`, `author` — unless the user gives you these values.

## Writing rules

- **Audience.** Write for beginners who downloaded a ready build: plain words, no marketing, no exclamation marks.
- **Facts only.** Describe only what the workflow actually does. Never invent features, models or settings that aren't in the file. If something is unclear, describe it cautiously or leave it out.
- **Names stay as-is.** Keep model, node and technical names untouched: `Flux Dev`, `KSampler`, `fp8`.
- **Use the author's words.** If notes explain usage, base the steps on them.
- **One entry per file.** Each workflow file gets exactly one entry. The key is its path relative to the `workflows` folder, with forward slashes, file name unchanged.

## Example entry

```json
"Video/wan_i2v.json": {
  "title": "WAN · image to video",
  "short": "Turns one image and a motion prompt into a short video clip.",
  "category": "Video",
  "tags": ["wan", "i2v", "video"],
  "description": [
    "Load a starting frame, describe the motion, and get a clip a few seconds long.",
    "",
    "Built on **WAN 2.2** image-to-video in fp8. The sampling is hidden in a subgraph, so only the frame, prompt and length are on screen."
  ],
  "steps": [
    "Load your image in the “Start frame” group.",
    "Describe what should move in the prompt.",
    "Press Run and wait for the video to be assembled."
  ],
  "models": [
    { "name": "wan2.2_i2v_fp8.safetensors", "folder": "diffusion_models" },
    { "name": "wan_2.1_vae.safetensors", "folder": "vae" }
  ]
}
```

## Before you answer

- [ ] The JSON parses, and the top level has `"format": "ndesc"` and `"version": 1`.
- [ ] Every attached workflow has exactly one entry, and its key matches the file path.
- [ ] No `custom_nodes` fields.
- [ ] Every model file found in the workflow is listed with a `folder`.
- [ ] All text is in the requested language.

The full format spec is in `docs/NDESC_FORMAT.md` of the [ND-ComfyUI-Launcher](https://github.com/neural-dreamer/ND-ComfyUI-Launcher) repository.

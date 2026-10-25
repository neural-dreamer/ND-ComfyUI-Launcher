"""Model paths (nd_modelpaths.py): extra_model_paths.yaml editing, detection and links."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nd_modelpaths as M  # noqa: E402

MANUAL = """# мой комментарий в начале
comfyui:
    base_path: "F:/Models/"
    # комментарий внутри
    loras: loras/
    checkpoints: |
        checkpoints/
        sd15/

other_ui:
    base_path: path/to/stable-diffusion-webui/
    checkpoints: models/Stable-diffusion
"""


class ModelPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.comfy = self.tmp / "Build" / "ComfyUI"
        (self.comfy / "models" / "checkpoints").mkdir(parents=True)
        (self.comfy / "main.py").write_text("")
        self.yaml_dir = str(self.comfy)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, rel, n=1):
        d = self.tmp / rel
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"m{i}.safetensors").write_bytes(b"x")
        return d

    def test_parse_manual_sections(self):
        secs = M.parse(MANUAL, self.yaml_dir)
        self.assertEqual([s["key"] for s in secs], ["comfyui", "other_ui"])
        self.assertEqual(secs[0]["entries"], [("loras", ["loras/"]), ("checkpoints", ["checkpoints/", "sd15/"])])
        self.assertFalse(secs[0]["managed"])
        self.assertEqual(os.path.normpath(secs[1]["base"]), os.path.normpath(os.path.join(self.yaml_dir, "path/to/stable-diffusion-webui")))

    def test_upsert_keeps_manual_text(self):
        text = M.upsert(MANUAL, self.yaml_dir, "nd_old", "Старая сборка", "D:/AI/Old/ComfyUI",
                        [("loras", ["models/loras/"]), ("TTS", ["models/TTS/"]), ("LLM", ["models/LLM/"])])
        self.assertTrue(text.startswith(MANUAL.rstrip("\n")))
        secs = M.parse(text, self.yaml_dir)
        nd = secs[-1]
        self.assertEqual((nd["key"], nd["title"], nd["managed"]), ("nd_old", "Старая сборка", True))
        self.assertEqual([t for t, _ in nd["entries"]], ["loras", "TTS", "LLM"])
        # повторное сохранение заменяет только свою секцию
        text2 = M.upsert(text, self.yaml_dir, "nd_old", "Старая сборка", "D:/AI/Old/ComfyUI", [("sam3", ["models/sam3/"])])
        self.assertIn("# комментарий внутри", text2)
        self.assertEqual(M.parse(text2, self.yaml_dir)[-1]["entries"], [("sam3", ["models/sam3/"])])
        self.assertEqual(text2.count("nd_old:"), 1)

    def test_disable_enable_remove(self):
        text = M.upsert(MANUAL, self.yaml_dir, "nd_a", "A", "D:/A", [("loras", ["loras/"])])
        off = M.set_enabled(text, self.yaml_dir, "nd_a", False)
        sec = [s for s in M.parse(off, self.yaml_dir) if s["key"] == "nd_a"][0]
        self.assertFalse(sec["enabled"])
        self.assertNotIn("\nnd_a:", off)          # для ComfyUI секция закомментирована
        on = M.set_enabled(off, self.yaml_dir, "nd_a", True)
        self.assertEqual(on, text)
        manual_off = M.set_enabled(MANUAL, self.yaml_dir, "comfyui", False)
        self.assertEqual(M.set_enabled(manual_off, self.yaml_dir, "comfyui", True), MANUAL)
        gone = M.remove(text, self.yaml_dir, "nd_a")
        self.assertEqual(gone, MANUAL)

    def test_single_default(self):
        text = M.upsert("", self.yaml_dir, "nd_a", "A", "D:/A", [("loras", ["loras/"])], is_default=True)
        text = M.upsert(text, self.yaml_dir, "nd_b", "B", "D:/B", [("loras", ["loras/"])], is_default=True)
        self.assertEqual([s["is_default"] for s in M.parse(text, self.yaml_dir)], [False, True])

    def test_detect_build_and_folder(self):
        old = self.tmp / "Old" / "ComfyUI"
        (old / "comfy").mkdir(parents=True)
        self.make("Old/ComfyUI/models/loras", 3)
        self.make("Old/ComfyUI/models/TTS", 2)
        self.make("Old/ComfyUI/models/sam3", 1)
        d = M.detect(self.tmp / "Old")
        self.assertEqual(d["kind"], "build")
        self.assertEqual({(i["type"], i["sub"], i["files"]) for i in d["items"]},
                         {("loras", "models/loras/", 3), ("TTS", "models/TTS/", 2), ("sam3", "models/sam3/", 1)})
        self.make("Shared/LLM", 2)
        f = M.detect(self.tmp / "Shared")
        self.assertEqual((f["kind"], f["items"][0]["type"], f["items"][0]["sub"]), ("folder", "LLM", "LLM/"))
        flat = M.detect(self.make("Flat", 4))
        self.assertEqual((flat["items"][0]["type"], flat["items"][0]["files"]), ("", 4))
        self.assertEqual((M.default_method("loras"), M.default_method("TTS")), (M.YAML, M.BOTH))

    def test_links_never_delete_target(self):
        target = self.make("Old/ComfyUI/models/TTS", 2)
        link, mode = M.plan_link(self.comfy, "TTS", target, "Old build")
        self.assertEqual((Path(link), mode), (self.comfy / "models" / "TTS", "folder"))
        M.create_link(link, target)
        self.assertTrue(M.is_link(link))
        self.assertEqual(M.plan_link(self.comfy, "TTS", target, "Old build")[1], "exists")
        self.assertEqual([Path(x[0]).name for x in M.list_links(self.comfy)], ["TTS"])
        # своя непустая папка не заменяется — ссылка ставится подпапкой
        self.make("Build/ComfyUI/models/checkpoints", 1)
        other = self.make("Old/ComfyUI/models/checkpoints", 1)
        link2, mode2 = M.plan_link(self.comfy, "checkpoints", other, "Old build")
        self.assertEqual((Path(link2), mode2), (self.comfy / "models" / "checkpoints" / "Old_build", "subfolder"))
        M.create_link(link2, other)
        M.remove_link(link)
        M.remove_link(link2)
        self.assertEqual(len(list(target.iterdir())), 2)
        self.assertEqual(len(list(other.iterdir())), 1)
        with self.assertRaises(ValueError):
            M.remove_link(self.comfy / "models" / "checkpoints")   # обычную папку удалить нельзя

    def test_search_order(self):
        text = M.upsert("", self.yaml_dir, "nd_a", "A", str(self.tmp / "A"), [("checkpoints", ["ck/"])])
        text = M.upsert(text, self.yaml_dir, "nd_b", "B", str(self.tmp / "B"), [("checkpoints", ["ck/"]), ("TTS", ["tts/"])], is_default=True)
        order = M.search_order(self.comfy, M.parse(text, self.yaml_dir))
        self.assertEqual([src for _, src in order["checkpoints"]], ["B", "build", "A"])
        self.assertEqual([src for _, src in order["TTS"]], ["B"])
        off = M.set_enabled(text, self.yaml_dir, "nd_b", False)
        self.assertNotIn("TTS", M.search_order(self.comfy, M.parse(off, self.yaml_dir)))

    def test_write_keeps_backup(self):
        y = self.comfy / "extra_model_paths.yaml"
        y.write_text(MANUAL, encoding="utf-8")
        M.write(y, "new: 1\n")
        self.assertEqual((self.comfy / "extra_model_paths.yaml.bak").read_text(encoding="utf-8"), MANUAL)


if __name__ == "__main__":
    unittest.main()

"""Platform switching (nd_backend.py): detection, layout, transactional switch with rollback."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nd_backend as B  # noqa: E402


def make_env(env, kind="nvidia", python="313", torch_version=None, extra=()):
    """Имитация python_embeded: python.exe, pythonXYZ._pth, torch/version.py и dist-info."""
    env = Path(env)
    site = env / "Lib" / "site-packages"
    (site / "torch").mkdir(parents=True)
    (env / "python.exe").write_bytes(b"")
    (env / f"python{python}._pth").write_text("import site\n")
    cuda, hip = ("13.0", None) if kind == "nvidia" else (None, "7.1.1") if kind == "amd" else (None, None)
    version = torch_version or ("2.9.0+cu130" if kind == "nvidia" else "2.9.0+rocm7.1.1" if kind == "amd" else "2.9.0+cpu")
    (site / "torch" / "version.py").write_text(
        f"__version__ = '{version}'\ndebug = False\ncuda: Optional[str] = {cuda!r}\ngit_version = 'abc'\nhip: Optional[str] = {hip!r}\nxpu: Optional[str] = None\n".replace("'None'", "None"))
    for name, ver in (("torch", version), ("torchvision", "0.24.0"), ("torchaudio", "2.9.0"), *extra):
        (site / f"{name}-{ver}.dist-info").mkdir()
    return env


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        (self.root / "ComfyUI" / "custom_nodes").mkdir(parents=True)
        (self.root / "ComfyUI" / "models").mkdir()
        (self.root / "ComfyUI" / "models" / "keep.safetensors").write_text("model")

    def tearDown(self):
        self._td.cleanup()

    def prepared(self):
        make_env(B.active_dir(self.root), "nvidia", extra=[("sageattention", "2.2.0")])
        make_env(B.env_dir(self.root, "amd"), "amd", python="312")


class DetectionTests(Base):
    def test_detect_by_torch_version_file(self):
        for kind, expected in (("nvidia", "nvidia"), ("amd", "amd"), ("cpu", "cpu")):
            env = make_env(self.root / kind, kind)
            self.assertEqual(B.detect_backend(env), expected)

    def test_amd_wheel_without_rocm_tag_is_found_by_hip(self):
        env = make_env(self.root / "a", "amd", torch_version="2.8.0a0+gitfc14c65")
        self.assertEqual(B.detect_backend(env), "amd")

    def test_fallback_to_dist_info(self):
        env = self.root / "e"
        (env / "Lib" / "site-packages" / "torch-2.9.0+cu130.dist-info").mkdir(parents=True)
        self.assertEqual(B.detect_backend(env), "nvidia")
        env2 = self.root / "e2"
        (env2 / "Lib" / "site-packages" / "torch-2.9.0+rocm7.1.dist-info").mkdir(parents=True)
        self.assertEqual(B.detect_backend(env2), "amd")

    def test_no_torch(self):
        env = self.root / "x"
        env.mkdir()
        self.assertIsNone(B.detect_backend(env))
        self.assertEqual(B.torch_info(env), {})

    def test_python_version(self):
        self.assertEqual(B.python_version(make_env(self.root / "p", python="313")), "3.13")
        self.assertEqual(B.python_version(make_env(self.root / "q", python="312")), "3.12")
        (self.root / "empty").mkdir()
        self.assertIsNone(B.python_version(self.root / "empty"))

    def test_marker_roundtrip_keeps_extra_fields(self):
        env = make_env(self.root / "m", "amd")
        data = B.write_marker(env, "amd", nodes_hash="abc")
        self.assertEqual(data["backend"], "amd")
        self.assertEqual(data["python"], "3.13")
        again = B.write_marker(env, "amd")
        self.assertEqual(again["nodes_hash"], "abc")
        self.assertEqual(again["created"], data["created"])

    def test_describe(self):
        info = B.describe(make_env(self.root / "d", "nvidia"))
        self.assertEqual((info["backend"], info["python"], info["cuda"]), ("nvidia", "3.13", "13.0"))


class PackagesTests(Base):
    def test_incompatible_packages_only_for_non_nvidia(self):
        env = make_env(self.root / "n", "nvidia", extra=[("sageattention", "2.2.0"), ("flash_attn", "2.8"), ("nvidia_cudnn_cu12", "9.1"), ("numpy", "2.0")])
        self.assertEqual(B.incompatible_packages(env, "nvidia"), {})
        found = B.incompatible_packages(env, "amd")
        self.assertEqual(set(found), {"sageattention", "flash_attn", "nvidia_cudnn_cu12"})
        self.assertNotIn("torch", found)

    def test_constraints_pin_torch_stack(self):
        env = make_env(self.root / "c", "amd")
        text = B.torch_constraints(env)
        self.assertIn("torch==2.9.0+rocm7.1.1", text)
        self.assertIn("torchvision==0.24.0", text)
        self.assertIn("torchaudio==2.9.0", text)

    def test_nodes_hash_changes_with_nodes_and_requirements(self):
        h0 = B.nodes_hash(self.root)
        node = self.root / "ComfyUI" / "custom_nodes" / "ComfyUI-Foo"
        node.mkdir()
        h1 = B.nodes_hash(self.root)
        self.assertNotEqual(h0, h1)
        (node / "requirements.txt").write_text("einops\n")
        h2 = B.nodes_hash(self.root)
        self.assertNotEqual(h1, h2)
        (self.root / "ComfyUI" / "custom_nodes" / "Off.disabled").mkdir()
        (self.root / "ComfyUI" / "custom_nodes" / "__pycache__").mkdir()
        self.assertEqual(B.nodes_hash(self.root), h2)

    def test_dir_size(self):
        d = self.root / "s"
        d.mkdir()
        (d / "a").write_bytes(b"12345")
        (d / "b").write_bytes(b"123")
        self.assertEqual(B.dir_size(d), 8)


class GpuTests(unittest.TestCase):
    def test_classification(self):
        cases = {
            "NVIDIA GeForce RTX 4070 Ti SUPER": ("nvidia", None),
            "AMD Radeon RX 7900 XTX": ("amd", "supported"),
            "AMD Radeon RX 9070 XT": ("amd", "supported"),
            "AMD Radeon RX 7600": ("amd", "uncertain"),
            "AMD Radeon RX 6800": ("amd", "uncertain"),
            "AMD Radeon RX 580 Series": ("amd", "unsupported"),
            "AMD Radeon PRO W7900": ("amd", "supported"),
            "AMD Radeon AI PRO R9700": ("amd", "supported"),
            "AMD Radeon(TM) Graphics": ("amd", "uncertain"),
            "Intel(R) Arc(TM) A770": ("intel", None),
            "Microsoft Basic Display Adapter": ("unknown", None),
        }
        for name, expected in cases.items():
            self.assertEqual(B.classify_gpu(name), expected, name)


class SwitchTests(Base):
    def test_plan_requires_prepared_target(self):
        make_env(B.active_dir(self.root), "nvidia")
        with self.assertRaises(B.BackendError):
            B.plan_switch(self.root, "amd")

    def test_plan_rejects_same_unknown_and_missing_torch(self):
        self.prepared()
        with self.assertRaises(B.BackendError):
            B.plan_switch(self.root, "nvidia")
        with self.assertRaises(B.BackendError):
            B.plan_switch(self.root, "sparkle")
        empty = Path(self._td.name) / "other"
        (empty / "python_embeded").mkdir(parents=True)
        (empty / "python_embeded" / "python.exe").write_bytes(b"")
        with self.assertRaises(B.BackendError):
            B.plan_switch(empty, "amd")

    def test_plan_rejects_wrong_torch_in_target_slot(self):
        make_env(B.active_dir(self.root), "nvidia")
        make_env(B.env_dir(self.root, "amd"), "nvidia")
        with self.assertRaises(B.BackendError):
            B.plan_switch(self.root, "amd")

    def test_switch_there_and_back_leaves_comfyui_untouched(self):
        self.prepared()
        result = B.switch(self.root, "amd")
        self.assertEqual(result, {"from": "nvidia", "to": "amd"})
        self.assertEqual(B.current_backend(self.root), "amd")
        self.assertEqual(B.python_version(B.active_dir(self.root)), "3.12")
        self.assertEqual(set(B.list_envs(self.root)), {"nvidia"})
        self.assertIsNone(B.read_journal(self.root))
        self.assertEqual(B.read_marker(B.active_dir(self.root))["backend"], "amd")
        B.switch(self.root, "nvidia")
        self.assertEqual(B.current_backend(self.root), "nvidia")
        self.assertEqual(B.python_version(B.active_dir(self.root)), "3.13")
        self.assertEqual(set(B.list_envs(self.root)), {"amd"})
        self.assertEqual((self.root / "ComfyUI" / "models" / "keep.safetensors").read_text(), "model")
        self.assertIn("sageattention", B.installed_packages(B.active_dir(self.root)))

    def test_failed_verification_rolls_back(self):
        self.prepared()
        with self.assertRaises(B.BackendError) as cm:
            B.switch(self.root, "amd", verify=lambda env: (False, "import torch failed"))
        self.assertIn("import torch failed", str(cm.exception))
        self.assertEqual(B.current_backend(self.root), "nvidia")
        self.assertEqual(B.python_version(B.active_dir(self.root)), "3.13")
        self.assertEqual(set(B.list_envs(self.root)), {"amd"})
        self.assertIsNone(B.read_journal(self.root))

    def test_verify_receives_new_active_env(self):
        self.prepared()
        seen = []
        B.switch(self.root, "amd", verify=lambda env: (seen.append(B.env_backend(env)) or True, ""))
        self.assertEqual(seen, ["amd"])

    def test_locked_folder_on_second_step_is_rolled_back(self):
        self.prepared()
        real = B._move
        calls = []

        def flaky(src, dst):
            calls.append((src, dst))
            if len(calls) == 2:
                raise B.BackendError("locked")
            real(src, dst)

        with mock.patch.object(B, "_move", flaky):
            with self.assertRaises(B.BackendError):
                B.switch(self.root, "amd")
        self.assertEqual(B.current_backend(self.root), "nvidia")
        self.assertIsNone(B.read_journal(self.root))
        self.assertTrue((B.env_dir(self.root, "amd") / "python.exe").exists())

    def test_locked_folder_on_first_step_changes_nothing(self):
        self.prepared()
        with mock.patch.object(B, "_move", side_effect=B.BackendError("locked")):
            with self.assertRaises(B.BackendError):
                B.switch(self.root, "amd")
        self.assertEqual(B.current_backend(self.root), "nvidia")
        self.assertIsNone(B.read_journal(self.root))

    def test_recover_after_crash_between_steps(self):
        self.prepared()
        # имитируем обрыв: старое окружение уже убрано в хранилище, новое ещё не встало
        stash = B.env_dir(self.root, "nvidia")
        stash.parent.mkdir(parents=True)
        B.active_dir(self.root).rename(stash)
        B._write_journal(self.root, {"from": "nvidia", "to": "amd", "state": "stashed"})
        self.assertTrue(B.recover(self.root))
        self.assertEqual(B.current_backend(self.root), "nvidia")
        self.assertEqual(set(B.list_envs(self.root)), {"amd"})
        self.assertIsNone(B.read_journal(self.root))

    def test_recover_after_crash_after_both_moves(self):
        self.prepared()
        B.switch(self.root, "amd")
        B._write_journal(self.root, {"from": "nvidia", "to": "amd", "state": "done"})
        self.assertTrue(B.recover(self.root))
        self.assertEqual(B.current_backend(self.root), "nvidia")

    def test_recover_without_journal_does_nothing(self):
        self.prepared()
        self.assertFalse(B.recover(self.root))
        self.assertEqual(B.current_backend(self.root), "nvidia")

    def test_needs_dependency_sync_after_new_node(self):
        self.prepared()
        B.write_marker(B.env_dir(self.root, "amd"), "amd", nodes_hash=B.nodes_hash(self.root))
        self.assertFalse(B.needs_dependency_sync(self.root, "amd"))
        (self.root / "ComfyUI" / "custom_nodes" / "NewNode").mkdir()
        self.assertTrue(B.needs_dependency_sync(self.root, "amd"))


class ExternalSwitchTests(Base):
    """Переключение внешним скриптом: begin_switch → (скрипт переставляет папки и пишет результат) → finish_pending."""

    def simulate_helper(self, ok=True, text=""):
        """То, что делает .cmd: переставляет папки и пишет switch.result."""
        j = B.read_journal(self.root)
        stash = B.env_dir(self.root, j["from"])
        stash.parent.mkdir(parents=True, exist_ok=True)
        B.active_dir(self.root).rename(stash)
        B.env_dir(self.root, j["to"]).rename(B.active_dir(self.root))
        if not ok:
            B.active_dir(self.root).rename(B.env_dir(self.root, j["to"]))
            stash.rename(B.active_dir(self.root))
        B.result_path(self.root).write_text(("done\n" if ok else "failed\n") + text, encoding="utf-8")

    def test_successful_switch_is_confirmed_on_next_start(self):
        self.prepared()
        plan = B.begin_switch(self.root, "amd")
        self.assertEqual((plan["from"], plan["to"]), ("nvidia", "amd"))
        self.assertEqual(B.read_journal(self.root)["state"], "pending")
        self.assertEqual(B.read_marker(B.active_dir(self.root))["backend"], "nvidia")
        self.simulate_helper(ok=True)
        done = B.finish_pending(self.root)
        self.assertEqual(done["status"], "done")
        self.assertEqual(B.read_marker(B.active_dir(self.root))["backend"], "amd")
        self.assertIsNone(B.read_journal(self.root))
        self.assertFalse(B.result_path(self.root).exists())
        self.assertIsNone(B.finish_pending(self.root))

    def test_failed_switch_reports_message_and_keeps_old_environment(self):
        self.prepared()
        B.begin_switch(self.root, "amd")
        self.simulate_helper(ok=False, text="torch check failed")
        res = B.finish_pending(self.root)
        self.assertEqual(res["status"], "failed")
        self.assertIn("torch check failed", res["message"])
        self.assertEqual(B.current_backend(self.root), "nvidia")
        self.assertIsNone(B.read_journal(self.root))

    def test_done_result_with_wrong_environment_is_not_trusted(self):
        self.prepared()
        B.begin_switch(self.root, "amd")
        B.result_path(self.root).write_text("done\n", encoding="utf-8")  # папки не менялись
        res = B.finish_pending(self.root)
        self.assertEqual(res["status"], "failed")
        self.assertEqual(B.current_backend(self.root), "nvidia")

    def test_fresh_journal_without_result_is_busy_not_rolled_back(self):
        self.prepared()
        B.begin_switch(self.root, "amd")
        self.assertEqual(B.finish_pending(self.root)["status"], "busy")
        self.assertIsNotNone(B.read_journal(self.root))

    def test_stale_journal_is_recovered_from_observed_layout(self):
        self.prepared()
        B.begin_switch(self.root, "amd")
        j = B.read_journal(self.root)
        j["started"] = 0
        B._write_journal(self.root, j)
        # скрипт успел переставить папки и умер до проверки
        stash = B.env_dir(self.root, "nvidia")
        stash.parent.mkdir(parents=True, exist_ok=True)
        B.active_dir(self.root).rename(stash)
        B.env_dir(self.root, "amd").rename(B.active_dir(self.root))
        self.assertEqual(B.finish_pending(self.root)["status"], "recovered")
        self.assertEqual(B.current_backend(self.root), "nvidia")
        self.assertEqual(set(B.list_envs(self.root)), {"amd"})

    def test_helper_script_content(self):
        text = B.helper_script(r"D:\Моя сборка 100%", {"from": "nvidia", "to": "amd"}, 4321, r'"D:\Моя сборка 100%\ND_Launcher.bat"')
        self.assertIn('set "ROOT=D:\\Моя сборка 100%%"', text)
        self.assertIn('set "PID=4321"', text)
        self.assertIn('set "FROM=nvidia"', text)
        self.assertIn('start "" "D:\\Моя сборка 100%%\\ND_Launcher.bat"', text)
        self.assertIn("import torch", text)
        self.assertIn("\r\n", text)
        self.assertNotIn("\n\n", text.replace("\r\n", ""))
        for label in (":wait", ":go", ":mv", ":fail1", ":fail2", ":verify_failed", ":restart", ":timeout"):
            self.assertIn(label + "\r\n", text)

    def test_write_helper_is_utf8(self):
        path = B.write_helper(self.root, {"from": "nvidia", "to": "amd"}, 1, '"x.bat"')
        self.assertEqual(path.name, B.HELPER)
        self.assertIn("chcp 65001", path.read_bytes().decode("utf-8"))


class OptionsAndGpuTests(unittest.TestCase):
    def test_amd_replaces_sage_flash_and_auto(self):
        for before in (B.SAGE, B.FLASH, ""):
            opts, changes = B.adapt_options({"attention": before, "fast": True}, "amd")
            self.assertEqual(opts["attention"], B.PYTORCH_ATTENTION)
            self.assertTrue(opts["fast"])
            self.assertTrue(changes)

    def test_amd_keeps_explicit_split_attention(self):
        opts, _ = B.adapt_options({"attention": "--use-split-cross-attention"}, "amd")
        self.assertEqual(opts["attention"], "--use-split-cross-attention")

    def test_saved_options_win_and_input_is_not_mutated(self):
        original = {"attention": B.SAGE}
        opts, changes = B.adapt_options(original, "nvidia", saved={"attention": B.SAGE, "vram": "--highvram"})
        self.assertEqual(opts["vram"], "--highvram")
        self.assertEqual(changes, [])
        B.adapt_options(original, "amd")
        self.assertEqual(original, {"attention": B.SAGE})

    def test_nvidia_leaves_options_alone(self):
        opts, changes = B.adapt_options({"attention": B.SAGE}, "nvidia")
        self.assertEqual(opts["attention"], B.SAGE)
        self.assertEqual(changes, [])

    def test_gpu_assessment(self):
        names = ["NVIDIA GeForce RTX 4070 Ti SUPER", "AMD Radeon(TM) Graphics"]
        self.assertEqual(B.gpu_assessment(names, "nvidia"), {"found": True, "name": names[0], "support": None})
        self.assertEqual(B.gpu_assessment(names, "amd")["support"], "uncertain")
        better = names + ["AMD Radeon RX 7900 XTX"]
        self.assertEqual(B.gpu_assessment(better, "amd"), {"found": True, "name": "AMD Radeon RX 7900 XTX", "support": "supported"})
        self.assertEqual(B.gpu_assessment(["NVIDIA GeForce RTX 3060"], "amd"), {"found": False, "name": None, "support": None})
        self.assertEqual(B.gpu_assessment([], "amd")["found"], False)

    def test_detect_gpus_is_empty_off_windows(self):
        import os
        if os.name != "nt":
            self.assertEqual(B.detect_gpus(), [])


if __name__ == "__main__":
    unittest.main()

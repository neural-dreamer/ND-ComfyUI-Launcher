"""Platform environment preparation (nd_backend_install.py): 7-Zip lookup, extraction, dependency sync plan."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import nd_backend as B  # noqa: E402
import nd_backend_install as I  # noqa: E402
from test_backend import make_env  # noqa: E402

try:
    import py7zr
except ImportError:  # pragma: no cover
    py7zr = None


def make_archive(path, top="ComfyUI_windows_portable_amd", kind="amd", with_python=True):
    """Маленький .7z в структуре официальной сборки: <top>/ComfyUI/main.py и <top>/python_embeded/..."""
    with tempfile.TemporaryDirectory() as src:
        src = Path(src)
        (src / top / "ComfyUI").mkdir(parents=True)
        (src / top / "ComfyUI" / "main.py").write_text("print('hi')")
        if with_python:
            make_env(src / top / "python_embeded", kind)
        with py7zr.SevenZipFile(path, "w") as z:
            z.writeall(src, arcname="")


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()


class DiscoveryTests(Base):
    def test_find_7zip_in_program_files(self):
        exe = self.root / "Program Files" / "7-Zip" / "7z.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")
        found = I.find_7zip({"ProgramFiles": str(self.root / "Program Files")}, which=lambda _n: None)
        self.assertEqual(Path(found), exe)

    def test_find_7zip_on_path(self):
        exe = self.root / "bin" / "7z"
        exe.parent.mkdir()
        exe.write_bytes(b"")
        self.assertEqual(Path(I.find_7zip({}, which=lambda n: str(exe) if n == "7z" else None)), exe)

    def test_find_7zip_missing(self):
        self.assertIsNone(I.find_7zip({"ProgramFiles": str(self.root)}, which=lambda _n: None))

    def test_choose_method(self):
        c = I.choose_method
        self.assertEqual(c("auto", "7z", True), "7zip")
        self.assertEqual(c("auto", None, True), "py7zr")
        self.assertIsNone(c("auto", None, False))
        self.assertEqual(c("py7zr", "7z", True), "py7zr")
        self.assertIsNone(c("py7zr", "7z", False))
        self.assertEqual(c("7zip", "7z", False), "7zip")
        self.assertIsNone(c("7zip", None, True))

    def test_archive_urls(self):
        self.assertEqual(I.archive_url("amd"), "https://github.com/Comfy-Org/ComfyUI/releases/latest/download/ComfyUI_windows_portable_amd.7z")
        self.assertTrue(I.archive_url("nvidia").endswith("ComfyUI_windows_portable_nvidia.7z"))
        with self.assertRaises(I.InstallError):
            I.archive_url("sparkle")

    def test_py7zr_install_command(self):
        self.assertEqual(I.py7zr_install_command("py.exe")[-1], "py7zr")


@unittest.skipIf(py7zr is None, "py7zr is not installed")
class Py7zrExtractTests(Base):
    def test_extracts_only_python_embeded(self):
        archive = self.root / "a.7z"
        make_archive(archive)
        steps = []
        env = I.extract_environment(self.root, "amd", archive, "py7zr", python_exe=sys.executable, progress=steps.append)
        self.assertEqual(env, B.env_dir(self.root, "amd"))
        self.assertTrue((env / "python.exe").is_file())
        self.assertEqual(B.detect_backend(env), "amd")
        self.assertEqual(B.read_marker(env)["backend"], "amd")
        self.assertFalse((self.root / "ComfyUI").exists())
        self.assertFalse((B.store_dir(self.root) / "_extract").exists())
        self.assertEqual(steps[-1], 100)
        self.assertEqual(steps, sorted(steps))

    def test_wrong_platform_archive_is_rejected(self):
        archive = self.root / "a.7z"
        make_archive(archive, kind="nvidia")
        with self.assertRaises(I.InstallError) as cm:
            I.extract_environment(self.root, "amd", archive, "py7zr", python_exe=sys.executable)
        self.assertIn("другой платформы", str(cm.exception))
        self.assertFalse(B.env_dir(self.root, "amd").exists())

    def test_archive_without_python_is_rejected(self):
        archive = self.root / "a.7z"
        make_archive(archive, with_python=False)
        with self.assertRaises(I.InstallError):
            I.extract_environment(self.root, "amd", archive, "py7zr", python_exe=sys.executable)
        self.assertFalse((B.store_dir(self.root) / "_extract").exists())

    def test_existing_environment_is_not_overwritten(self):
        archive = self.root / "a.7z"
        make_archive(archive)
        make_env(B.env_dir(self.root, "amd"), "amd")
        with self.assertRaises(I.InstallError):
            I.extract_environment(self.root, "amd", archive, "py7zr", python_exe=sys.executable)

    def test_cancel_stops_extraction(self):
        archive = self.root / "a.7z"
        make_archive(archive)
        with self.assertRaises(I.Cancelled):
            I.extract_environment(self.root, "amd", archive, "py7zr", python_exe=sys.executable, cancel=lambda: True)
        self.assertFalse(B.env_dir(self.root, "amd").exists())
        self.assertFalse((B.store_dir(self.root) / "_extract").exists())

    def test_missing_archive(self):
        with self.assertRaises(I.InstallError):
            I.extract_environment(self.root, "amd", self.root / "none.7z", "py7zr", python_exe=sys.executable)

    def test_py7zr_available_detection(self):
        self.assertTrue(I.py7zr_available(sys.executable))
        self.assertFalse(I.py7zr_available(self.root / "no-python"))


@unittest.skipIf(os.name == "nt" or py7zr is None, "uses a POSIX shell stand-in for 7z.exe")
class SevenZipCliTests(Base):
    def fake_7z(self, exit_code=0):
        """Имитация 7z: x <архив> -o<папка> ... — раскладывает структуру официальной сборки и печатает проценты через \\r."""
        script = self.root / "fake7z.sh"
        top = "Top"
        script.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do case "$a" in -o*) out="${a#-o}";; esac; done\n'
            f'mkdir -p "$out/{top}/python_embeded/Lib/site-packages/torch" "$out/{top}/ComfyUI"\n'
            f'touch "$out/{top}/python_embeded/python.exe"\n'
            f'echo "python313._pth" > /dev/null; echo "import site" > "$out/{top}/python_embeded/python313._pth"\n'
            f"printf \"__version__ = '2.9.0+rocm7.1'\\nhip = '7.1'\\n\" > \"$out/{top}/python_embeded/Lib/site-packages/torch/version.py\"\n"
            "printf ' 10%%\\r 55%%\\r100%%\\n'\n"
            f"exit {exit_code}\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return str(script)

    def test_extract_via_7zip(self):
        archive = self.root / "a.7z"
        archive.write_bytes(b"x")
        steps, lines = [], []
        env = I.extract_environment(self.root, "amd", archive, "7zip", sevenzip=self.fake_7z(), progress=steps.append, log=lines.append)
        self.assertTrue((env / "python.exe").is_file())
        self.assertEqual(B.detect_backend(env), "amd")
        self.assertIn(55, steps)
        self.assertEqual(steps[-1], 100)

    def test_7zip_failure_is_reported(self):
        archive = self.root / "a.7z"
        archive.write_bytes(b"x")
        with self.assertRaises(I.InstallError) as cm:
            I.extract_environment(self.root, "amd", archive, "7zip", sevenzip=self.fake_7z(exit_code=2))
        self.assertIn("код 2", str(cm.exception))
        self.assertFalse(B.env_dir(self.root, "amd").exists())


class DownloadTests(Base):
    SCRIPT = "import sys,os;open(sys.argv[2],'wb').write(b'7z');print('[ND-DL] done')"

    def test_download_command_shape(self):
        cmd = I.download_command("py.exe", "SCRIPT", "http://x/a.7z", "D:/a.7z", 6)
        self.assertEqual(cmd, ["py.exe", "-s", "-c", "SCRIPT", "http://x/a.7z", "D:/a.7z", "6", ""])

    def test_download_archive_runs_script_and_skips_existing(self):
        lines = []
        dest = I.download_archive(self.root, "amd", sys.executable, self.SCRIPT, on_line=lines.append)
        self.assertEqual(dest, I.archive_path(self.root, "amd"))
        self.assertEqual(dest.read_bytes(), b"7z")
        self.assertIn("[ND-DL] done", lines)
        dest.write_bytes(b"already")
        again = I.download_archive(self.root, "amd", sys.executable, "import sys;sys.exit(9)")
        self.assertEqual(again.read_bytes(), b"already")

    def test_download_failure(self):
        with self.assertRaises(I.InstallError):
            I.download_archive(self.root, "amd", sys.executable, "import sys;sys.exit(6)")


class DependencyTests(Base):
    def prepare_build(self):
        (self.root / "ComfyUI" / "custom_nodes" / "NodeA").mkdir(parents=True)
        (self.root / "ComfyUI" / "custom_nodes" / "NodeA" / "requirements.txt").write_text("einops\n")
        (self.root / "ComfyUI" / "custom_nodes" / "NodeB").mkdir()
        (self.root / "ComfyUI" / "custom_nodes" / "Off.disabled").mkdir()
        (self.root / "ComfyUI" / "custom_nodes" / "Off.disabled" / "requirements.txt").write_text("x\n")
        (self.root / "ComfyUI" / "requirements.txt").write_text("numpy\n")

    def test_node_requirements_skip_disabled_and_empty(self):
        self.prepare_build()
        self.assertEqual([n for n, _ in I.node_requirements(self.root)], ["NodeA"])

    def test_sync_plan_orders_comfyui_first_and_pins_torch(self):
        self.prepare_build()
        plan = I.sync_plan(self.root, "py.exe", "c.txt")
        self.assertEqual([n for n, _ in plan], ["ComfyUI", "NodeA"])
        for _name, cmd in plan:
            self.assertEqual(cmd[:3], ["py.exe", "-m", "pip"])
            self.assertEqual(cmd[cmd.index("-c") + 1], "c.txt")

    def test_launcher_deps_command(self):
        cmd = I.launcher_deps_command("py.exe", "requirements.txt")
        self.assertEqual(cmd[-2:], ["-r", "requirements.txt"])

    def test_pyside_command(self):
        cmd = I.pyside_command("py.exe")
        self.assertEqual(cmd[:3], ["py.exe", "-m", "pip"])
        self.assertEqual(cmd[-1], "PySide6-Essentials>=6.7,<7")

    def test_write_constraints(self):
        env = make_env(self.root / "env", "amd")
        path = I.write_constraints(self.root, env, "amd")
        self.assertIn("torch==2.9.0+rocm7.1.1", path.read_text())

    def test_sync_dependencies_reports_failures_and_stores_hash(self):
        self.prepare_build()
        env = make_env(B.env_dir(self.root, "amd"), "amd")
        # «pip» подменяем скриптом на Python: падает на NodeA
        fake = self.root / "fakepy.py"
        fake.write_text("import sys\nsys.exit(1 if 'NodeA' in ' '.join(sys.argv) else 0)\n")
        orig = I.pip_base
        I.pip_base = lambda _py: [sys.executable, str(fake)]
        try:
            result = I.sync_dependencies(self.root, "amd", env, "ignored")
        finally:
            I.pip_base = orig
        self.assertEqual(result["ok"], ["ComfyUI"])
        self.assertEqual(result["failed"], [("NodeA", 1)])
        self.assertEqual(B.read_marker(env)["nodes_hash"], B.nodes_hash(self.root))

    def test_sync_cancel(self):
        self.prepare_build()
        env = make_env(B.env_dir(self.root, "amd"), "amd")
        with self.assertRaises(I.Cancelled):
            I.sync_dependencies(self.root, "amd", env, "ignored", cancel=lambda: True)


if __name__ == "__main__":
    unittest.main()

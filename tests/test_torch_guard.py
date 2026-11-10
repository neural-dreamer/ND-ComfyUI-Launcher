"""Защита PyTorch при «ComfyUI + зависимости»: если после батника torch остался без CUDA — возвращаем сборку с тем же CUDA."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nd_launcher as L  # noqa: E402


class Console:
    def __init__(self):
        self.lines = []

    def system(self, msg, error=False):
        self.lines.append((msg, error))


class Fake:
    """Минимальная подмена MainWindow для методов защиты."""
    python_exe = Path("python.exe")
    root = Path(".")

    def __init__(self, versions):
        self.versions = list(versions)
        self.console = Console()
        self.tasks = type("T", (), {"errors": 0})()

    def _torch_version(self):
        return self.versions.pop(0) if self.versions else None

    _torch_after_repair = L.MainWindow._torch_after_repair


class TorchGuardTests(unittest.TestCase):
    def test_cuda_kept_no_repair(self):
        f = Fake(["2.10.0+cu130"])
        self.assertIsNone(L.MainWindow._torch_guard(f, "2.9.1+cu130", "cu130"))

    def test_cpu_build_triggers_repair_with_same_cuda_index(self):
        f = Fake(["2.10.0+cpu"])
        steps = L.MainWindow._torch_guard(f, "2.9.1+cu130", "cu130")
        label, prog, args, cwd = steps[0]
        self.assertIn("--index-url", args)
        self.assertEqual(args[args.index("--index-url") + 1], "https://download.pytorch.org/whl/cu130")
        self.assertIn("--no-deps", args)
        self.assertTrue(f.console.lines[0][1])   # сообщение помечено как ошибка

    def test_plain_pypi_version_counts_as_no_cuda(self):
        f = Fake(["2.10.0"])
        self.assertIsNotNone(L.MainWindow._torch_guard(f, "2.9.1+cu130", "cu130"))

    def test_unknown_version_does_nothing(self):
        f = Fake([None])
        self.assertIsNone(L.MainWindow._torch_guard(f, "2.9.1+cu130", "cu130"))

    def test_still_cpu_after_repair_counts_error(self):
        f = Fake(["2.10.0+cpu"])
        L.MainWindow._torch_after_repair(f, "2.9.1+cu130", "cu130")
        self.assertEqual(f.tasks.errors, 1)


if __name__ == "__main__":
    unittest.main()

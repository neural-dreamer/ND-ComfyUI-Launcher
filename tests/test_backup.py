"""Restore points (nd_backup.py) on a fake portable build: python -m unittest discover -s tests."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nd_backup as B  # noqa: E402


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "ComfyUI_windows_portable"
        self.store = B.default_store(self.root)
        w = self.write
        w("ComfyUI/main.py", "v1")
        w("ComfyUI/comfyui_version.py", '__version__ = "0.3.60"')
        self.git("ComfyUI", "a" * 40, "https://github.com/comfyanonymous/ComfyUI")
        w("ComfyUI/models/checkpoints/m.safetensors", b"\0" * 64)
        w("ComfyUI/output/o.png", "o")
        w("ComfyUI/user/default/comfy.settings.json", "{}")
        w("ComfyUI/custom_nodes/NodeA/__init__.py", "A1")
        self.git("ComfyUI/custom_nodes/NodeA", "b" * 40, "https://github.com/x/NodeA")
        w("ComfyUI/custom_nodes/NodeB/__init__.py", "B1")
        w("ComfyUI/custom_nodes/NodeA/__pycache__/x.pyc", b"pyc")
        w("python_embeded/python.exe", os.urandom(512))
        w("python_embeded/Lib/site-packages/numpy-1.26.4.dist-info/METADATA", "numpy")
        w("python_embeded/Lib/site-packages/numpy/core.py", "np1")
        w("update/update_comfyui_stable.bat", "@echo off")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())

    def git(self, rel, commit, remote):
        self.write(f"{rel}/.git/HEAD", "ref: refs/heads/master\n")
        self.write(f"{rel}/.git/refs/heads/master", commit + "\n")
        self.write(f"{rel}/.git/config", f'[remote "origin"]\n\turl = {remote}\n')

    def break_build(self):
        w = self.write
        w("ComfyUI/main.py", "v2 broken")
        w("ComfyUI/comfyui_version.py", '__version__ = "0.3.61"')
        w("ComfyUI/.git/refs/heads/master", "c" * 40 + "\n")
        shutil.rmtree(self.root / "python_embeded/Lib/site-packages/numpy-1.26.4.dist-info")
        w("python_embeded/Lib/site-packages/numpy-2.1.0.dist-info/METADATA", "numpy2")
        w("python_embeded/Lib/site-packages/numpy/core.py", "np2")
        w("python_embeded/Lib/site-packages/numpy/_core/__init__.py", "new")
        w("python_embeded/Lib/site-packages/numpy/_core/__pycache__/__init__.cpython-312.pyc", b"pyc")
        w("ComfyUI/custom_nodes/NodeC/__init__.py", "C")
        os.rename(self.root / "ComfyUI/custom_nodes/NodeB", self.root / "ComfyUI/custom_nodes/NodeB.disabled")

    def test_excludes_models_outputs_and_caches(self):
        p = B.create(self.root, self.store)
        files = [r for a in B.load_point(self.store, p["id"])["files"].values() for r in a]
        self.assertFalse([r for r in files if "/models/" in r or "/output/" in r or r.endswith(".pyc")])
        self.assertIn("ComfyUI/custom_nodes/NodeB/__init__.py", files)
        self.assertIn("ComfyUI/.git/HEAD", files)

    def test_second_point_stores_only_changes(self):
        B.create(self.root, self.store)
        self.assertEqual(B.estimate(self.root, self.store)["new_bytes"], 0)
        self.break_build()
        p2 = B.create(self.root, self.store)
        self.assertLess(p2["stats"]["new_files"], p2["stats"]["files"])

    def test_restore_returns_build_to_point(self):
        p1 = B.create(self.root, self.store)
        self.break_build()
        p2 = B.create(self.root, self.store)
        d = B.diff(p1["summary"], p2["summary"])
        self.assertEqual(d["packages"]["changed"], [("numpy", "1.26.4", "2.1.0")])
        self.assertEqual(d["nodes"]["added"], ["NodeC"])
        self.assertEqual(d["nodes"]["changed"], [])
        r = B.restore(self.root, self.store, p1["id"])
        self.assertEqual(r["errors"], [])
        self.assertEqual((self.root / "ComfyUI/main.py").read_text(), "v1")
        self.assertFalse((self.root / "python_embeded/Lib/site-packages/numpy/_core").exists())
        self.assertFalse((self.root / "ComfyUI/custom_nodes/NodeC").exists())
        self.assertTrue((Path(r["trash"]) / "ComfyUI/custom_nodes/NodeC/__init__.py").is_file())
        self.assertTrue((self.root / "ComfyUI/models/checkpoints/m.safetensors").is_file())
        self.assertEqual(B.diff(p1["summary"], B.summary(self.root)), B.diff(p1["summary"], p1["summary"]))

    def test_partial_restore_and_keep(self):
        p1 = B.create(self.root, self.store, label="one")
        self.break_build()
        B.restore(self.root, self.store, p1["id"], areas=("python",))
        self.assertEqual(B.summary(self.root)["packages"]["numpy"], "1.26.4")
        self.assertEqual((self.root / "ComfyUI/main.py").read_text(), "v2 broken")
        for label in ("two", "three", "four"):
            B.create(self.root, self.store, label=label, keep=2)
        self.assertEqual([p["label"] for p in B.list_points(self.store, self.root)], ["four", "three"])
        with self.assertRaises(FileNotFoundError):
            B.load_point(self.store, p1["id"])


    def objects(self):
        return [f for f in (self.store / "objects").rglob("*") if f.is_file() and f.parent.name != "tmp"]

    def test_objects_are_compressed_except_compressed_formats(self):
        self.write("ComfyUI/web/logo.png", os.urandom(300))
        self.write("python_embeded/Lib/site-packages/big.py", "x = 1\n" * 20000)
        p = B.create(self.root, self.store)
        files = B.load_point(self.store, p["id"])["files"]
        sha_png = files["comfy"]["ComfyUI/web/logo.png"][0]
        sha_py = files["python"]["python_embeded/Lib/site-packages/big.py"][0]
        self.assertEqual(B._obj(self.store, sha_png).name, sha_png)
        self.assertEqual(B._obj(self.store, sha_py).name, sha_py + ".z")
        self.assertLess(p["stats"]["stored_bytes"], p["stats"]["new_bytes"])
        (self.root / "python_embeded/Lib/site-packages/big.py").write_text("broken")
        B.restore(self.root, self.store, p["id"])
        self.assertEqual((self.root / "python_embeded/Lib/site-packages/big.py").read_text(), "x = 1\n" * 20000)

    def test_old_uncompressed_store_is_recompressed(self):
        original = B._compressible
        B._compressible = lambda name: False   # как хранилище прежней версии
        try:
            B.create(self.root, self.store)
        finally:
            B._compressible = original
        self.assertFalse([f for f in self.objects() if f.suffix == ".z"])
        p2 = B.create(self.root, self.store)
        self.assertEqual(p2["stats"]["new_files"], 0)
        self.assertTrue([f for f in self.objects() if f.suffix == ".z"])
        self.assertEqual(len(self.objects()), len({f.name.removesuffix(".z") for f in self.objects()}))
        (self.root / "ComfyUI/main.py").write_text("changed")
        B.restore(self.root, self.store, p2["id"])
        self.assertEqual((self.root / "ComfyUI/main.py").read_text(), "v1")

    def test_damaged_object_is_not_restored(self):
        self.write("python_embeded/Lib/site-packages/big.py", "y = 2\n" * 20000)
        p = B.create(self.root, self.store)
        sha = B.load_point(self.store, p["id"])["files"]["python"]["python_embeded/Lib/site-packages/big.py"][0]
        obj = B._obj(self.store, sha)
        data = bytearray(obj.read_bytes())
        data[len(data) // 2] ^= 0xFF
        obj.write_bytes(bytes(data))
        (self.root / "python_embeded/Lib/site-packages/big.py").write_text("current")
        r = B.restore(self.root, self.store, p["id"])
        self.assertEqual(len(r["errors"]), 1)
        self.assertEqual((self.root / "python_embeded/Lib/site-packages/big.py").read_text(), "current")


    def test_point_size_on_disk(self):
        self.write("python_embeded/Lib/site-packages/big.py", "z = 3\n" * 20000)
        p = B.create(self.root, self.store)
        st = p["stats"]
        self.assertLess(st["disk_bytes"], st["bytes"])
        info = self.store / "points" / f"{p['id']}.info.json"
        data = __import__("json").loads(info.read_text(encoding="utf-8"))
        del data["stats"]["disk_bytes"]   # точка прежней тестовой версии
        info.write_text(__import__("json").dumps(data), encoding="utf-8")
        pts = B.fill_disk_sizes(self.store, B.list_points(self.store, self.root))
        self.assertEqual(pts[0]["stats"]["disk_bytes"], st["disk_bytes"])
        self.assertEqual(B.list_points(self.store, self.root)[0]["stats"]["disk_bytes"], st["disk_bytes"])


if __name__ == "__main__":
    unittest.main()

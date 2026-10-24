"""Exercise storage selection and cancellation without a Windows disk."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from test_browser_downloader import SCRIPT, BrowserDownloaderTests

TREE = ast.parse(SCRIPT)
PREPARE = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare_random_access')

class SparsePreparationTests(unittest.TestCase):
    def test_windows_preparation_never_extends_even_with_sparse_support(self):
        for allowed in (True, False):
            with self.subTest(allowed=allowed), tempfile.TemporaryDirectory() as td:
                target = str(Path(td)/'part')
                class Ioctl:
                    def __call__(self, *args):
                        self_size = os.path.getsize(target)
                        assert self_size == 0
                        assert args[1] == 0x900C4
                        return allowed
                ioctl = Ioctl()
                ns = dict(tmp=target, parts=None, size=46*1024**3, os=SimpleNamespace(name='nt'))
                exec(compile(ast.Module(body=[PREPARE], type_ignores=[]),'prepare','exec'), ns)
                with patch.dict('sys.modules', {'msvcrt':SimpleNamespace(get_osfhandle=lambda fd:fd)}), patch('ctypes.WinDLL',create=True,return_value=SimpleNamespace(DeviceIoControl=ioctl)):
                    self.assertEqual(ns['prepare_random_access'](), allowed)
                self.assertEqual(os.path.getsize(target), 0)

class StorageDownloadTests(BrowserDownloaderTests):
    def test_sequential_fallback_downloads_correct_bytes(self):
        fallback = SCRIPT.replace('if ranged and not prepare_random_access():', 'if ranged:')
        with patch('test_browser_downloader.SCRIPT', fallback):
            result = self.run_download('/file')
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(self.dest.read_bytes(), self.data)
        self.assertIn(b'using sequential download', result.stdout)

    def test_multiple_chunks_and_resume(self):
        import json
        chunk = 32768
        script = SCRIPT.replace('CHUNK = 32 * 1024 * 1024', 'CHUNK = 32768')
        part = Path(str(self.dest)+'.ndpart')
        part.write_bytes(self.data[:chunk])
        positions = {s: s+chunk if s==0 else s for s in range(0,len(self.data),chunk)}
        Path(str(part)+'.json').write_text(json.dumps(dict(size=len(self.data),chunk=chunk,parts=positions)))
        with patch('test_browser_downloader.SCRIPT',script):
            result = self.run_download('/file')
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(self.dest.read_bytes(),self.data)
        self.assertIn(b'Resuming:',result.stdout)

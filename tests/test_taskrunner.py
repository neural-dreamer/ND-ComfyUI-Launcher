"""TaskRunner: разбор прогресса pip/git, перезапуск и пропуск шага (настоящие дочерние процессы)."""
import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication  # noqa: E402
import nd_launcher as L  # noqa: E402

app = QCoreApplication.instance() or QCoreApplication([])


def pump(cond, timeout=15):
    t0 = time.time()
    while not cond() and time.time() - t0 < timeout:
        app.processEvents()
        time.sleep(0.02)
    return cond()


class TaskRunnerTests(unittest.TestCase):
    def setUp(self):
        self.r = L.TaskRunner()
        self.out = []
        self.r.output.connect(self.out.append)
        self.fin = []
        self.r.finished.connect(lambda t, e: self.fin.append(e))

    def test_filter_pip_progress(self):
        self.r.cur = dict(step=None, label="x", t0=time.time(), last=0, mode="pip", buf="", done=0, total=0, file="",
                          pct=None, phase="", git_speed=0, git_size=0, samples=[], retries=0)
        self.r.busy = True
        out = self.r._filter("  Downloading foo-1.whl (73.2 MB)\nProgress 100 of 1000\nProgress 400 of 1000\nok\n")
        self.assertNotIn("Progress", out)
        self.assertIn("Downloading foo-1.whl", out)
        a = self.r.activity()
        self.assertEqual((a["done"], a["total"], a["file"]), (400, 1000, "foo-1.whl"))

    def test_filter_git_and_retries(self):
        self.r.cur = dict(step=None, label="x", t0=time.time(), last=0, mode="git", buf="", done=0, total=0, file="",
                          pct=None, phase="", git_speed=0, git_size=0, samples=[], retries=0)
        self.r.busy = True
        out = self.r._filter("Cloning into 'a'...\rReceiving objects:  45% (9/20), 12.30 MiB | 1.20 MiB/s\r")
        self.assertIn("Cloning into", out)
        self.assertNotIn("Receiving", out)
        a = self.r.activity()
        self.assertEqual(a["pct"], 45)
        self.assertAlmostEqual(a["git_size"], 12.3 * 1024 ** 2, delta=1000)
        self.assertAlmostEqual(a["git_speed"], 1.2 * 1024 ** 2, delta=1000)
        self.r._filter("Resolving deltas: 100% (5/5), done.\r")
        self.assertEqual(self.r.activity()["phase"], "Resolving deltas")
        self.assertAlmostEqual(self.r.activity()["git_size"], 12.3 * 1024 ** 2, delta=1000)   # размер не теряется
        self.r.cur["mode"] = "pip"
        before = self.r.cur["last"]
        self.r._filter("WARNING: Retrying (Retry(total=4)) after connection broken\n")
        self.assertEqual(self.r.cur["retries"], 1)
        self.assertEqual(self.r.cur["last"], before)   # повтор — не прогресс

    def test_restart_reruns_step(self):
        marker = Path(os.environ.get("TMPDIR", "/tmp")) / f"nd_tr_{os.getpid()}"
        marker.unlink(missing_ok=True)
        code = ("import os,sys,time\nm=sys.argv[1]\n"
                "if os.path.exists(m):\n    print('second'); sys.exit(0)\n"
                "open(m,'w').close(); print('first', flush=True); time.sleep(60)\n")
        self.r.run("t", [("slow", sys.executable, ["-c", code, str(marker)], ".")])
        self.assertTrue(pump(lambda: any("first" in o for o in self.out)))
        self.r.restart_step()
        self.assertTrue(pump(lambda: bool(self.fin)))
        self.assertEqual(self.fin[-1], 0)
        self.assertTrue(any("second" in o for o in self.out))
        marker.unlink(missing_ok=True)

    def test_skip_continues_and_counts_error(self):
        steps = [("slow", sys.executable, ["-c", "import time;print('go',flush=True);time.sleep(60)"], "."),
                 ("quick", sys.executable, ["-c", "print('after')"], ".")]
        self.r.run("t", steps)
        self.assertTrue(pump(lambda: any("go" in o for o in self.out)))
        self.r.skip_step()
        self.assertTrue(pump(lambda: bool(self.fin)))
        self.assertEqual(self.fin[-1], 1)
        self.assertTrue(any("after" in o for o in self.out))

    def test_kill_cancels_all(self):
        steps = [("slow", sys.executable, ["-c", "import time;print('go',flush=True);time.sleep(60)"], "."),
                 ("quick", sys.executable, ["-c", "print('after')"], ".")]
        self.r.run("t", steps)
        self.assertTrue(pump(lambda: any("go" in o for o in self.out)))
        self.r.kill()
        self.assertTrue(pump(lambda: bool(self.fin)))
        self.assertFalse(any("after" in o for o in self.out))


if __name__ == "__main__":
    unittest.main()

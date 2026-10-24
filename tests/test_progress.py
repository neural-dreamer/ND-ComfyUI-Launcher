"""Regression coverage for slow steps, fragmented streams and download-row metrics."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'nd_launcher.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))


def logic():
    names = {'feed', '_on_progress', '_clear_generation_progress', '_on_line',
             '_on_dl_output', '_update_dl_metrics', 'fmt_size'}
    nodes = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    for cls in TREE.body:
        if isinstance(cls, ast.ClassDef) and cls.name in ('Console', 'MainWindow'):
            nodes += [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = dict(re=re, tr=lambda s,*args:s.format(*args),
              ANSI_RE=re.compile(r'\x1b\[[0-9;]*[A-Za-z]'), PROGRESS_RE=re.compile(r'(\d{1,3})%\|'))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), ns)
    return ns


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.ns = logic()

    def console(self):
        return SimpleNamespace(_buf={}, progress=Mock(), append_line=Mock(), line_received=Mock())

    def test_fragmented_tqdm(self):
        c = self.console()
        self.ns['feed'](c, '\r 2', 'comfy')
        self.ns['feed'](c, '5%|## | 1/4 [00:10]', 'comfy')
        self.assertEqual(c.progress.emit.call_args.args[0], 25)

    def test_trailing_carriage_return(self):
        c = self.console()
        self.ns['feed'](c, '50%|###| 2/4\r', 'comfy')
        self.assertEqual(c.progress.emit.call_args.args[0], 50)

    def test_downloads_and_tasks_do_not_replace_generation(self):
        c = self.console()
        for source in ('dl', 'task'):
            self.ns['feed'](c, '\r99%|###| stuff\n100%|###| done', source)
        c.progress.emit.assert_not_called()

    def test_slow_step_does_not_arm_hide_timer(self):
        w = SimpleNamespace(_progress_hide=Mock(), pbar=Mock(), lbl_progress=Mock())
        for pct in (10, 100):
            self.ns['_on_progress'](w, pct, 'step')
        w._progress_hide.start.assert_not_called()
        self.assertEqual(w._generation_progress, (100, 'step'))
        self.assertEqual(w._progress_hide.stop.call_count, 2)

    def test_prompt_completion_arms_hide(self):
        w = SimpleNamespace(_progress_hide=Mock(), _clear_generation_progress=Mock())
        self.ns['_on_line'](w, 'Prompt executed in 200.0 seconds', 'comfy')
        w._progress_hide.start.assert_called_once_with(1500)

    def test_new_prompt_clears_old_progress(self):
        w = SimpleNamespace(_progress_hide=Mock(), _clear_generation_progress=Mock())
        self.ns['_on_line'](w, 'got prompt', 'comfy')
        w._clear_generation_progress.assert_called_once()

    def test_clear_progress(self):
        w = SimpleNamespace(_progress_hide=Mock(), pbar=Mock(), lbl_progress=Mock(), _generation_progress=(10,'a'))
        self.ns['_clear_generation_progress'](w)
        self.assertIsNone(w._generation_progress)
        w.pbar.hide.assert_called_once()

    def download(self):
        q = dict(name='model.safetensors', via='direct', status='work', size=1024**3, _item=Mock())
        w = SimpleNamespace(console=Mock(), dl_bar=Mock(), lbl_dl=Mock(), dl_current=q)
        w._update_dl_metrics = lambda row:self.ns['_update_dl_metrics'](w, row)
        return w, q

    def test_download_fragmentation(self):
        w, q = self.download()
        self.ns['_on_dl_output'](w, '\r 50%|##########          | 512.0 MB/1.0 GB [12.')
        self.assertNotIn('progress_text', q)
        self.ns['_on_dl_output'](w, '5 MB/s]')
        self.assertEqual(q['progress_text'], '512.0 MB / 1.0 GB')
        self.assertEqual(q['speed_text'], '12.5 MB/с')
        q['_item'].setText.assert_any_call(3, '512.0 MB / 1.0 GB')
        w.lbl_dl.setText.assert_called_with('model.safetensors')

    def test_latest_download_record(self):
        w,q = self.download()
        self.ns['_on_dl_output'](w, '\r 1%| | 1 MB/100 MB [0 B/s]\r 2%| | 2 MB/100 MB [1 MB/s]')
        self.assertEqual(q['progress_text'], '2 MB / 100 MB')
        w.dl_bar.setValue.assert_called_with(2)

    def test_unknown_total(self):
        w,q = self.download()
        self.ns['_on_dl_output'](w, '\r 0%| | 8 MB/? [1 MB/s]')
        self.assertEqual(q['progress_text'], '8 MB / ?')

    def test_paused_keeps_bytes_and_hides_speed(self):
        w,q = self.download()
        q.update(status='paused', progress_text='512 MB / 1 GB', speed_text='12 MB/s')
        self.ns['_update_dl_metrics'](w,q)
        q['_item'].setText.assert_any_call(3,'512 MB / 1 GB')
        q['_item'].setText.assert_any_call(4,'—')

    def test_cli_does_not_use_direct_parser(self):
        w,q = self.download()
        q['via'] = 'cli'
        self.ns['_on_dl_output'](w, '\r 50%| | 1 MB/2 MB [1 MB/s]')
        self.assertNotIn('progress_text', q)


if __name__ == '__main__':
    unittest.main()

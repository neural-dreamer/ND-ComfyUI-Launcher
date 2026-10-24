"""Update logic tests without Qt or a Windows installation: python -m unittest discover -s tests."""
import ast
import base64
import html
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'nd_launcher.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))


def load_logic():
    names = {'launcher_version_key', 'check_launcher_update', 'HttpError'}
    nodes = [n for n in TREE.body if getattr(n, 'name', '') in names]
    cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
    nodes += [n for n in cls.body if getattr(n, 'name', '') in
              {'update_comfy', '_render_launcher_update', '_on_bridge',
               '_check_launcher_update', '_on_launcher_updates_toggled'}]
    ns = dict(re=re, json=json, base64=base64, html=html, os=os,
              VERSION='1.1.3', REPO_URL='https://github.com/neural-dreamer/ND-ComfyUI-Launcher',
              APP_TITLE='test', tr=lambda text, *args: text.format(*args), C={'CYAN': '#00e5ff'},
              QMessageBox=SimpleNamespace(warning=Mock()))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), ns)
    return ns


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_logic()

    def check(self, release='v1.1.3', source='1.1.3', error=None):
        def get(url, timeout):
            self.assertEqual(timeout, 10)
            if url.endswith('/releases/latest'):
                if error:
                    raise error
                result = {'tag_name': release}
            else:
                result = {'encoding': 'base64', 'content': base64.b64encode(
                    f'VERSION = "{source}"\n'.encode()).decode()}
            return json.dumps(result).encode(), {}
        self.ns['http_get'] = get
        return self.ns['check_launcher_update']()

    def test_equal(self):
        self.assertIsNone(self.check())

    def test_older(self):
        self.assertIsNone(self.check('v1.1.2', '1.1.2'))

    def test_numeric_order(self):
        self.assertEqual(self.check('v1.1.10')['version'], '1.1.10')

    def test_release_link(self):
        self.assertTrue(self.check('v1.2.0')['url'].endswith('/releases/latest'))

    def test_source_without_release(self):
        result = self.check(source='1.2.0', error=self.ns['HttpError'](404))
        self.assertEqual(result['url'], self.ns['REPO_URL'])

    def test_prerelease_ignored(self):
        self.assertIsNone(self.check('v1.2.0-rc1'))

    def test_source_newer_than_release(self):
        self.assertEqual(self.check('v1.2.0', '1.3.0')['version'], '1.3.0')

    def test_api_failure(self):
        with self.assertRaises(self.ns['HttpError']):
            self.check(error=self.ns['HttpError'](403))

    def test_bad_source(self):
        with self.assertRaises(ValueError):
            self.check(source='garbage')

    def test_update_buttons(self):
        with tempfile.TemporaryDirectory(prefix='build with spaces ') as folder:
            root = Path(folder)
            upd = root / 'update'
            upd.mkdir()
            for deps, script in [(False, 'update_comfyui_stable.bat'),
                                 (True, 'update_comfyui_and_python_dependencies.bat')]:
                (upd / script).touch()
                window = SimpleNamespace(root=root, _ensure_idle=lambda: True,
                                         tasks=Mock(), replace_example_image=Mock(), _post_update_steps=lambda kind: [])
                self.ns['update_comfy'](window, deps)
                steps = window.tasks.run.call_args.args[1]
                self.assertEqual(steps[0][2], ['/d', '/c', f'call {script} nopause <nul'])
                self.assertEqual(steps[0][3], upd)
                batches = [step for step in steps if isinstance(step, tuple)]
                self.assertEqual(len(batches), 2 if deps else 1)
                self.assertEqual(batches[-1][2], ['/d', '/c', 'call update_comfyui_stable.bat nopause <nul'])

    def test_dependencies_require_stable_batch_before_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'update').mkdir()
            (root/'update'/'update_comfyui_and_python_dependencies.bat').touch()
            window=SimpleNamespace(root=root,_ensure_idle=lambda:True,tasks=Mock())
            self.ns['update_comfy'](window,True)
            window.tasks.run.assert_not_called()
            self.ns['QMessageBox'].warning.assert_called_once()

    def test_missing_script_does_not_update(self):
        with tempfile.TemporaryDirectory() as folder:
            window = SimpleNamespace(root=Path(folder), _ensure_idle=lambda: True, tasks=Mock())
            self.ns['update_comfy'](window, False)
            window.tasks.run.assert_not_called()
            self.ns['QMessageBox'].warning.assert_called_once()

    def test_busy_does_not_update(self):
        window = SimpleNamespace(_ensure_idle=lambda: False, tasks=Mock())
        self.ns['update_comfy'](window, True)
        window.tasks.run.assert_not_called()

    def test_notification_survives_render(self):
        window = SimpleNamespace(cfg={}, _launcher_update={'version': '1.2.0', 'url': self.ns['REPO_URL']},
                                 lbl_launcher_update=Mock())
        self.ns['_render_launcher_update'](window)
        window.lbl_launcher_update.setVisible.assert_called_with(True)
        self.assertIn('1.2.0', window.lbl_launcher_update.setText.call_args.args[0])
        window._launcher_update = None
        self.ns['_render_launcher_update'](window)
        window.lbl_launcher_update.setVisible.assert_called_with(False)

    def test_network_error_only_logs(self):
        window = SimpleNamespace(cfg={}, console=Mock(), _launcher_update=None, _render_launcher_update=Mock())
        self.ns['_on_bridge'](window, 'launcher_update', None, OSError('offline'))
        window.console.system.assert_called_once()
        self.ns['QMessageBox'].warning.assert_not_called()

    def test_check_disabled_skips_network(self):
        self.ns['run_in_thread'] = Mock()
        window = SimpleNamespace(cfg={'check_launcher_updates': False}, _launcher_update_pending=False)
        self.ns['_check_launcher_update'](window)
        self.ns['run_in_thread'].assert_not_called()

    def test_check_enabled_by_default_and_no_duplicate(self):
        self.ns['run_in_thread'] = Mock()
        window = SimpleNamespace(cfg={}, _launcher_update_pending=False, _bridge=Mock())
        self.ns['_check_launcher_update'](window)
        self.ns['_check_launcher_update'](window)
        self.ns['run_in_thread'].assert_called_once()

    def test_disabled_drops_inflight_result(self):
        window = SimpleNamespace(cfg={'check_launcher_updates': False}, _launcher_update_pending=True,
                                 _launcher_update=None, console=Mock(), _render_launcher_update=Mock())
        self.ns['_on_bridge'](window, 'launcher_update', {'version': '9.0.0'}, None)
        self.assertIsNone(window._launcher_update)
        self.assertFalse(window._launcher_update_pending)
        window._render_launcher_update.assert_not_called()

    def test_toggle_saves_hides_and_rechecks(self):
        window = SimpleNamespace(cfg={}, _launcher_update={'version': '9.0.0'},
                                 _render_launcher_update=Mock(), _check_launcher_update=Mock())
        window._set_cfg = Mock(side_effect=lambda k, v: window.cfg.update({k: v}))
        self.ns['_on_launcher_updates_toggled'](window, False)
        window._set_cfg.assert_called_with('check_launcher_updates', False)
        self.assertIsNone(window._launcher_update)
        window._check_launcher_update.assert_not_called()
        self.ns['_on_launcher_updates_toggled'](window, True)
        window._set_cfg.assert_called_with('check_launcher_updates', True)
        window._check_launcher_update.assert_called_once()

    def test_notification_is_link(self):
        window = SimpleNamespace(cfg={}, _launcher_update={'version': '1.2.0', 'url': self.ns['REPO_URL']},
                                 lbl_launcher_update=Mock())
        self.ns['_render_launcher_update'](window)
        text = window.lbl_launcher_update.setText.call_args.args[0]
        self.assertIn('<a href="' + self.ns['REPO_URL'] + '"', text)
        self.assertIn('text-decoration:underline', text)


if __name__ == '__main__':
    unittest.main()

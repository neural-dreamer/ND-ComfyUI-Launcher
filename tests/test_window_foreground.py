import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

TREE=ast.parse((Path(__file__).parents[1]/'nd_launcher.py').read_text())
FN=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='raise_window_windows')
NS={}
exec(compile(ast.Module(body=[FN],type_ignores=[]),'foreground','exec'),NS)

class ForegroundTests(unittest.TestCase):
    def api(self, iconic=False, topmost=False, position=True):
        return SimpleNamespace(IsWindow=Mock(return_value=True),IsIconic=Mock(return_value=iconic),
            ShowWindow=Mock(),SetForegroundWindow=Mock(return_value=False),
            GetWindowLongW=Mock(return_value=8 if topmost else 0),SetWindowPos=Mock(return_value=position))

    def call(self, api, force):
        with patch('ctypes.WinDLL',create=True,return_value=api):
            return NS['raise_window_windows'](0x123456789,force)

    def test_denied_activation_still_lifts_then_unpins(self):
        api=self.api();release=self.call(api,True)
        api.ShowWindow.assert_not_called()
        self.assertEqual(api.SetWindowPos.call_args.args[:2],(0x123456789,-1))
        release()
        self.assertEqual(api.SetWindowPos.call_args.args[:2],(0x123456789,-2))
        self.assertEqual(api.SetWindowPos.call_count,2)

    def test_minimized_is_restored(self):
        api=self.api(iconic=True);self.call(api,False)
        api.ShowWindow.assert_called_once_with(0x123456789,9)
        api.SetWindowPos.assert_not_called()

    def test_existing_topmost_not_removed(self):
        api=self.api(topmost=True);self.assertIsNone(self.call(api,True))
        api.SetWindowPos.assert_not_called()

    def test_failed_lift_does_not_schedule_cleanup(self):
        api=self.api(position=False);self.assertIsNone(self.call(api,True))

    def test_cleanup_ignores_destroyed_window(self):
        api=self.api();release=self.call(api,True)
        api.IsWindow.return_value=False;release()
        self.assertEqual(api.SetWindowPos.call_count,1)

    def test_regular_activation_does_not_force_z_order(self):
        api=self.api();self.assertIsNone(self.call(api,False))
        api.SetForegroundWindow.assert_called_once()
        api.SetWindowPos.assert_not_called()

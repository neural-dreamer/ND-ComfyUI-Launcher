import ast
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nd_browser import BrowserServer, validate_transfer


def payload(**extra):
    value=dict(request_id='a'*32,url='https://civitai.red/api/download/models/123',
               final_url='https://cdn.example.com/model?signature=xyz',referrer='https://civitai.red/models/123',
               filename=r'C:\Models\example.safetensors',total_bytes=1024)
    return dict(value,**extra)


class BrowserValidationTests(unittest.TestCase):
    def test_valid_windows_path_and_signed_url(self):
        self.assertEqual(validate_transfer(payload())['filename'],r'C:\Models\example.safetensors')

    def test_cdn_url_with_red_referrer(self):
        self.assertTrue(validate_transfer(payload(url='https://cdn.example.com/model')))

    def test_unrelated_site(self):
        with self.assertRaises(ValueError):validate_transfer(payload(url='https://example.com/a',referrer='https://civitai.red.evil.com'))

    def test_rejects_local_url_and_credentials(self):
        for url in ['http://example.com/a','https://127.0.0.1/a','https://localhost/a','https://u:p@example.com/a','https://example.com:8000/a']:
            with self.subTest(url=url), self.assertRaises(ValueError):validate_transfer(payload(final_url=url))

    def test_rejects_devices_traversal_ads_and_executables(self):
        for path in [r'\\server\a.safetensors',r'C:\a\..\b.safetensors',r'C:\NUL.safetensors',r'C:\a.safetensors:ads',r'C:\evil.exe','relative.safetensors']:
            with self.subTest(path=path),self.assertRaises(ValueError):validate_transfer(payload(filename=path))


class HTTPBridgeTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def dispatch(request):
            self.calls.append(request)
            request['result']={'ok':True}
            request['done'].set()
        self.server=BrowserServer('x'*40,dispatch,port=0)
        self.url='http://127.0.0.1:'+str(self.server.httpd.server_address[1])

    def tearDown(self):self.server.close()

    def request(self,path,data=None,token='x'*40,origin=None):
        headers={'X-ND-Token':token,'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.url+path,json.dumps(data or {}).encode(),headers)
        return urllib.request.urlopen(req,timeout=3)

    def test_authenticated_prepare(self):
        with self.request('/prepare',payload(),origin='chrome-extension://'+'a'*32) as r:
            self.assertTrue(json.load(r)['ok'])
        self.assertEqual(self.calls[0]['action'],'prepare')

    def test_rejects_wrong_key(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/ping',token='wrong')
        self.assertEqual(cm.exception.code,403)
        self.assertFalse(self.calls)

    def test_rejects_web_origin(self):
        with self.assertRaises(urllib.error.HTTPError):self.request('/ping',origin='https://civitai.red')
        self.assertFalse(self.calls)

    def test_bad_payload_never_reaches_gui(self):
        with self.assertRaises(urllib.error.HTTPError):self.request('/prepare',payload(filename='x.exe'))
        self.assertFalse(self.calls)


class HandoffQueueTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse((ROOT/'nd_launcher.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MainWindow')
        method=next(n for n in cls.body if getattr(n,'name','')=='_on_browser_request')
        self.ns=dict(time=time,sys=SimpleNamespace(platform='win32'),os=__import__('os'),Path=Path,VERSION='1.1.3',tr=lambda s,*a:s.format(*a))
        exec(compile(ast.Module(body=[method],type_ignores=[]),'method','exec'),self.ns)
        self.w=SimpleNamespace(cfg={'browser_capture':True},_browser_server=True,root=Path('.'),python_exe=Mock(),
            _browser_reservations={},_browser_committed={},dl_queue=[],dl_paused=False,dl_tasks=Mock(),
            _check_browser_destination=Mock(return_value=Path('/tmp/example.safetensors')),
            go=Mock(),bring_to_front=Mock(),_dl_steps=Mock(return_value=['steps']),_render_dl_queue=Mock(),update_controls=Mock(),console=Mock())
        self.w.python_exe.is_file.return_value=True
        self.w.dl_tasks.busy=False

    def call(self,action,data):
        e=dict(action=action,data=data,done=threading.Event(),deadline=time.monotonic()+8)
        self.ns['_on_browser_request'](self.w,e)
        self.assertTrue(e['done'].is_set())
        return e['result']

    def test_prepare_never_starts_and_commit_is_idempotent(self):
        p=payload()
        self.assertTrue(self.call('prepare',p)['ok'])
        self.w.dl_tasks.run.assert_not_called()
        self.assertTrue(self.call('commit',{'request_id':p['request_id']})['ok'])
        self.assertTrue(self.call('commit',{'request_id':p['request_id']})['ok'])
        self.assertTrue(self.call('prepare',p)['accepted'])
        self.assertEqual(len(self.w.dl_queue),1)
        self.w.dl_tasks.run.assert_called_once()
        self.w.go.assert_called_once_with("models")
        self.w.bring_to_front.assert_called_once_with(browser_handoff=True)

    def test_focus_can_be_disabled(self):
        self.w.cfg["browser_show_downloads"] = False
        self.call("prepare", payload())
        self.assertTrue(self.call("commit", {"request_id": "a"*32})["ok"])
        self.w.go.assert_not_called()
        self.w.bring_to_front.assert_not_called()

    def test_disabled_does_not_accept(self):
        self.w.cfg['browser_capture']=False
        self.assertFalse(self.call('prepare',payload())['ok'])
        self.assertFalse(self.w.dl_queue)

    def test_changed_payload_same_id_rejected(self):
        self.call('prepare',payload())
        self.assertFalse(self.call('prepare',payload(total_bytes=99))['ok'])

    def test_commit_without_prepare_rejected(self):
        self.assertFalse(self.call('commit',{'request_id':'missing'})['ok'])

    def test_queue_paused_stays_paused(self):
        self.w.dl_paused=True
        self.call('prepare',payload())
        self.assertTrue(self.call('commit',{'request_id':'a'*32})['ok'])
        self.w.dl_tasks.run.assert_not_called()
        self.assertEqual(len(self.w.dl_queue),1)

if __name__=='__main__':unittest.main()

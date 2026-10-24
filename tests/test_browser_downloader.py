import ast
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

TREE=ast.parse((Path(__file__).resolve().parents[1]/'nd_launcher.py').read_text())
SCRIPT=next(n.value.value for n in TREE.body if isinstance(n,ast.Assign) and any(getattr(t,'id','')=='FAST_DL_SCRIPT' for t in n.targets))

class BrowserDownloaderTests(unittest.TestCase):
    def setUp(self):
        self.data=b'test model bytes\0'*10000
        self.seen=[]
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                owner.seen.append((self.path,self.headers.get('Authorization')))
                if self.path=='/expired':self.send_error(403);return
                if self.path=='/api':
                    self.send_response(302)
                    self.send_header('Location',f'http://localhost:{self.server.server_address[1]}/file')
                    self.end_headers();return
                if self.path=='/html':
                    self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
                    self.wfile.write(b'<html>login</html>');return
                start,end=0,len(owner.data)-1
                rng=self.headers.get('Range')
                if rng:
                    a,b=rng[6:].split('-');start=int(a);end=min(int(b),end)
                self.send_response(206 if rng else 200)
                self.send_header('Content-Type','application/octet-stream')
                self.send_header('Content-Length',str(end-start+1))
                if rng:self.send_header('Content-Range',f'bytes {start}-{end}/{len(owner.data)}')
                self.end_headers()
                try:self.wfile.write(owner.data[start:end+1])
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.base=f'http://127.0.0.1:{self.server.server_address[1]}'
        self.tmp=tempfile.TemporaryDirectory()
        self.dest=Path(self.tmp.name)/'model.safetensors'

    def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()

    def run_download(self,path,extra=None):
        env=dict(os.environ,ND_DL_NO_OVERWRITE='1',ND_DL_TOKEN='',ND_DL_REFRESH_URL='',ND_DL_REFRESH_TOKEN='',ND_DL_FALLBACK_URL='')
        env.update(extra or {})
        return subprocess.run([sys.executable,'-c',SCRIPT,self.base+path,str(self.dest),'2',''],env=env,capture_output=True,timeout=15)

    def test_binary_download(self):
        result=self.run_download('/file')
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(self.dest.read_bytes(),self.data)

    def test_refresh_expired_link_does_not_leak_token_to_redirect_host(self):
        result=self.run_download('/expired',{'ND_DL_REFRESH_URL':self.base+'/api','ND_DL_REFRESH_TOKEN':'secret'})
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(self.dest.read_bytes(),self.data)
        self.assertIn(('/api','Bearer secret'),self.seen)
        self.assertTrue(all(auth is None for path,auth in self.seen if path=='/file'))

    def test_signed_browser_link_fallback_preserves_access(self):
        result=self.run_download("/expired", {"ND_DL_FALLBACK_URL":self.base+"/file"})
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(self.dest.read_bytes(),self.data)

    def test_existing_file_preserved(self):
        self.dest.write_bytes(b'existing')
        self.assertEqual(self.run_download('/file').returncode,10)
        self.assertEqual(self.dest.read_bytes(),b'existing')
        self.assertFalse(self.seen)

    def test_login_page_not_saved_as_model(self):
        self.assertEqual(self.run_download('/html').returncode,3)
        self.assertFalse(self.dest.exists())

if __name__=='__main__':unittest.main()

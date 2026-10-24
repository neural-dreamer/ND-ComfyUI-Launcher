"""Authenticated loopback bridge for the optional Chrome download extension."""
import hmac
import ipaddress
import json
import ntpath
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PORT = 17863
MAX_BODY = 65536
MODEL_SUFFIXES = {'.safetensors', '.ckpt', '.pt', '.pth', '.bin', '.gguf', '.zip'}


def red_url(value):
    try:
        u = urlsplit(value)
        return u.scheme == 'https' and u.hostname in ('civitai.red', 'www.civitai.red', 'civitai.com', 'www.civitai.com', 'huggingface.co', 'www.huggingface.co', 'modelscope.cn', 'www.modelscope.cn') and not u.username and not u.password and u.port in (None, 443)
    except (TypeError, ValueError):
        return False


def public_url(value):
    if not isinstance(value, str) or len(value) > 16000:
        raise ValueError('Invalid download URL')
    u = urlsplit(value)
    host = (u.hostname or '').lower()
    if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
        raise ValueError('Only public HTTPS download URLs are supported')
    if not host or '.' not in host or host.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('Local download URLs are not allowed')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('Local download URLs are not allowed')
    return value


def validate_transfer(data):
    if not isinstance(data, dict):
        raise ValueError('Invalid request')
    request_id = data.get('request_id', '')
    if not isinstance(request_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}', request_id):
        raise ValueError('Invalid request ID')
    original = data.get('url', '')
    referrer = data.get('referrer', '')
    if not (red_url(original) or red_url(referrer)):
        raise ValueError('Supported sources: Hugging Face, Civitai.com, Civitai.red and ModelScope.cn')
    original = public_url(original)
    final = public_url(data.get('final_url') or original)
    path = data.get('filename', '')
    if not isinstance(path, str) or len(path) > 32000 or not re.match(r'^[A-Za-z]:[\\/]', path):
        raise ValueError('Wait for Chrome to confirm an absolute local Windows filename')
    parts = path.replace('/', '\\').split('\\')[1:]
    for part in parts:
        if (not part or part in ('.', '..') or part.endswith((' ', '.'))
                or any(ord(c) < 32 or c in '<>:"|?*' for c in part)
                or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)):
            raise ValueError('Unsupported destination path')
    path = ntpath.normpath(path)
    if ntpath.splitext(path)[1].lower() not in MODEL_SUFFIXES:
        raise ValueError('Only model files and ZIP model archives are supported')
    size = data.get('total_bytes', 0)
    if not isinstance(size, (int, float)) or isinstance(size, bool):
        size = 0
    size = max(0, min(int(size), 10**15))
    return dict(request_id=request_id, url=original, final_url=final,
                referrer=referrer, filename=path, total_bytes=size)


class BrowserServer:
    """Workers exchange short requests with the GUI through a caller-owned signal."""
    def __init__(self, token, dispatch, port=PORT):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError('Invalid pairing key')
        self.token = token
        self.dispatch = dispatch
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # URLs and pairing keys must not be logged.

            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def origin_ok(self):
                origin = self.headers.get('Origin', '')
                return not origin or bool(re.fullmatch(r'chrome-extension://[a-p]{32}', origin))

            def reply(self, status, data):
                payload = json.dumps(data).encode('utf-8')
                self.send_response(status)
                origin = self.headers.get('Origin', '')
                if origin and self.origin_ok():
                    self.send_header('Access-Control-Allow-Origin', origin)
                    self.send_header('Vary', 'Origin')
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_OPTIONS(self):
                if not self.origin_ok():
                    return self.reply(403, {'ok': False, 'error': 'Origin denied'})
                self.send_response(204)
                self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', ''))
                self.send_header('Access-Control-Allow-Methods', 'POST')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-ND-Token')
                self.end_headers()

            def do_POST(self):
                supplied = self.headers.get('X-ND-Token', '')
                if not self.origin_ok() or not hmac.compare_digest(supplied.encode(), owner.token.encode()):
                    return self.reply(403, {'ok': False, 'error': 'Pairing key rejected'})
                if self.path not in ('/ping', '/prepare', '/commit'):
                    return self.reply(404, {'ok': False, 'error': 'Unknown action'})
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= MAX_BODY:
                        raise ValueError('Invalid request size')
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data, dict):
                        raise ValueError('Invalid request')
                    action = self.path[1:]
                    if action == 'prepare':
                        data = validate_transfer(data)
                    envelope = dict(action=action, data=data, done=threading.Event(),
                                    deadline=time.monotonic() + 8, result=None)
                    owner.dispatch(envelope)
                    if not envelope['done'].wait(8):
                        return self.reply(503, {'ok': False, 'error': 'Launcher is busy; retry later'})
                    self.reply(200, envelope['result'])
                except (ValueError, TypeError, OverflowError) as exc:
                    self.reply(400, {'ok': False, 'error': str(exc)})
                except Exception:
                    self.reply(503, {'ok': False, 'error': 'Bridge unavailable'})

        self.httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

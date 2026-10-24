import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from nd_browser import validate_transfer
from test_browser_bridge import payload

class MultiSiteTests(unittest.TestCase):
    def test_all_sources_and_cdn_referrers(self):
        for host in ('huggingface.co','civitai.com','civitai.red','modelscope.cn','www.modelscope.cn'):
            for cdn in (False, True):
                with self.subTest(host=host,cdn=cdn):
                    url='https://'+host+'/model/resolve/main/model.safetensors'
                    self.assertTrue(validate_transfer(payload(url='https://cdn.example.org/file' if cdn else url,referrer=url)))

    def test_lookalikes_are_rejected(self):
        for host in ('huggingface.co.evil.org','evilmodelscope.cn','civitai.com.evil.org'):
            with self.subTest(host=host),self.assertRaises(ValueError):
                validate_transfer(payload(url='https://'+host+'/file',referrer=''))

    def test_tokens_only_go_to_their_own_provider(self):
        tree=ast.parse((Path(__file__).parents[1]/'nd_launcher.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MainWindow')
        method=next(n for n in cls.body if getattr(n,'name','')=='_dl_step')
        ns={'FAST_DL_SCRIPT':'script'}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'method','exec'),ns)
        w=SimpleNamespace(spin_conn=Mock(),edit_civ_token=Mock(),edit_hf_token=Mock(),python_exe='python')
        w.spin_conn.value.return_value=8
        w.edit_civ_token.text.return_value='civ-secret'
        w.edit_hf_token.text.return_value='hf-secret'
        for host,token in [('huggingface.co','hf-secret'),('civitai.com','civ-secret'),('civitai.red','civ-secret'),('modelscope.cn','')]:
            for cdn in (False,True):
                with self.subTest(host=host,cdn=cdn):
                    original='https://'+host+'/file'
                    q=dict(name='model',dest=Path('/models/model.bin'),folder=Path('/models'))
                    result=ns['_dl_step'](w,q,dict(url='https://cdn.example.org/file' if cdn else original,original_url=original),dict(source='browser'))
                    env=result[4]
                    self.assertEqual(env['ND_DL_TOKEN'],'' if cdn else token)
                    if cdn:
                        self.assertEqual(env['ND_DL_REFRESH_TOKEN'],token)
                        self.assertEqual(env['ND_DL_REFRESH_URL'],original)

    def test_manual_and_browser_use_identical_direct_command(self):
        tree=ast.parse((Path(__file__).parents[1]/'nd_launcher.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MainWindow')
        method=next(n for n in cls.body if getattr(n,'name','')=='_dl_step')
        ns={'FAST_DL_SCRIPT':'script','hf_resolve_url':lambda *args:'https://huggingface.co/u/repo/resolve/main/m.bin'}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'method','exec'),ns)
        w=SimpleNamespace(spin_conn=Mock(),edit_civ_token=Mock(),edit_hf_token=Mock(),python_exe='python',chk_hf_cli=Mock())
        w.spin_conn.value.return_value=8;w.edit_civ_token.text.return_value='civ';w.edit_hf_token.text.return_value='hf';w.chk_hf_cli.isChecked.return_value=False
        for source,url in [('civitai','https://civitai.red/api/download/models/12'),('hf','https://huggingface.co/u/repo/resolve/main/m.bin')]:
            q=dict(name='m.bin',dest=Path('/models/m.bin'),folder=Path('/models'))
            info=dict(source=source,repo='u/repo',revision='main',repo_type='model')
            normal=ns['_dl_step'](w,q,dict(url=url,hf_path='m.bin'),info)
            captured=ns['_dl_step'](w,q,dict(url='https://cdn.example.org/m.bin',original_url=url),dict(source='browser'))
            self.assertEqual(normal[1:4],captured[1:4])
            self.assertEqual(normal[4]['ND_DL_TOKEN'],captured[4]['ND_DL_TOKEN'])
            self.assertEqual(captured[4]['ND_DL_NO_OVERWRITE'],'1')
            self.assertEqual(captured[4]['ND_DL_FALLBACK_URL'],'https://cdn.example.org/m.bin')

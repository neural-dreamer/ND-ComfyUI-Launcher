import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

TREE=ast.parse((Path(__file__).parents[1]/'nd_launcher.py').read_text())
CLS=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='MainWindow')
NODES=[n for n in TREE.body if getattr(n,'name','')=='parse_post_update_commands']+[n for n in CLS.body if getattr(n,'name','')=='_post_update_steps']
NS={'re':re,'tr':lambda s,*a:s.format(*a)}
exec(compile(ast.Module(body=NODES,type_ignores=[]),'commands','exec'),NS)
parse=NS['parse_post_update_commands']

class PostCommandsTests(unittest.TestCase):
    def test_prefixes_comments_and_windows_paths(self):
        text='# comment\npython.exe -m pip install x\npip install y\n"C:\\Other Python\\python.exe" "C:\\my scripts\\task.py"'
        self.assertEqual(parse(text),[(2,['-m','pip','install','x']),(3,['-m','pip','install','y']),(4,[r'C:\my scripts\task.py'])])

    def test_windows_quote_roundtrip(self):
        for args in [['-c', 'print("hi")'],['script.py','','C:\\folder name\\'],['-m','pip','install',r'C:\a b\c.whl']]:
            self.assertEqual(parse(subprocess.list2cmdline(args))[0][1],args)

    def test_invalid_quotes_or_empty_python(self):
        for text in ['python.exe','-m','-c','-m pip "broken']:
            with self.assertRaises(ValueError):parse(text)

    def window(self,root,text):
        return SimpleNamespace(cfg={'post_update_enabled':True,'post_update_commands':text,'post_update_comfy':True},python_exe=sys.executable,root=Path(root),tasks=SimpleNamespace(errors=0),console=Mock())

    def run_steps(self,w,kind='comfy'):
        queue=NS['_post_update_steps'](w,kind)
        executed=[]
        while queue:
            step=queue.pop(0)
            if callable(step):queue[:0]=step() or []
            else:
                label,exe,args,cwd=step
                executed.append(step)
                result=subprocess.run([exe]+args,cwd=cwd,capture_output=True)
                w.tasks.errors+=int(result.returncode!=0)
        return executed

    def test_portable_python_cwd_and_order(self):
        with tempfile.TemporaryDirectory() as td:
            lines=[subprocess.list2cmdline(['-c', "from pathlib import Path; Path('result').open('a').write('"+v+"')"]) for v in ('1','2')]
            w=self.window(td,'\n'.join(lines));steps=self.run_steps(w)
            self.assertEqual((Path(td)/'result').read_text(),'12')
            self.assertTrue(all(s[1]==sys.executable and s[3]==Path(td) for s in steps))

    def test_failure_stops_remaining_commands(self):
        with tempfile.TemporaryDirectory() as td:
            w=self.window(td,'-c "raise SystemExit(2)"\n-c "raise Exception()"')
            self.assertEqual(len(self.run_steps(w)),1)
            w.tasks.errors=1
            self.assertEqual(self.run_steps(w),[])
            w.console.system.assert_called()

    def test_optional_and_scope(self):
        w=self.window('.', '-m pip --version')
        self.assertEqual(NS['_post_update_steps'](w,'nodes'),[])
        w.cfg['post_update_enabled']=False
        self.assertEqual(NS['_post_update_steps'](w,'comfy'),[])
        w.cfg.update(post_update_enabled=True,post_update_nodes=True)
        self.assertTrue(NS['_post_update_steps'](w,'nodes'))

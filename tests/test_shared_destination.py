"""The current shared destination is authoritative for every checked file."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SOURCE=Path(__file__).resolve().parents[1]/'nd_launcher.py'
TREE=ast.parse(SOURCE.read_text(encoding='utf-8'))
CLS=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='MainWindow')
NODES=[n for n in CLS.body if isinstance(n,ast.FunctionDef) and n.name in ('_checked_rows','_on_common_folder_changed','_on_root_changed')]
NS={'Path':Path,'Qt':SimpleNamespace(UserRole=256,Checked=2)}
exec(compile(ast.Module(body=NODES,type_ignores=[]),str(SOURCE),'exec'),NS)

class SharedDestinationTests(unittest.TestCase):
    def window(self, destination='/models/shared'):
        files=[dict(name='one',folder='loras',custom='/old/one'),dict(name='two',folder='vae',custom='/old/two'),dict(name='three')]
        items=[]
        for i in range(3):
            items.append(SimpleNamespace(data=lambda col,role,i=i:i,checkState=lambda col,i=i:2 if i<2 else 0))
        combo=Mock()
        combo.currentData.side_effect=lambda role=None:'loras' if role is not None else destination
        return SimpleNamespace(_current_files=lambda:files,cb_dl_folder=combo,
            tree_files=SimpleNamespace(topLevelItemCount=lambda:3,topLevelItem=lambda i:items[i]),
            _set_cfg=Mock(),_update_dl_summary=Mock()),files

    def test_one_folder_overrides_old_individual_destinations(self):
        w,files=self.window()
        rows=NS['_checked_rows'](w)
        self.assertEqual([f['name'] for f,p in rows],['one','two'])
        self.assertEqual([p for f,p in rows],[Path('/models/shared')]*2)
        self.assertFalse(files[2]['checked'])

    def test_cancelled_browse_keeps_selections(self):
        w,files=self.window('__browse__')
        self.assertEqual(NS['_checked_rows'](w),[])
        self.assertTrue(files[0]['checked'])

    def test_folder_selection_saves_without_assign_button(self):
        w,_=self.window()
        NS['_on_common_folder_changed'](w)
        w._set_cfg.assert_called_once_with('dl_last_folder','loras')
        w._update_dl_summary.assert_called_once()

    def test_custom_path_saves(self):
        w,_=self.window('/custom/models')
        w.cb_dl_folder.currentData.side_effect=lambda role=None:None if role is not None else '/custom/models'
        NS['_on_common_folder_changed'](w)
        w._set_cfg.assert_called_once_with('dl_last_folder','/custom/models')

    def test_root_change_does_not_rebuild_file_selection(self):
        w=SimpleNamespace(_set_cfg=Mock(),cb_dl_root=Mock(),cb_dl_folder=Mock(),
                          _last_folder_key=lambda:'loras',_fill_folder_combo=Mock(),_on_common_folder_changed=Mock())
        w.cb_dl_root.currentData.return_value='external'
        NS['_on_root_changed'](w)
        w._fill_folder_combo.assert_called_once_with(w.cb_dl_folder,key='loras')
        w._on_common_folder_changed.assert_called_once()

if __name__=='__main__':unittest.main()

from pathlib import Path
import tempfile
import unittest
from nd_extension_install import browser_spec, extension_browsers, load_catalog, prepare_extension

SOURCE = Path(__file__).resolve().parents[1] / 'chrome_extension'

class ExtensionInstallTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(SOURCE)

    def test_browser_specific_pages(self):
        cases = [(r'C:\Chrome\chrome.exe','chrome://extensions/'),
                 (r'C:\Edge\msedge.exe','edge://extensions/'),
                 (r'C:\Yandex\browser.exe','browser://extensions/'),
                 (r'C:\Brave\brave.exe','brave://extensions/'),
                 (r'C:\Opera GX\launcher.exe','opera://extensions/'),
                 (r'C:\Vivaldi\vivaldi.exe','vivaldi://extensions/'),
                 (r'C:\Chromium\chrome.exe','chrome://extensions/'),
                 (r'C:\Thorium\thorium.exe','chrome://extensions/')]
        for exe,url in cases:
            with self.subTest(exe=exe):
                self.assertEqual(browser_spec(exe,'',self.catalog)['url'],url)
        self.assertEqual(browser_spec(r'C:\Chromium\chrome.exe','',self.catalog)['id'],'chromium')

    def test_unrelated_executables_not_offered(self):
        for exe in ('firefox.exe','iexplore.exe','random.exe','launcher.exe','browser.exe'):
            self.assertIsNone(browser_spec(exe,'',self.catalog))

    def test_registry_label_identifies_yandex_portable(self):
        self.assertEqual(browser_spec('browser.exe','Яндекс Браузер',self.catalog)['id'],'yandex')

    def test_detected_preferred_fallback_and_dedup(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            yandex=base/'Yandex/YandexBrowser/Application/browser.exe'
            edge=base/'portable/msedge.exe'
            firefox=base/'firefox.exe'
            for p in (yandex,edge,firefox):
                p.parent.mkdir(parents=True,exist_ok=True);p.touch()
            rows=extension_browsers([('Yandex',str(yandex)),('Firefox',str(firefox))],str(edge),self.catalog,{'LOCALAPPDATA':td})
            self.assertEqual({r[1] for r in rows},{str(yandex),str(edge)})
            self.assertEqual(len(rows),2)
            self.assertEqual(extension_browsers([],str(base/'missing/chrome.exe'),self.catalog,{}),[])

    def test_prepare_updates_stable_folder_and_handles_self_copy(self):
        with tempfile.TemporaryDirectory() as td:
            target=prepare_extension(SOURCE,td)
            self.assertEqual(target,Path(td)/'NDLauncher/ChromeExtension')
            self.assertEqual((target/'manifest.json').read_bytes(),(SOURCE/'manifest.json').read_bytes())
            (target/'options.css').write_text('old')
            prepare_extension(SOURCE,td)
            self.assertEqual((target/'options.css').read_bytes(),(SOURCE/'options.css').read_bytes())
            self.assertEqual(prepare_extension(target,td),target)
            self.assertFalse((target/'chrome_extension').exists())

    def test_missing_source_and_environment_fail(self):
        with self.assertRaises(OSError):prepare_extension(SOURCE,None)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):prepare_extension(td,td)

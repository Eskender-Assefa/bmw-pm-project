"""Portable-package boundary tests, using only temporary files."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.package_windows import safe_name
from scripts.portable_server import relocate_sources


class PortablePackageTests(unittest.TestCase):
    def make_source(self, root, stored):
        (root / '.local' / 'sources').mkdir(parents=True)
        (root / '.local' / 'sources' / 'sample.pdf').write_bytes(b'original source')
        with sqlite3.connect(root / '.local' / 'cockpit.sqlite') as db:
            db.execute('CREATE TABLE sources(id TEXT, path TEXT)')
            db.execute('INSERT INTO sources VALUES (?,?)', ('s1', stored))

    def test_sources_survive_linux_windows_and_repeated_moves(self):
        for stored in ('/home/old/app/.local/sources/sample.pdf',
                       'C:\\Users\\Friend\\BMW\\app\\.local\\sources\\sample.pdf',
                       '.local/sources/sample.pdf'):
            with self.subTest(stored=stored), tempfile.TemporaryDirectory(prefix='BMW test ') as directory:
                root = Path(directory)
                self.make_source(root, stored)
                relocate_sources(root)
                relocate_sources(root)
                with sqlite3.connect(root / '.local' / 'cockpit.sqlite') as db:
                    self.assertEqual(db.execute('SELECT path FROM sources').fetchone()[0], '.local/sources/sample.pdf')
                self.assertEqual((root / '.local/sources/sample.pdf').read_bytes(), b'original source')

    def test_missing_documents_fail_before_server_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root, '.local/sources/missing.pdf')
            with self.assertRaisesRegex(RuntimeError, 'source document is missing'):
                relocate_sources(root)

    def test_source_paths_cannot_escape_the_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root, '.local/../../outside.pdf')
            with self.assertRaises(RuntimeError):
                relocate_sources(root)

    def test_windows_unsafe_names_are_rejected(self):
        for name in ('../escape', '/absolute', 'C:/drive', 'a\\b', 'CON.txt',
                     'test/a:b.txt', 'trailing.', 'trailing ', 'NUL', 'x/LPT2.log'):
            with self.subTest(name=name):
                self.assertFalse(safe_name(name))

    def test_normal_archive_names_are_supported(self):
        for name in ('BMW-G60-Windows/Start BMW.exe', 'app/.local/cockpit.sqlite',
                     'runtime/python/Lib/site-packages/pydantic_core/_pydantic_core.cp314-win_amd64.pyd'):
            self.assertTrue(safe_name(name))


if __name__ == '__main__':
    unittest.main()

"""Boundary checks for the private CAS restore manifest (no server access)."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import restore_cold_rehearsals as restorer
from restore_cold_rehearsals import NAMES, SOURCE, validate_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self):
        metadata = dict(mode=0o700, uid=0, gid=0, mtime_ns=1, atime_ns=1, xattrs={})
        self.sha = hashlib.sha256(b'').hexdigest()
        self.manifest = {
            'format': 'gpm-cold-rehearsal-cas-v2',
            'roots': {name: (SOURCE / name).as_posix() for name in NAMES},
            'objects': {self.sha: 0},
            'files': [dict(path=name, kind='directory', **metadata) for name in NAMES]
                     + [dict(path=NAMES[0] + '/file', kind='file', bytes=0,
                             sha256=self.sha, source_nlink=1, **metadata)],
        }

    def test_valid_inventory(self):
        self.assertEqual(len(validate_manifest(self.manifest)), 6)

    def test_path_escape_and_noncanonical_paths(self):
        for path in ['/etc/passwd', '../escape', NAMES[0] + '/../escape',
                     NAMES[0] + '//file', NAMES[0] + '/./file', NAMES[0] + '/x\\y']:
            with self.subTest(path=path):
                candidate = copy.deepcopy(self.manifest)
                candidate['files'][-1]['path'] = path
                with self.assertRaises(RuntimeError):
                    validate_manifest(candidate)

    def test_symlink_parent(self):
        row = self.manifest['files'][0]
        self.manifest['files'].insert(-1, dict(row, path=NAMES[0] + '/link',
                                               kind='symlink', target='/etc'))
        self.manifest['files'][-1]['path'] = NAMES[0] + '/link/file'
        with self.assertRaises(RuntimeError):
            validate_manifest(self.manifest)

    def test_duplicate_entry(self):
        self.manifest['files'].append(copy.deepcopy(self.manifest['files'][-1]))
        with self.assertRaises(RuntimeError):
            validate_manifest(self.manifest)

    def test_wrong_size_and_hardlinks(self):
        for field, value in [('bytes', 1), ('source_nlink', 2)]:
            candidate = copy.deepcopy(self.manifest)
            candidate['files'][-1][field] = value
            with self.assertRaises(RuntimeError):
                validate_manifest(candidate)

    def test_wrong_root_and_unreferenced_object(self):
        candidate = copy.deepcopy(self.manifest)
        candidate['roots'][NAMES[0]] = '/etc'
        with self.assertRaises(RuntimeError):
            validate_manifest(candidate)
        self.manifest['objects']['a' * 64] = 1
        with self.assertRaises(RuntimeError):
            validate_manifest(self.manifest)


@unittest.skipUnless(os.name == 'posix', 'Linux metadata round trip')
class RestoreTests(unittest.TestCase):
    def test_full_and_bounded_restore(self):
        with tempfile.TemporaryDirectory(prefix='gpm-cas-restore-test-') as directory:
            parent = Path(directory)
            source = parent / 'original'
            source.mkdir()
            for name in NAMES:
                (source / name).mkdir()
            for name in ['one', 'two']:
                (source / NAMES[0] / name).write_bytes(b'round trip\n')
            (source / NAMES[1] / 'empty').touch()
            os.symlink('/outside/must-not-be-followed', source / NAMES[0] / 'link')
            files = []
            objects = {}
            for path in sorted(source.rglob('*')):
                info = path.lstat()
                row = dict(path=path.relative_to(source).as_posix(), mode=info.st_mode & 0o7777,
                           uid=info.st_uid, gid=info.st_gid, atime_ns=info.st_atime_ns,
                           mtime_ns=info.st_mtime_ns, xattrs={})
                if path.is_symlink():
                    row.update(kind='symlink', target=os.readlink(path))
                elif path.is_dir():
                    row.update(kind='directory')
                else:
                    data = path.read_bytes()
                    sha = hashlib.sha256(data).hexdigest()
                    row.update(kind='file', bytes=len(data), sha256=sha, source_nlink=1)
                    objects[sha] = data
                files.append(row)
            manifest = dict(format='gpm-cold-rehearsal-cas-v2', files=files,
                            objects={sha: len(data) for sha, data in objects.items()},
                            roots={name: str(source / name) for name in NAMES})
            with patch.object(restorer, 'PARENT', parent), patch.object(restorer, 'SOURCE', source), \
                    patch.object(restorer, 'RESERVE', 0):
                for full in [False, True]:
                    if full:
                        # Recovery must work after the original directories are gone.
                        shutil.rmtree(source)
                    stream = io.BytesIO()
                    for sha, data in objects.items():
                        stream.write((json.dumps(dict(sha256=sha, bytes=len(data))) + '\n').encode())
                        stream.write(data)
                    stream.write(b'{"end":true}\n')
                    stream.seek(0)
                    destination = parent / ('cold-restore-20261117-full' if full else 'cold-restore-20261117-trial')
                    restorer.restore(destination, manifest, stream, full)
                    result = json.loads((destination / 'restore-result.json').read_text())
                    self.assertEqual(result['restored_files'], 3)
                    self.assertEqual(result['original_file_hashes_compared'], 0 if full else 3)
                    self.assertEqual(result['complete_tree_retained'], full)
                    if full:
                        self.assertEqual((destination / NAMES[0] / 'one').read_bytes(), b'round trip\n')
                        self.assertEqual(os.readlink(destination / NAMES[0] / 'link'), '/outside/must-not-be-followed')
                    else:
                        self.assertEqual(list(destination.iterdir()), [destination / 'restore-result.json'])


if __name__ == '__main__':
    unittest.main()

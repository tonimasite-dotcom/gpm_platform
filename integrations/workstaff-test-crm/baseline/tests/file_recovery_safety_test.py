"""Exercise malicious archive paths and integrity failures on synthetic files."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import restore_files_receiver as receiver

FIXTURES = receiver.WORK / 'file-restore-safety-tests-20261109'


def run_case(name, members, expected, should_pass):
    work = FIXTURES / name
    work.mkdir(mode=0o700, parents=True, exist_ok=False)
    receiver.WORK = work
    receiver.DEST = work / 'restore'
    compressed = io.BytesIO()
    with tarfile.open(fileobj=compressed, mode='w:gz') as archive:
        for path, kind, content in members:
            member = tarfile.TarInfo(path)
            if kind == 'file':
                member.size = len(content)
                member.mode = 0o640
                archive.addfile(member, io.BytesIO(content))
            else:
                member.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
                member.linkname = content
                archive.addfile(member)
    manifest = {'ts_root': '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru', 'files': expected}
    stream = io.BytesIO(json.dumps(manifest).encode() + b'\n' + compressed.getvalue())
    old_input, old_output = sys.stdin, sys.stdout
    class Input:
        buffer = stream
    sys.stdin = Input()
    sys.stdout = io.StringIO()
    passed = False
    try:
        receiver.main()
        passed = True
    except RuntimeError:
        pass
    finally:
        sys.stdin, sys.stdout = old_input, old_output
    if passed != should_pass:
        raise AssertionError('Unexpected outcome: ' + name)
    if (work / 'escape').exists():
        raise AssertionError('Path escaped restore tree')
    if name == 'external_symlink_quarantined':
        if (receiver.DEST / 'tree/public/storage').exists() or (receiver.DEST / 'tree/public/storage').is_symlink():
            raise AssertionError('External symlink activated')
        links = json.loads((receiver.DEST / 'quarantined-symlinks.json').read_text())
        if links['public/storage']['target'] != '/outside-storage':
            raise AssertionError('Lost symlink metadata')


if __name__ == '__main__':
    value = b'synthetic-test-content'
    record = {'kind': 'file', 'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest(), 'mode': 0o640}
    cases = [
        ('regular_file', [('nested/test.txt', 'file', value)], {'nested/test.txt': record}, True),
        ('parent_traversal', [('../escape', 'file', value)], {'../escape': record}, False),
        ('absolute_path', [('/escape', 'file', value)], {'/escape': record}, False),
        ('duplicate_member', [('test', 'file', value), ('test', 'file', value)], {'test': record}, False),
        ('wrong_content', [('test', 'file', b'x' * len(value))], {'test': record}, False),
        ('wrong_size', [('test', 'file', b'x')], {'test': record}, False),
        ('missing_member', [], {'test': record}, False),
        ('hardlink', [('test', 'hardlink', 'other')], {'test': record}, False),
        ('unexpected_member', [('unknown', 'file', value)], {'test': record}, False),
        ('external_symlink_quarantined', [('public/storage', 'symlink', '/outside-storage')],
            {'public/storage': {'kind': 'symlink', 'target': '/outside-storage'}}, True),
    ]
    for case in cases:
        run_case(*case)
    print('File recovery safety: ' + str(len(cases)) + ' scenarios passed')

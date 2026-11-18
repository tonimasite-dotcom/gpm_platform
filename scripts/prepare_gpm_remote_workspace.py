"""Prepare an isolated GPM developer workspace on its frontend host only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

FRONTEND_HOST = '186.246.10.163'
ROOT = Path('/opt/gpm-development')
VERSION = '3.38.5'


def run(args, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True, timeout=900)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['inspect', 'prepare'], required=True)
    parser.add_argument('--expected-host', required=True)
    args = parser.parse_args()
    assert args.expected_host == FRONTEND_HOST, 'GPM frontend target mismatch'
    connection = os.environ.get('SSH_CONNECTION', '').split()
    assert len(connection) == 4 and connection[2] == FRONTEND_HOST, 'Connected host mismatch'
    assert not ROOT.is_symlink(), 'Unexpected workspace link'
    mem = {line.split(':')[0]: int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:', 'MemAvailable:'))}
    free = shutil.disk_usage('/opt').free
    info = {'project': 'GPM', 'component': 'frontend development', 'mode': args.mode, 'free_bytes': free, 'memory': mem, 'existing_workspace': ROOT.exists(), 'production_changed': False}
    print(json.dumps(info), flush=True)
    if args.mode == 'inspect':
        return
    assert free >= 6 * 1024**3, 'Insufficient disk reserve for developer SDK'
    assert mem['MemAvailable'] >= 1024**3, 'Insufficient memory reserve; do not compete with production'
    assert not ROOT.exists(), 'Existing workspace requires separate review'
    os.umask(0o077)
    os.nice(15)
    ROOT.mkdir(mode=0o700)
    (ROOT / 'owner.json').write_text(json.dumps({'project': 'GPM', 'role': 'isolated development', 'frontend_host': FRONTEND_HOST}))
    sdk_dir = ROOT / 'sdk'
    sdk_dir.mkdir()
    archive = ROOT / 'flutter-sdk.tar.xz'
    with urllib.request.urlopen('https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json', timeout=60) as response:
        releases = json.load(response)
    release = next(row for row in releases['releases'] if row['version'] == VERSION and row['channel'] == 'stable' and row.get('dart_sdk_arch', 'x64') == 'x64')
    url = releases['base_url'] + '/' + release['archive']
    assert url.startswith('https://storage.googleapis.com/flutter_infra_release/')
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as response, archive.open('xb') as output:
        for block in iter(lambda: response.read(4 * 1024**2), b''):
            output.write(block)
            digest.update(block)
    assert digest.hexdigest() == release['sha256'], 'Official SDK checksum mismatch'
    with tarfile.open(archive, 'r:xz') as source:
        for entry in source.getmembers():
            target = (sdk_dir / entry.name).resolve()
            assert str(target).startswith(str(sdk_dir.resolve()) + '/')
            if entry.issym():
                assert str((target.parent / entry.linkname).resolve()).startswith(str(sdk_dir.resolve()) + '/')
            if entry.islnk():
                assert str((sdk_dir / entry.linkname).resolve()).startswith(str(sdk_dir.resolve()) + '/')
            assert entry.isfile() or entry.isdir() or entry.issym() or entry.islnk()
        source.extractall(sdk_dir)
    archive.unlink()
    repo = ROOT / 'repository'
    run(['git', 'clone', '--depth', '1', '--branch', 'main', 'https://github.com/tonimasite-dotcom/gpm_platform.git', str(repo)])
    (repo / '.env').write_text('GPM_APP_MODE=demo\n')
    sdk = sdk_dir / 'flutter'
    cache = ROOT / 'pub-cache'
    env = dict(os.environ, CI='true', FLUTTER_SUPPRESS_ANALYTICS='true', DART_SUPPRESS_ANALYTICS='true', PUB_CACHE=str(cache))
    env['PATH'] = str(sdk / 'bin') + ':' + env['PATH']
    run([str(sdk / 'bin/flutter'), 'pub', 'get'], cwd=str(repo), env=env)
    run([str(sdk / 'bin/flutter'), 'analyze', '--no-pub'], cwd=str(repo), env=env)
    workspace = {'folders': [{'path': 'repository'}], 'settings': {'dart.flutterSdkPath': str(sdk), 'terminal.integrated.env.linux': {'PATH': str(sdk / 'bin') + ':${env:PATH}', 'PUB_CACHE': str(cache), 'CI': 'true'}}, 'extensions': {'recommendations': ['Dart-Code.dart-code', 'Dart-Code.flutter']}}
    (ROOT / 'GPM.code-workspace').write_text(json.dumps(workspace, indent=2))
    result = dict(info, workspace_ready=True, flutter=VERSION, sdk_sha256=release['sha256'], archive_removed=True, analyze='passed', builds='GitHub Actions')
    (ROOT / 'ready.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

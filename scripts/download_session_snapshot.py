"""Download and hash a session's encrypted assets; never decrypt or start services."""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def github_token():
    value = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if value:
        return value
    result = subprocess.run(['git', 'credential', 'fill'],
                            input='protocol=https\nhost=github.com\n\n', text=True,
                            capture_output=True, check=True,
                            env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never'))
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)['password']


def encrypted_asset(repo, asset_id, token):
    url = 'https://api.github.com/repos/' + repo + '/releases/assets/' + str(int(asset_id))
    request = urllib.request.Request(url + '?nonce=' + str(time.time_ns()), headers={
        'Authorization': 'Bearer ' + token, 'Accept': 'application/octet-stream',
        'User-Agent': 'GPM-session-recovery', 'Cache-Control': 'no-cache'})
    try:
        return urllib.request.build_opener(NoRedirect).open(request, timeout=120)
    except urllib.error.HTTPError as error:
        if error.code != 302:
            raise
        # Only the signed download URL goes to the storage host, never the GitHub credential.
        return urllib.request.urlopen(error.headers['Location'], timeout=120)


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def download(row, repo, destination, token):
    name = pathlib.PurePosixPath(row['name'])
    if len(name.parts) != 1 or '\\' in row['name'] or ':' in row['name']:
        raise RuntimeError('Unsafe artifact filename')
    target = destination / name.name
    if target.exists():
        if target.is_symlink() or target.stat().st_size != row['bytes'] or sha(target) != row['sha256']:
            raise RuntimeError('Existing file does not match; it will not be overwritten')
        print(json.dumps({'verified_existing': row['name']}), flush=True)
        return
    partial = destination / (name.name + '.download')
    state = destination / (name.name + '.resume.json')
    identity = {'name': row['name'], 'bytes': row['bytes'], 'sha256': row['sha256']}
    if state.is_symlink() or state.exists() and json.loads(state.read_text()) != identity:
        raise RuntimeError('Unrecognized resume metadata; refusing to alter it')
    if partial.exists():
        if partial.is_symlink() or not state.is_file() or json.loads(state.read_text()) != identity:
            raise RuntimeError('Unrecognized partial download; refusing to alter it')
    else:
        with partial.open('xb'):
            pass
        if not state.exists():
            with state.open('x') as output:
                json.dump(identity, output)
    parts = row.get('parts') or [row]
    offset = 0
    for part in parts:
        complete = False
        if partial.stat().st_size >= offset + part['bytes']:
            value = hashlib.sha256()
            with partial.open('rb') as source:
                source.seek(offset)
                remaining = part['bytes']
                while remaining:
                    block = source.read(min(4 * 1024 * 1024, remaining))
                    if not block:
                        break
                    remaining -= len(block)
                    value.update(block)
            complete = not remaining and value.hexdigest() == part['sha256']
        if not complete:
            with partial.open('r+b') as output:
                output.seek(offset)
                output.truncate()
                value = hashlib.sha256()
                count = 0
                with encrypted_asset(repo, part['asset_id'], token) as source:
                    for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
                        count += len(block)
                        if count > part['bytes']:
                            raise RuntimeError('Asset exceeds expected length')
                        output.write(block)
                        value.update(block)
                if count != part['bytes'] or value.hexdigest() != part['sha256']:
                    raise RuntimeError('Downloaded part hash mismatch')
        offset += part['bytes']
        print(json.dumps({'artifact': row['name'], 'verified_bytes': offset,
                          'total_bytes': row['bytes']}), flush=True)
    if partial.stat().st_size != row['bytes'] or sha(partial) != row['sha256']:
        raise RuntimeError('Complete encrypted artifact hash mismatch')
    # Exclusive hard-link creation cannot replace an existing user file.
    os.link(str(partial), str(target))
    partial.unlink()
    print(json.dumps({'download_sha256_verified': row['name']}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=pathlib.Path)
    parser.add_argument('--directory', required=True, type=pathlib.Path)
    parser.add_argument('--role', action='append')
    parser.add_argument('--include-history', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.directory.mkdir(parents=True, exist_ok=True)
    rows = manifest['artifacts']
    if args.include_history:
        rows = rows + manifest.get('external_artifacts', [])
    if args.role:
        rows = [row for row in rows if row['role'] in args.role]
    token = github_token()
    for row in rows:
        download(row, manifest['repo'], args.directory, token)
    print(json.dumps({'encrypted_artifacts_verified': len(rows), 'plaintext_extracted': False,
                      'database_or_application_started': False}), flush=True)


if __name__ == '__main__':
    main()

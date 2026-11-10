#!/usr/bin/env python3
"""Read effective TS FPM settings through its Unix socket. No shared reload."""
from pathlib import Path
import json
import os
import pwd
import secrets
import socket
import stat
import struct
import tempfile

SOCKET = Path('/var/run/ts.workstaffcrm.ru.sock')
TEMP_PARENT = Path('/var/www/gruzpiter/data/tmp')


def record(kind, body=b''):
    if len(body) > 65535:
        raise ValueError('FCGI_RECORD_TOO_LARGE')
    padding = (-len(body)) % 8
    return struct.pack('!BBHHBB', 1, kind, 1, len(body), padding, 0) + body + b'\0' * padding


def length(value):
    return bytes([value]) if value < 128 else struct.pack('!I', value | 0x80000000)


def exact(client, size):
    chunks = []
    while size:
        block = client.recv(size)
        if not block:
            raise RuntimeError('FCGI_TRUNCATED_RESPONSE')
        chunks.append(block)
        size -= len(block)
    return b''.join(chunks)


def request(script, token, extra_params=None, metadata_only=False):
    params = {'SCRIPT_FILENAME': str(script), 'SCRIPT_NAME': '/private-gpm-ts-probe.php',
              'SERVER_NAME': 'ts.workstaffcrm.ru', 'HTTP_HOST': 'ts.workstaffcrm.ru',
              'SERVER_PROTOCOL': 'HTTP/1.1', 'REQUEST_METHOD': 'GET', 'REQUEST_URI': '/private-gpm-ts-probe.php',
              'REMOTE_ADDR': '127.0.0.1', 'GPM_TS_PRIVATE_PROBE_TOKEN': token}
    if extra_params:
        params.update(extra_params)
    encoded = b''
    for key, value in params.items():
        key = key.encode()
        value = value.encode()
        encoded += length(len(key)) + length(len(value)) + key + value
    output = b''
    errors = b''
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(20)
        client.connect(str(SOCKET))
        client.sendall(record(1, struct.pack('!HB5s', 1, 0, b'\0' * 5))
                       + record(4, encoded) + record(4) + record(5))
        while True:
            version, kind, request_id, size, padding, reserved = struct.unpack('!BBHHBB', exact(client, 8))
            if version != 1 or request_id != 1:
                raise RuntimeError('UNEXPECTED_FCGI_RECORD')
            content = exact(client, size)
            exact(client, padding)
            if kind == 6:
                output += content
            elif kind == 7:
                errors += content
            elif kind == 3:
                app_status, protocol_status = struct.unpack('!IB3x', content)
                if app_status != 0 or protocol_status != 0:
                    raise RuntimeError('FCGI_APPLICATION_FAILED')
                break
    if errors:
        raise RuntimeError('FCGI_DIAGNOSTIC_ERROR_WITHHELD')
    headers, body = output.split(b'\r\n\r\n', 1)
    if metadata_only:
        values = {}
        for line in headers.decode(errors='replace').split('\r\n'):
            key, separator, value = line.partition(':')
            if separator:
                values[key.lower()] = value.strip()
        status = int(values.get('status', '200').split()[0])
        return {'status': status, 'demo_marker': values.get('x-gpm-ts-demo'), 'response_bytes': len(body)}
    if b'Status: 403' in headers or b'Status: 500' in headers:
        raise RuntimeError('FCGI_REQUEST_REJECTED')
    return json.loads(body)


def run_probe(script_name='fpm_inspect.php', plan=None):
    os.umask(0o077)
    if SOCKET.is_symlink() or not stat.S_ISSOCK(SOCKET.stat().st_mode):
        raise RuntimeError('EXACT_TS_SOCKET_REQUIRED')
    if TEMP_PARENT.resolve() != TEMP_PARENT or not TEMP_PARENT.is_dir():
        raise RuntimeError('EXACT_PRIVATE_TEMP_PARENT_REQUIRED')
    owner = pwd.getpwnam('gruzpiter')
    if SOCKET.stat().st_uid != owner.pw_uid:
        raise RuntimeError('TS_SOCKET_OWNER_MISMATCH')
    folder = Path(tempfile.mkdtemp(prefix='gpm-ts-fpm-inspect-', dir=str(TEMP_PARENT)))
    script = folder / 'inspect.php'
    secret = folder / 'token'
    plan_path = folder / 'plan.json'
    try:
        os.chown(folder, owner.pw_uid, owner.pw_gid)
        if script_name not in ['fpm_inspect.php', 'fpm_invalidate.php', 'fpm_runtime_probe.php']:
            raise RuntimeError('UNKNOWN_PRIVATE_PROBE')
        script.write_bytes((Path(__file__).parent / script_name).read_bytes())
        secret.write_text(secrets.token_hex(32))
        files = [script, secret]
        if plan is not None:
            plan_path.write_text(json.dumps(plan))
            files.append(plan_path)
        for path in files:
            path.chmod(0o600)
            os.chown(path, owner.pw_uid, owner.pw_gid)
        result = request(script, secret.read_text())
        result.update({'socket': str(SOCKET), 'main_crm_accessed': False,
                       'existing_live_files_changed': False, 'shared_services_reloaded': False})
        return result
    finally:
        # Only the two files just created, in the exact new private temp folder.
        if folder.parent == TEMP_PARENT and folder.resolve() == folder:
            for path in [script, secret, plan_path]:
                if path.exists() and not path.is_symlink():
                    path.unlink()
            folder.rmdir()


def main():
    print(json.dumps(run_probe(), indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'passed': False, 'safe_error': 'TS_FPM_PROBE_FAILED_DETAILS_WITHHELD'}))
        raise SystemExit(1)

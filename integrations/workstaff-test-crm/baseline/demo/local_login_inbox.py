#!/usr/bin/env python3
"""Owner's loopback-only login-code viewer. No codes or credentials in logs."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
import secrets
import subprocess
import webbrowser


def fetch_codes():
    root = Path(__file__).resolve().parents[4]
    common = subprocess.run(['git', '-C', str(root), 'rev-parse', '--git-common-dir'],
                            capture_output=True, check=True).stdout.decode().strip()
    git_directory = Path(common)
    if not git_directory.is_absolute():
        git_directory = root / git_directory
    original = git_directory.resolve().parent
    command = ['ssh', '-i', str(Path.home() / '.ssh/id_ed25519'),
               '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'UserKnownHostsFile=' + str(original / '.tmp/test-crm-known-hosts'),
               'root@5.183.191.222',
               '/opt/php74/bin/php /root/gpm-ts-update/demo-tools-20261110-v05/read_login_inbox.php']
    result = subprocess.run(command, capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError('PRIVATE_INBOX_UNAVAILABLE')
    return json.loads(result.stdout)['rows']


def make_handler(secret, fetch=fetch_codes):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            if self.headers.get('Host') != host or self.path != '/' + secret:
                self.send_error(404)
                return
            if self.headers.get('Origin') not in [None, 'http://' + host]:
                self.send_error(403)
                return
            try:
                rows = fetch()
                table = ''.join('<tr><td>' + html.escape(str(row['email'])) + '</td><td><code>'
                                + html.escape(str(row['code'])) + '</code></td></tr>' for row in rows)
                body = ('<!doctype html><meta charset="utf-8"><title>Тестовые коды входа TS</title>'
                        '<style>body{font:18px system-ui;max-width:850px;margin:48px auto;padding:20px}'
                        'td{padding:14px;border-bottom:1px solid #ddd}code{font-size:24px}</style>'
                        '<h1>Тестовые коды входа TS</h1><p>Для ts.workstaffcrm.ru. Сначала введите свой '
                        'логин и пароль на сайте, затем обновите это окно. Email не отправляется. '
                        'Код виден здесь 10 минут и перестает работать после успешного входа.</p>'
                        '<p><a href="">Обновить</a></p><table><tr><th>Учетная запись</th><th>Код</th></tr>'
                        + (table or '<tr><td colspan="2">Новых кодов нет.</td></tr>') + '</table>').encode()
                self.send_response(200)
            except Exception:
                body = 'Закрытый ящик пока недоступен. Проверьте SSH-доступ и установку защиты TS.'.encode()
                self.send_response(503)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main():
    token = secrets.token_urlsafe(32)
    with HTTPServer(('127.0.0.1', 0), make_handler(token)) as server:
        webbrowser.open('http://127.0.0.1:' + str(server.server_port) + '/' + token)
        print('Открыто локальное окно тестовых кодов TS. Для закрытия нажмите Ctrl+C.')
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()

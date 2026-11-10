"""Synthetic SMTP loopback inside NEW network namespace; never real email/DB."""
from pathlib import Path
import json
from email import policy
from email.parser import BytesParser
import os
import socketserver
import subprocess
import threading

PRIVATE = Path('/root/gpm-ts-update/20261110-demo-06')


def main():
    if os.readlink('/proc/self/ns/net') == os.readlink('/proc/1/ns/net'):
        raise RuntimeError('PRIVATE_NETWORK_REQUIRED')
    subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True, capture_output=True)
    receipts = []
    class Smtp(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(10)
            def reply(value):
                self.wfile.write(value + b'\r\n')
                self.wfile.flush()
            reply(b'220 fixture ESMTP')
            recipients = []
            while True:
                line = self.rfile.readline(65536)
                if not line:
                    return
                command = line.upper()
                if command.startswith((b'EHLO', b'HELO')):
                    reply(b'250-fixture')
                    reply(b'250 AUTH PLAIN LOGIN')
                elif command.startswith(b'AUTH PLAIN'):
                    reply(b'235 OK')
                elif command.startswith(b'AUTH LOGIN'):
                    reply(b'334 VXNlcm5hbWU6')
                    self.rfile.readline()
                    reply(b'334 UGFzc3dvcmQ6')
                    self.rfile.readline()
                    reply(b'235 OK')
                elif command.startswith(b'RCPT TO:'):
                    recipients.append(line.strip().lower())
                    reply(b'250 OK')
                elif command.startswith(b'DATA'):
                    reply(b'354 End with dot')
                    body = bytearray()
                    while True:
                        part = self.rfile.readline(65536)
                        if part == b'.\r\n':
                            break
                        if not part or len(body) > 1000000:
                            raise RuntimeError('BOUNDED_FIXTURE_MESSAGE_REQUIRED')
                        body.extend(part)
                    mime = BytesParser(policy=policy.default).parsebytes(bytes(body))
                    rendered = b'\n'.join(part.get_payload(decode=True) or b'' for part in mime.walk() if not part.is_multipart())
                    receipts.append({'correct_single_recipient': recipients == [b'rcpt to:<fixture@example.invalid>'],
                                     'original_code_rendered': b'synthetic-fixture-code' in rendered,
                                     'not_business_mail': b'ordinary mail' not in rendered})
                    recipients = []
                    reply(b'250 OK')
                elif command.startswith(b'QUIT'):
                    reply(b'221 bye')
                    return
                else:
                    reply(b'250 OK')
    with socketserver.ThreadingTCPServer(('127.0.0.1', 0), Smtp) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        environment = dict(os.environ, GPM_TS_DEMO_REHEARSAL='1', GPM_FIXTURE_SMTP_PORT=str(server.server_address[1]))
        result = subprocess.run(['/opt/php74/bin/php', str(Path(__file__).with_name('transport_acceptance.php'))],
                                env=environment, capture_output=True, timeout=60)
        server.shutdown()
    if result.returncode:
        (PRIVATE / 'private-transport-error.log').write_bytes(result.stderr + result.stdout)
        raise RuntimeError('TRANSPORT_ACCEPTANCE_FAILED_DETAILS_WITHHELD')
    report = json.loads(result.stdout)
    (PRIVATE / 'synthetic-smtp-receipt.json').write_text(json.dumps(receipts))
    if len(receipts) != 1 or not all(receipts[0].values()):
        raise RuntimeError('ONLY_ONE_CORRECT_LOGIN_MESSAGE_REQUIRED')
    report['synthetic_smtp'] = {'messages': 1, **receipts[0], 'outside_namespace_deliveries': 0}
    report['checks'].append('only_original_login_email_reaches_isolated_smtp')
    (PRIVATE / 'transport-acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'checks': len(report['checks']), 'synthetic_smtp_messages': 1,
                      'outside_namespace_deliveries': 0, 'live_files_changed': False}))


if __name__ == '__main__':
    main()

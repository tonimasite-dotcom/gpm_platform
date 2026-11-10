#!/usr/bin/env python3
"""Local viewer access control tests with synthetic challenges, no SSH calls."""
from http.client import HTTPConnection
from http.server import HTTPServer
import json
import threading
from local_login_inbox import make_handler


def main():
    calls = []
    def fetch():
        calls.append(True)
        return [{'email': '<script>fixture</script>@example.invalid', 'code': '<fixture&code>'}]
    with HTTPServer(('127.0.0.1', 0), make_handler('synthetic-access-token', fetch)) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host = '127.0.0.1:' + str(server.server_port)
        checks = []
        def request(path, headers=None):
            client = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            client.request('GET', path, headers=headers or {})
            response = client.getresponse()
            result = response.status, dict(response.getheaders()), response.read().decode()
            client.close()
            return result
        try:
            status, headers, body = request('/wrong-token')
            assert status == 404 and not calls
            checks.append('unknown_token_rejected_without_ssh')
            status, headers, body = request('/synthetic-access-token', {'Host': 'evil.invalid'})
            assert status == 404 and not calls
            checks.append('foreign_host_rejected_without_ssh')
            status, headers, body = request('/synthetic-access-token', {'Host': host, 'Origin': 'https://evil.invalid'})
            assert status == 403 and not calls
            checks.append('cross_origin_rejected_without_ssh')
            status, headers, body = request('/synthetic-access-token')
            assert status == 200 and len(calls) == 1
            checks.append('valid_loopback_session_reads_private_inbox')
            assert '<script>fixture</script>' not in body and '&lt;script&gt;' in body and '&lt;fixture&amp;code&gt;' in body
            checks.append('mailbox_content_html_escaped')
            assert headers['Cache-Control'] == 'no-store' and headers['Referrer-Policy'] == 'no-referrer'
            checks.append('codes_not_cached_or_sent_in_referrer')
            assert headers['X-Frame-Options'] == 'DENY' and "default-src 'none'" in headers['Content-Security-Policy']
            checks.append('framing_and_external_resources_blocked')
            print(json.dumps({'passed': True, 'checks': checks, 'real_ssh_calls': False, 'real_codes_used': False}))
        finally:
            server.shutdown()
            thread.join(timeout=2)


if __name__ == '__main__':
    main()

import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:gpm_platform/registration/registration_preview_api.dart';

void main() {
  test(
    'server token only in browser, revisions and idempotency survive lost reply',
    () async {
      String? stored;
      final keys = <String?>[];
      final requests = <http.Request>[];
      var completeCalls = 0;
      final transport = MockClient((request) async {
        requests.add(request);
        final path = request.url.path;
        if (path.endsWith('/complete')) {
          completeCalls++;
          keys.add(request.headers['Idempotency-Key']);
          if (completeCalls == 1) throw Exception('Synthetic lost reply');
        }
        if (request.method != 'POST' || !path.endsWith('/sessions')) {
          expect(
            request.headers['Authorization'],
            'Bearer reg_preview_synthetic_token',
          );
        }
        return http.Response(
          jsonEncode({
            'preview': true,
            'registration_id': 'reg_synthetic',
            'revision': request.method == 'PATCH' ? 1 : 0,
            'session_token': 'reg_preview_synthetic_token',
            'answers': {'first_name': 'Иван'},
            if (path.endsWith('/complete')) 'profile_id': 'preview_synthetic',
          }),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      });
      final api = RegistrationPreviewApi(
        client: transport,
        readCredentials: () => stored,
        writeCredentials: (value) => stored = value,
      );
      await api.load();
      expect(jsonDecode(stored!), {
        'id': 'reg_synthetic',
        'token': 'reg_preview_synthetic_token',
      });
      await api.save({'first_name': 'Иван'});
      expect(jsonDecode(requests.last.body), {
        'expected_revision': 0,
        'answers': {'first_name': 'Иван'},
      });
      await expectLater(
        api.complete(),
        throwsA(isA<RegistrationPreviewError>()),
      );
      await api.complete();
      expect(keys[0], keys[1]);
      expect(keys[0]!.length, greaterThanOrEqualTo(16));
      final restored = RegistrationPreviewApi(
        client: transport,
        readCredentials: () => stored,
        writeCredentials: (_) {},
      );
      await restored.load();
      expect(requests.last.method, 'GET');
      expect(requests.last.url.path.endsWith('/sessions/reg_synthetic'), true);
    },
  );
}

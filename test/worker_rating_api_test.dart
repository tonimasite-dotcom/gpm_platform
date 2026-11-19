import 'dart:convert';
import 'dart:io';

import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

void main() {
  test('rating API preserves authentication, slash order numbers, versions and retry identity', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    final requests = <Map<String, dynamic>>[];
    var conflict = false;
    server.listen((request) async {
      request.response.headers.contentType = ContentType.json;
      if (request.uri.path == '/app-api/auth/login') {
        final body = jsonDecode(await utf8.decoder.bind(request).join()) as Map;
        request.response.write(jsonEncode({
          'access_token': 'synthetic-test-token',
          'username': body['username'], 'role': body['role'],
        }));
      } else {
        final text = await utf8.decoder.bind(request).join();
        final body = text.isEmpty ? null : jsonDecode(text);
        requests.add({
          'path': request.uri.path, 'query': request.uri.queryParameters,
          'method': request.method, 'body': body,
          'authorization': request.headers.value('authorization'),
        });
        if (conflict) {
          request.response.statusCode = 409;
          request.response.write(jsonEncode({'detail': 'Оценка изменилась. Обновите историю'}));
        } else if (request.method == 'GET') {
          request.response.write(jsonEncode({
            'summary': {'rating': 2, 'review_count': 1, 'positive_percent': 100},
            'history': [], 'has_more': false, 'next_offset': 0,
          }));
        } else {
          request.response.write(jsonEncode({
            'success': true,
            'order': {'id': '033/25', 'external_order_id': '033/25', 'status': 'CONVERTED'},
          }));
        }
      }
      await request.response.close();
    });
    dotenv.testLoad(fileInput:
      'GPM_APP_MODE=api\nGPM_APP_API_URL=http://${server.address.host}:${server.port}\n');
    final api = GpmApiService();
    await api.login(username: 'worker', password: 'Synthetic password!', role: 'worker');
    await api.getWorkerRatingHistory(orderId: '033/25', offset: 20, limit: 10);
    expect(requests.last['path'], '/app-api/me/rating');
    expect(requests.last['query'], {'order_id': '033/25', 'offset': '20', 'limit': '10'});
    await api.appealWorkerRating(
      orderId: '033/25', reason: 'Прошу проверить факты',
      expectedRevision: 2, requestId: 'stable-appeal',
    );
    expect(requests.last['path'], '/app-api/me/order-rating-appeals/033%2F25');
    expect(requests.last['body'], {
      'reason': 'Прошу проверить факты', 'expected_revision': 2, 'request_id': 'stable-appeal',
    });
    await api.login(username: 'logist', password: 'Synthetic password!', role: 'logist');
    await api.getWorkerRatingHistory(workerId: 'worker-id-1', orderId: '033/25');
    expect(requests.last['path'], '/app-api/logist/workers/worker-id-1/rating');
    final payload = {
      'worker_id': 'worker-id-1', 'result': 'success', 'reason': 'Факты проверены',
      'expected_revision': 2, 'request_id': 'stable-correction',
    };
    for (var attempt = 0; attempt < 2; attempt++) {
      await api.correctWorkerRating(
        orderId: '033/25', workerId: 'worker-id-1', result: 'success',
        reason: 'Факты проверены', expectedRevision: 2, requestId: 'stable-correction',
      );
      expect(requests.last['path'], '/app-api/me/order-rating-corrections/033%2F25');
      expect(requests.last['body'], payload);
      expect(requests.last['authorization'], 'Bearer synthetic-test-token');
    }
    await api.resolveWorkerRatingAppeal(
      orderId: '033/25', workerId: 'worker-id-1', reason: 'Оценка подтверждена',
      expectedRevision: 2, requestId: 'stable-resolution',
    );
    expect(requests.last['path'], '/app-api/me/order-rating-resolutions/033%2F25');
    await api.completeOrderWithResult(
      orderId: '033/25', workerId: 'worker-id-1', result: 'fail',
      reason: 'Проверенная причина',
    );
    expect((requests.last['body'] as Map)['reason'], 'Проверенная причина');
    conflict = true;
    await expectLater(api.correctWorkerRating(
      orderId: '033/25', workerId: 'worker-id-1', result: 'good',
      reason: 'Другая причина', expectedRevision: 1, requestId: 'stale',
    ), throwsA(isA<StateError>().having((error) => error.message, 'message', contains('Оценка изменилась'))));
  });
}

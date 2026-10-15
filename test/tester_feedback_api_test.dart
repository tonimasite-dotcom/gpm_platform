import 'dart:convert';
import 'dart:io';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

void main() {
  for (final entry in {
    'success': 1,
    'fail': -2,
    'good': -1,
    'excellent': 2,
  }.entries) {
    test(
      'demo rating ${entry.key} matches server rules and is counted once',
      () async {
        dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
        final api = GpmApiService();
        final initial =
            (await api.getWorkerProfile(GpmApiService.demoWorkerId))!['rating']
                as int;
        await api.updateOrderStatus('1002', 'DONE_PENDING');
        final first = await api.completeOrderWithResult(
          orderId: '1002',
          workerId: GpmApiService.demoWorkerId,
          result: entry.key,
        );
        final repeated = await api.completeOrderWithResult(
          orderId: '1002',
          workerId: GpmApiService.demoWorkerId,
          result: entry.key,
        );
        expect(first['success'], true);
        expect(repeated['already_recorded'], true);
        expect(
          (await api.getWorkerProfile(GpmApiService.demoWorkerId))!['rating'],
          initial + entry.value,
        );
      },
    );
  }

  test(
    'API sends every approved worker result, including a CRM number with slash',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      final requests = <Map<String, dynamic>>[];
      server.listen((request) async {
        request.response.headers.contentType = ContentType.json;
        if (request.uri.path == '/app-api/auth/login') {
          request.response.write(
            jsonEncode({
              'access_token': 'test-token',
              'username': 'logist',
              'role': 'logist',
            }),
          );
        } else {
          final body = jsonDecode(await utf8.decoder.bind(request).join());
          requests.add({
            'path': request.uri.path,
            'method': request.method,
            'body': body,
          });
          request.response.write(
            jsonEncode({
              'success': true,
              'order': {
                'id': '033/25',
                'external_order_id': '033/25',
                'status': 'CONVERTED',
              },
            }),
          );
        }
        await request.response.close();
      });
      dotenv.testLoad(
        fileInput:
            'GPM_APP_MODE=api\nGPM_APP_API_URL=http://${server.address.host}:${server.port}\n',
      );
      final api = GpmApiService();
      await api.login(
        username: 'logist',
        password: 'synthetic-password',
        role: 'logist',
      );
      for (final result in ['success', 'fail', 'good', 'excellent']) {
        final response = await api.completeOrderWithResult(
          orderId: '033/25',
          workerId: 'actual-worker',
          result: result,
        );
        expect(response['success'], true);
        expect(requests.last, {
          'path': '/app-api/me/order-reviews/033%2F25',
          'method': 'POST',
          'body': {'worker_id': 'actual-worker', 'result': result},
        });
      }
    },
  );

  test('API loads actual worker data and staff updates only employment', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    Map<String, dynamic>? patchBody;
    String? patchPath;
    Map<String, String>? directoryQuery;
    String? directoryAuthorization;
    server.listen((request) async {
      request.response.headers.contentType = ContentType.json;
      if (request.uri.path == '/app-api/auth/login') {
        request.response.write(
          jsonEncode({
            'access_token': 'test-token',
            'username': 'logist',
            'role': 'logist',
          }),
        );
      } else if (request.uri.path == '/app-api/logist/workers') {
        directoryQuery = request.uri.queryParameters;
        directoryAuthorization = request.headers.value('Authorization');
        request.response.write(
          jsonEncode({
            'workers': [
              {'id': 'server-worker', 'display_name': 'Серверный исполнитель'},
            ],
            'has_more': false,
            'next_offset': 21,
          }),
        );
      } else if (request.uri.path.startsWith('/app-api/logist/workers/')) {
        if (request.method == 'PATCH') {
          patchPath = request.uri.path;
          patchBody = jsonDecode(await utf8.decoder.bind(request).join());
        }
        request.response.write(
          jsonEncode({
            'profile': {
              'display_name': 'Серверный исполнитель',
              'nationality': true,
              'identity_status': 'verified',
              'employment_type': 'state',
            },
          }),
        );
      } else {
        // A real API order that happens to share a demo ID has no demo replies.
        request.response.write(
          jsonEncode({
            'orders': [
              {'id': '1001', 'applications': []},
            ],
          }),
        );
      }
      await request.response.close();
    });
    dotenv.testLoad(
      fileInput:
          'GPM_APP_MODE=api\nGPM_APP_API_URL=http://${server.address.host}:${server.port}\n',
    );
    final api = GpmApiService();
    await api.login(
      username: 'logist',
      password: 'synthetic-password',
      role: 'logist',
    );
    await api.getOrders();
    expect(await api.getApplicationsForOrder('1001'), isEmpty);
    final directory = await api.getWorkerDirectory(
      query: ' Ёлкин +7 ',
      offset: 20,
    );
    expect(directoryQuery, {'q': 'Ёлкин +7', 'offset': '20', 'limit': '20'});
    expect(directoryAuthorization, 'Bearer test-token');
    expect((directory['workers'] as List).single['id'], 'server-worker');
    final worker = await api.getWorkerProfile('server-worker');
    expect(worker?['display_name'], 'Серверный исполнитель');
    expect(worker?['nationality'], isTrue);
    await api.updateWorkerEmployment('server-worker', 'state');
    expect(patchPath, '/app-api/logist/workers/server-worker');
    expect(patchBody, {'employment_type': 'state'});
    await api.updateWorkerStaffProfile('server-worker', {
      'nationality': false,
      'employment_type': 'contract',
    });
    expect(patchBody, {'nationality': false, 'employment_type': 'contract'});
  });
}

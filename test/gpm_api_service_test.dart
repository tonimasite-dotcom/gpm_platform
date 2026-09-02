import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

void main() {
  test('draft update keeps CRM order number with slash in route', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    String? patchPath;
    Map<String, dynamic>? patchBody;
    server.listen((request) async {
      request.response.headers.contentType = ContentType.json;
      if (request.uri.path == '/app-api/auth/login') {
        request.response.write(
          jsonEncode({
            'access_token': 'draft-access-token',
            'username': 'logist',
            'role': 'logist',
          }),
        );
      } else if (request.method == 'PATCH') {
        patchPath = request.uri.path;
        patchBody = jsonDecode(await utf8.decoder.bind(request).join());
        request.response.write(jsonEncode({'success': true, 'order': {}}));
      } else if (request.uri.path == '/app-api/me/orders') {
        request.response.write(jsonEncode({'orders': []}));
      }
      await request.response.close();
    });

    dotenv.testLoad(
      fileInput:
          'GPM_APP_MODE=api\n'
          'GPM_APP_API_URL=http://${server.address.host}:${server.port}\n',
    );
    final api = GpmApiService();
    await api.login(
      username: 'logist',
      password: 'synthetic-password',
      role: 'logist',
    );

    final result = await api.updateOrderDraft('033/25', {
      'city': 'Москва',
      'workers_count': 2,
    });

    expect(result['success'], isTrue);
    expect(patchPath, '/app-api/me/orders/033/25');
    expect(patchBody?['city'], 'Москва');
    expect(patchBody?['workers_count'], 2);
  });

  test('API worker orders preserve server-owned worker metadata', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    server.listen((request) async {
      request.response.headers.contentType = ContentType.json;
      if (request.uri.path == '/app-api/auth/login') {
        request.response.write(
          jsonEncode({
            'access_token': 'test-access-token',
            'username': 'worker',
            'role': 'worker',
          }),
        );
      } else {
        request.response.write(
          jsonEncode({
            'orders': [
              {
                'id': 'server-order-1',
                'status': 'IN_PROCESS',
                'assigned_count': 1,
                'worker_application_status': 'APPROVED',
                'is_assigned_to_worker': true,
              },
            ],
          }),
        );
      }
      await request.response.close();
    });

    dotenv.testLoad(
      fileInput:
          'GPM_APP_MODE=api\n'
          'GPM_APP_API_URL=http://${server.address.host}:${server.port}\n',
    );
    final api = GpmApiService();
    final login = await api.login(
      username: 'worker',
      password: 'synthetic-password',
      role: 'worker',
    );

    final orders = await api.getOrdersForWorker(GpmApiService.demoWorkerId);

    expect(login['success'], isTrue);
    expect(orders, hasLength(1));
    expect(orders.single['worker_application_status'], 'APPROVED');
    expect(orders.single['is_assigned_to_worker'], isTrue);
    expect(orders.single['assigned_count'], 1);
  });

  test(
    'closing recruitment keeps slash order id and requests IN_PROCESS',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      String? patchPath;
      Map<String, dynamic>? patchBody;
      server.listen((request) async {
        request.response.headers.contentType = ContentType.json;
        if (request.uri.path == '/app-api/auth/login') {
          request.response.write(
            jsonEncode({
              'access_token': 'close-recruitment-token',
              'username': 'logist',
              'role': 'logist',
            }),
          );
        } else if (request.method == 'PATCH') {
          patchPath = request.uri.path;
          patchBody = jsonDecode(await utf8.decoder.bind(request).join());
          request.response.write(
            jsonEncode({
              'success': true,
              'order': {'id': '001/26', 'status': 'IN_PROCESS'},
            }),
          );
        } else {
          request.response.write(jsonEncode({'orders': []}));
        }
        await request.response.close();
      });

      dotenv.testLoad(
        fileInput:
            'GPM_APP_MODE=api\n'
            'GPM_APP_API_URL=http://${server.address.host}:${server.port}\n',
      );
      final api = GpmApiService();
      await api.login(
        username: 'logist',
        password: 'synthetic-password',
        role: 'logist',
      );

      final result = await api.closeOrderRecruitment('001/26');

      expect(result['success'], isTrue);
      expect(patchPath, '/app-api/me/orders/001/26');
      expect(patchBody, {'status': 'IN_PROCESS'});
    },
  );

  test('worker verification sends private attachment only to backend', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    Map<String, dynamic>? submittedBody;
    server.listen((request) async {
      request.response.headers.contentType = ContentType.json;
      if (request.uri.path == '/app-api/auth/login') {
        request.response.write(
          jsonEncode({
            'access_token': 'verification-access-token',
            'username': 'worker',
            'role': 'worker',
          }),
        );
      } else if (request.uri.path == '/app-api/me/verifications/identity') {
        submittedBody = jsonDecode(await utf8.decoder.bind(request).join());
        request.response.write(
          jsonEncode({
            'submission': {
              'submission_id': 'synthetic-submission',
              'status': 'pending',
            },
          }),
        );
      }
      await request.response.close();
    });

    dotenv.testLoad(
      fileInput:
          'GPM_APP_MODE=api\n'
          'GPM_APP_API_URL=http://${server.address.host}:${server.port}\n',
    );
    final api = GpmApiService();
    await api.login(
      username: 'worker',
      password: 'synthetic-password',
      role: 'worker',
    );
    final bytes = Uint8List.fromList([0xff, 0xd8, 0xff, 0x00]);

    final submission = await api.submitMyVerification(
      verificationType: 'identity',
      data: {
        'full_name': 'Синтетический Исполнитель',
        'passport_series': '0000',
        'passport_number': '000000',
      },
      attachmentBytes: bytes,
      attachmentName: 'passport.jpg',
      attachmentMediaType: 'image/jpeg',
    );

    expect(submission['status'], 'pending');
    expect(submittedBody?['attachment']?['filename'], 'passport.jpg');
    expect(
      base64Decode(submittedBody?['attachment']?['base64'] as String),
      bytes,
    );
  });
}

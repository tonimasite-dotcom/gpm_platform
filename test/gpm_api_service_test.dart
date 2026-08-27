import 'dart:convert';
import 'dart:io';

import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

void main() {
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
}

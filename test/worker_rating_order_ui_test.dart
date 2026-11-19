import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/client/client_orders_screen.dart';
import 'package:gpm_platform/screens/logist/logist_orders_screen.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'package:gpm_platform/widgets/worker_rating.dart';

import 'worker_rating_v2_test.dart' show RatingUiApi;

class RatingOrderUiApi extends RatingUiApi {
  final order = <String, dynamic>{
    'id': 'job-1', 'external_order_id': 'job-1',
    'title': 'Неоцененная заявка', 'status': 'DONE_PENDING',
    'address': 'Тестовый адрес', 'city': 'Москва',
    'scheduled_at': '2026-11-20T12:00:00Z', 'created_at': '2026-11-19T12:00:00Z',
    'workers_count': 1, 'hours': 4, 'price_per_hour': 450,
    'assigned_worker_ids': ['worker-1'],
    'worker_reviews': <String, dynamic>{},
    'applications': [
      {'id': 'application-1', 'worker_id': 'worker-1', 'worker_name': 'Тестовый рабочий',
        'status': 'APPROVED', 'worker': {'display_name': 'Тестовый рабочий',
          'rating': 2, 'rating_summary': {'rating': 2, 'review_count': 1, 'positive_percent': 100}}},
    ],
  };
  final disputedOrder = <String, dynamic>{
    'id': 'job-2', 'title': 'Оспоренная заявка', 'status': 'CONVERTED',
    'address': 'Тестовый адрес', 'workers_count': 1, 'hours': 4,
    'assigned_worker_ids': ['worker-2'],
    'worker_reviews': {
      'worker-2': {'result': 'fail', 'rating_delta': -2,
        'appeals': [{'status': 'open', 'reason': 'Прошу проверить факты'}]},
    },
  };

  @override
  Future<List<Map<String, dynamic>>> getOrders() async => [
    Map<String, dynamic>.from(order), Map<String, dynamic>.from(disputedOrder),
  ];

  @override
  Future<Map<String, dynamic>?> getOrderById(String orderId) async =>
      Map<String, dynamic>.from(orderId == 'job-1' ? order : disputedOrder);

  @override
  Future<List<Map<String, dynamic>>> getApplicationsForOrder(String orderId) async =>
      (order['applications'] as List).map((item) => Map<String, dynamic>.from(item as Map)).toList();

  @override
  Future<Map<String, dynamic>> getOrderAttendance(String orderId) async => {
    'order_id': orderId, 'verifier_mode': 'authenticated_client', 'attendance': [],
  };

  @override
  Future<Map<String, dynamic>> completeOrderWithResult({
    required String orderId, required String workerId, required String result, String reason = '',
  }) async {
    (order['worker_reviews'] as Map)[workerId] = {
      'result': result, 'rating_delta': workerResultDeltas[result],
      'reason': reason, 'revision': 1, 'appeals': [],
    };
    return {'success': true, 'order': Map<String, dynamic>.from(order)};
  }

  @override
  Future<bool> updateOrderStatus(String leadId, String newStatus) async {
    statusCalls++;
    order['status'] = newStatus;
    return true;
  }
}

void main() {
  late RatingOrderUiApi api;
  setUp(() {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    api = RatingOrderUiApi();
    app.gpmApi = api;
  });

  Future<void> tap(WidgetTester tester, Finder finder) async {
    if (finder.evaluate().isEmpty) {
      await tester.scrollUntilVisible(finder, 180, scrollable: find.byType(Scrollable).first);
    }
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  testWidgets('completed but unrated and appealed orders remain in separate queues', (tester) async {
    api.order['status'] = 'CONVERTED';
    await tester.pumpWidget(MaterialApp(theme: buildGpmTheme(),
      home: const Scaffold(body: LogistOrdersScreen())));
    await tester.pumpAndSettle();
    await tap(tester, find.text('Без оценки'));
    expect(find.text('Неоцененная заявка'), findsOneWidget);
    expect(find.text('Оспоренная заявка'), findsNothing);
    await tap(tester, find.text('Оспоренные'));
    expect(find.text('Оспоренная заявка'), findsOneWidget);
    expect(find.text('Неоцененная заявка'), findsNothing);
    expect(api.statusCalls, 0);
  });

  testWidgets('review does not accept work; separate explicit confirmation completes it', (tester) async {
    await tester.pumpWidget(MaterialApp(theme: buildGpmTheme(),
      home: LogistOrderDetailsScreen(order: api.order, onUpdate: () {})));
    await tester.pumpAndSettle();
    await tap(tester, find.text('Справился хорошо'));
    await tester.tap(find.text('Сохранить оценку'));
    await tester.pumpAndSettle();
    expect(api.order['status'], 'DONE_PENDING');
    expect(api.statusCalls, 0);
    await tap(tester, find.text('Принять выполненную работу'));
    expect(api.statusCalls, 0);
    await tester.tap(find.text('Принять работу'));
    await tester.pumpAndSettle();
    expect(api.order['status'], 'CONVERTED');
    expect(api.statusCalls, 1);
  });

  testWidgets('client sees assigned worker general score without internal rating actions', (tester) async {
    api.order['created_by_role'] = 'client';
    await tester.pumpWidget(MaterialApp(theme: buildGpmTheme(),
      home: const ClientOrderDetailsScreen(orderId: 'job-1')));
    await tester.pumpAndSettle();
    if (find.textContaining('Рейтинг: 2').evaluate().isEmpty) {
      await tester.scrollUntilVisible(find.textContaining('Рейтинг: 2'), 180,
        scrollable: find.byType(Scrollable).first);
    }
    expect(find.textContaining('Рейтинг: 2'), findsOneWidget);
    expect(find.textContaining('Оценок: 1'), findsOneWidget);
    expect(find.text('Исправить оценку'), findsNothing);
    expect(find.text('Оспорить оценку'), findsNothing);
  });
}

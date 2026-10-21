import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/logist/worker_profile_review_screen.dart';
import 'package:gpm_platform/screens/logist/logist_orders_screen.dart';
import 'package:gpm_platform/screens/worker/worker_orders_screen.dart';
import 'package:gpm_platform/screens/worker/worker_profile_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/utils/order_display.dart';

class _ServerWorkerApi extends GpmApiService {
  @override
  bool get isApiMode => true;

  @override
  Future<List<Map<String, dynamic>>> getOrdersForWorker(
    String workerId,
  ) async => [
    {
      'id': 'rf-server-order',
      'title': 'Заказ для РФ',
      'national': 'yes',
      'status': 'PROCESSED',
      'workers_count': 1,
      'hours': 4,
    },
  ];

  @override
  Map<String, dynamic>? getWorkerProfileSync(String workerId) => null;
}

class _ProfileApi extends GpmApiService {
  final bool recorded;
  Map<String, dynamic>? saved;

  _ProfileApi({required this.recorded});

  @override
  bool get isApiMode => true;

  @override
  Future<Map<String, dynamic>> getMyProfile() async => {
    'display_name': 'Исполнитель',
    'nationality': true,
    'nationality_recorded': recorded,
  };

  @override
  Future<Map<String, dynamic>?> getWorkerProfile(String workerId) async => {
    'display_name': 'Исполнитель',
    'nationality': true,
    'employment_type': 'contract',
  };

  @override
  Future<Map<String, dynamic>> updateWorkerStaffProfile(
    String workerId,
    Map<String, dynamic> patch,
  ) async {
    saved = patch;
    return patch;
  }
}

class _ReviewApi extends _ProfileApi {
  _ReviewApi() : super(recorded: true);

  final order = <String, dynamic>{
    'id': 'review-order',
    'status': 'DONE_PENDING',
    'assigned_worker_ids': ['first-worker', 'second-worker'],
    'worker_reviews': <String, dynamic>{},
  };
  Map<String, String>? reviewed;

  @override
  bool get isApiMode => true;

  @override
  Future<Map<String, dynamic>?> getOrderById(String orderId) async => order;

  @override
  Future<List<Map<String, dynamic>>> getApplicationsForOrder(
    String orderId,
  ) async => [
    for (final id in ['first-worker', 'second-worker'])
      {
        'id': 'application-$id',
        'worker_id': id,
        'status': 'APPROVED',
        'worker': {
          'display_name': id == 'first-worker'
              ? 'Первый рабочий'
              : 'Второй рабочий',
        },
      },
  ];

  @override
  Future<Map<String, dynamic>> getOrderAttendance(String orderId) async => {
    'attendance': [],
  };

  @override
  Future<Map<String, dynamic>> completeOrderWithResult({
    required String orderId,
    required String workerId,
    required String result,
  }) async {
    reviewed = {'worker_id': workerId, 'result': result};
    (order['worker_reviews'] as Map)[workerId] = {'result': result};
    return {'success': true, 'order': order};
  }
}

void main() {
  testWidgets('logist rates the selected worker with the new labels', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    final api = _ReviewApi();
    app.gpmApi = api;
    await tester.pumpWidget(
      MaterialApp(
        home: LogistOrderDetailsScreen(order: api.order, onUpdate: () {}),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Нейтрально'), findsNothing);
    expect(find.text('Справился хорошо'), findsNWidgets(2));
    final secondWorkerRating = find.text('Справился хорошо').last;
    await tester.ensureVisible(secondWorkerRating);
    await tester.tap(secondWorkerRating);
    await tester.pumpAndSettle();
    expect(api.reviewed, {'worker_id': 'second-worker', 'result': 'excellent'});
    expect(find.text('Оценка: Справился хорошо'), findsOneWidget);
    expect(find.text('Справился хорошо'), findsOneWidget);
  });

  for (final recorded in [false, true]) {
    testWidgets('worker citizenship control respects recorded=$recorded', (
      tester,
    ) async {
      dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
      app.gpmApi = _ProfileApi(recorded: recorded);
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: WorkerProfileScreen())),
      );
      await tester.pumpAndSettle();
      final citizenship = tester.widget<SegmentedButton<bool>>(
        find.byType(SegmentedButton<bool>).first,
      );
      expect(citizenship.onSelectionChanged == null, recorded);
      expect(citizenship.selected, recorded ? {true} : isEmpty);
    });
  }

  testWidgets('logist opens profile from an application and saves staff data', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    final api = _ReviewApi();
    app.gpmApi = api;
    await tester.pumpWidget(
      MaterialApp(
        home: LogistOrderDetailsScreen(order: api.order, onUpdate: () {}),
      ),
    );
    await tester.pumpAndSettle();
    final profileButton = find.text('Профиль и данные').first;
    await tester.ensureVisible(profileButton);
    await tester.tap(profileButton);
    await tester.pumpAndSettle();
    expect(find.byType(WorkerProfileReviewScreen), findsOneWidget);
    await tester.tap(find.byType(DropdownButtonFormField<bool>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Не РФ').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Штатный исполнитель').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Сохранить'));
    await tester.pumpAndSettle();
    expect(api.saved, {'nationality': false, 'employment_type': 'state'});
    expect(find.byType(WorkerProfileReviewScreen), findsNothing);
  });

  testWidgets(
    'server-visible RF orders do not depend on the local profile cache',
    (tester) async {
      dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
      app.gpmApi = _ServerWorkerApi();
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: WorkerOrdersScreen())),
      );
      await tester.pumpAndSettle();
      expect(find.text('Заказ для РФ'), findsOneWidget);
    },
  );
  test(
    'worker payment uses performer rate and divides legacy total budgets',
    () {
      expect(
        workerPaymentLines({
          'price_per_hour': 600,
          'hours': 6,
          'min_time': 4,
          'workers_count': 2,
          'individual_price': 15000,
        }),
        contains('Предполагаемый заработок: 3600 ₽'),
      );
      expect(
        workerPaymentLines({'workers_count': 2, 'individual_price': 4400}),
        ['Ставка не указана', 'Предполагаемый заработок: 2200 ₽'],
      );
    },
  );

  testWidgets('worker sees the same pay before and after opening an order', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = GpmApiService();
    final order = <String, dynamic>{
      'id': 'payment-order',
      'title': 'Проверка оплаты',
      'status': 'PROCESSED',
      'workers_count': 2,
      'hours': 4,
      'min_time': 4,
      'price_per_hour': 600,
    };
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OrdersList(orders: [order], emptyText: '', onChanged: () {}),
        ),
      ),
    );
    expect(find.text('Ставка: 600 ₽/ч'), findsOneWidget);
    expect(find.text('Предполагаемый заработок: 2400 ₽'), findsOneWidget);
    await tester.tap(find.text('Проверка оплаты'));
    await tester.pumpAndSettle();
    expect(find.text('Ставка: 600 ₽/ч'), findsOneWidget);
    expect(find.text('Предполагаемый заработок: 2400 ₽'), findsOneWidget);
    expect(find.text('Завершить заказ'), findsNothing);
  });
}

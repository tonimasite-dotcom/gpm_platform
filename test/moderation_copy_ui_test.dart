import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/attendance/order_attendance.dart';
import 'package:gpm_platform/screens/logist/logist_orders_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';

class VersionApi extends GpmApiService {
  @override
  Future<List<Map<String, dynamic>>> getApplicationsForOrder(String id) async => [];
}

Map<String, dynamic> order({bool pending = true, int rate = 750}) => {
  'id': pending ? 'gpm-review-synthetic' : 'TEST/26',
  'external_order_id': pending ? 'gpm-review-synthetic' : 'TEST/26',
  'title': 'Заявка № TEST/26',
  'status': pending ? 'NEW' : 'PROCESSED',
  'source': 'external',
  'source_system': 'workstaff',
  'city': 'Москва',
  'address': 'Тестовый адрес',
  'workers_count': 2,
  'hours': 4,
  'price_per_hour': rate,
  if (pending) ...{
    'moderation_parent_id': 'TEST/26',
    'published_copy_id': 'TEST/26',
    'has_published_copy': true,
  },
};

void main() {
  setUp(() {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = VersionApi();
  });

  Future<void> open(WidgetTester tester, Map<String, dynamic> value) async {
    await tester.pumpWidget(MaterialApp(
      theme: buildGpmTheme(),
      home: Scaffold(body: SingleChildScrollView(child: LogistOrderCard(
        key: const ValueKey('stable-order-card'),
        order: value,
        onUpdate: () {},
      ))),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets('pending replacement clearly marks the existing published copy', (tester) async {
    await open(tester, order());
    expect(find.text('Есть опубликованная копия'), findsOneWidget);
    await tester.tap(find.text('Заявка № TEST/26'));
    await tester.pumpAndSettle();
    expect(find.text('Есть опубликованная копия'), findsOneWidget);
    expect(find.textContaining('gpm-review-'), findsNothing);
    expect(find.byType(OrderAttendancePanel), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('published card refreshes replaced content without changing identity', (tester) async {
    await open(tester, order(pending: false, rate: 500));
    expect(find.text('Есть опубликованная копия'), findsNothing);
    expect(find.text('Ставка: 500 ₽/ч'), findsOneWidget);
    await open(tester, order(pending: false, rate: 820));
    expect(find.text('Ставка: 820 ₽/ч'), findsOneWidget);
    expect(find.text('Ставка: 500 ₽/ч'), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });
}

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/worker/worker_orders_screen.dart';
import 'package:gpm_platform/screens/logist/logist_orders_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

class _OrdersApi extends GpmApiService {
  _OrdersApi(this.orders);
  final List<Map<String, dynamic>> orders;
  int calls = 0;
  @override
  Future<List<Map<String, dynamic>>> getOrders() async { calls++; return orders; }
  @override
  Future<List<Map<String, dynamic>>> getOrdersForWorker(String workerId) => getOrders();
  @override
  Future<List<Map<String, dynamic>>> getApplicationsForOrder(String orderId) async => [];
}

Future<void> _open(WidgetTester tester, Widget screen, {Size size = const Size(900, 1800), double scale = 1}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(
    locale: const Locale('ru', 'RU'),
    supportedLocales: const [Locale('ru', 'RU')],
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    builder: (context, child) => MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)), child: child!,
    ),
    home: Scaffold(body: screen),
  ));
  await tester.pumpAndSettle();
}

String _stamp(DateTime value) => value.toUtc().toIso8601String();
String _date(DateTime value) => '${value.day.toString().padLeft(2, '0')}.${value.month.toString().padLeft(2, '0')}.${value.year}';

Future<void> _period(WidgetTester tester, DateTime from, DateTime to) async {
  await tester.tap(find.byKey(const Key('logist_publication_dates')));
  await tester.pumpAndSettle();
  await tester.enterText(find.widgetWithText(TextField, 'С даты'), _date(from));
  await tester.enterText(find.widgetWithText(TextField, 'По дату'), _date(to));
  await tester.tap(find.text('Применить'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('worker defaults to today and day choices compose with tabs without reload', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final tomorrow = DateTime(now.year, now.month, now.day + 1);
    final api = _OrdersApi([
      {'id': 'today', 'title': 'Сегодняшняя', 'status': 'PROCESSED', 'scheduled_at': _stamp(today), 'created_at': _stamp(tomorrow)},
      {'id': 'tomorrow', 'title': 'Завтрашняя', 'status': 'PROCESSED', 'scheduled_at': _stamp(tomorrow), 'created_at': _stamp(today)},
      {'id': 'missing', 'title': 'Без даты', 'status': 'PROCESSED'},
      {'id': 'active', 'title': 'Назначенная', 'status': 'IN_PROCESS', 'is_assigned_to_worker': true, 'scheduled_at': _stamp(today)},
      {'id': 'history', 'title': 'Завершенная', 'status': 'CONVERTED', 'is_assigned_to_worker': true, 'scheduled_at': _stamp(tomorrow)},
    ]);
    app.gpmApi = api;
    await _open(tester, const WorkerOrdersScreen());
    expect(tester.widgetList<ChoiceChip>(find.byType(ChoiceChip)).map((chip) => (chip.label as Text).data),
        ['Сегодня', 'Завтра', 'Все']);
    expect(find.text('Сегодняшняя'), findsOneWidget);
    expect(find.text('Завтрашняя'), findsNothing);
    expect(find.text('Без даты'), findsNothing);
    await tester.tap(find.text('Мои'));
    await tester.pumpAndSettle();
    expect(find.text('Назначенная'), findsOneWidget);
    await tester.tap(find.text('Завтра'));
    await tester.pumpAndSettle();
    expect(find.text('Назначенная'), findsNothing);
    await tester.tap(find.text('История'));
    await tester.pumpAndSettle();
    expect(find.text('Завершенная'), findsOneWidget);
    await tester.tap(find.text('Доступные'));
    await tester.tap(find.text('Все'));
    await tester.pumpAndSettle();
    expect(find.text('Сегодняшняя'), findsOneWidget);
    expect(find.text('Завтрашняя'), findsOneWidget);
    expect(find.text('Без даты'), findsOneWidget);
    expect(api.calls, 1);
  });

  testWidgets('logist filters publication date with status, reset and cancel', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    final today = DateTime(2026, 11, 20);
    final tomorrow = DateTime(2026, 11, 21);
    final api = _OrdersApi([
      {'id': 'today', 'title': 'Опубликована сегодня', 'status': 'NEW', 'created_at': _stamp(today), 'scheduled_at': _stamp(tomorrow)},
      {'id': 'tomorrow', 'title': 'Опубликована завтра', 'status': 'PROCESSED', 'created_at': _stamp(tomorrow), 'scheduled_at': _stamp(today)},
      {'id': 'missing', 'title': 'Без публикации', 'status': 'NEW'},
    ]);
    app.gpmApi = api;
    await _open(tester, const LogistOrdersScreen());
    await _period(tester, today, today);
    expect(find.text('Опубликована сегодня'), findsOneWidget);
    expect(find.text('Опубликована завтра'), findsNothing);
    expect(find.text('Без публикации'), findsNothing);
    await tester.tap(find.text('Одобрен'));
    await tester.pumpAndSettle();
    expect(find.text('Нет заказов по выбранным фильтрам'), findsOneWidget);
    await tester.tap(find.text('Сбросить даты'));
    await tester.pumpAndSettle();
    expect(find.text('Опубликована завтра'), findsOneWidget);
    expect(find.text('Опубликована сегодня'), findsNothing);
    await tester.tap(find.byType(ChoiceChip).first);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('logist_publication_dates')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Отмена'));
    await tester.pumpAndSettle();
    expect(find.text('Опубликована сегодня'), findsOneWidget);
    expect(find.text('Опубликована завтра'), findsOneWidget);
    expect(find.text('Без публикации'), findsOneWidget);
    expect(api.calls, 1);
  });

  testWidgets('invalid reversed range is rejected and can be cancelled', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    app.gpmApi = _OrdersApi([]);
    await _open(tester, const LogistOrdersScreen());
    await _period(tester, DateTime(2026, 11, 21), DateTime(2026, 11, 20));
    expect(find.text('Конец периода раньше начала'), findsOneWidget);
    await tester.tap(find.text('Отмена'));
    await tester.pumpAndSettle();
    expect(find.text('Сбросить даты'), findsNothing);
  });

  testWidgets('date controls fit narrow screen with large text', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    app.gpmApi = _OrdersApi([]);
    await _open(tester, const WorkerOrdersScreen(), size: const Size(320, 568), scale: 2);
    expect(find.text('Сегодня'), findsOneWidget);
    expect(find.text('Завтра'), findsOneWidget);
    expect(find.text('Все'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    app.gpmApi = _OrdersApi([]);
    await _open(tester, const LogistOrdersScreen(), size: const Size(320, 568), scale: 2);
    expect(find.byKey(const Key('logist_publication_dates')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

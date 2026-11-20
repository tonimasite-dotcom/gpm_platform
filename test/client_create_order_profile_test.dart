import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/client/client_create_order_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

class _ProfileApi extends GpmApiService {
  _ProfileApi(this.profile, {this.role = 'client'});
  Future<Map<String, dynamic>> profile;
  final String role;
  int profileCalls = 0;
  final orders = <Map<String, dynamic>>[];

  @override
  String get currentRole => role;

  @override
  Future<Map<String, dynamic>> getMyProfile() {
    profileCalls++;
    return profile;
  }

  @override
  Future<List<Map<String, dynamic>>> suggestAddresses({
    required String query,
    String city = '',
  }) async => throw StateError('Synthetic unavailable address provider');

  @override
  Future<Map<String, dynamic>> createOrder({
    required String title,
    required String address,
    required int workersCount,
    required int hours,
    required String description,
    required String clientEmail,
    required String clientPhone,
    String? scheduledAt,
    String? city,
    String source = 'manual',
    String? externalOrderId,
    String? metro,
    String? national,
    int? minTime,
    int? pricePerHour,
    int? priceRegular,
    int? priceState,
    int? individualPrice,
    int? legalPrice,
    String? nationality,
    String? workerCategory,
    String? workMode,
    String? shiftDescription,
    String? telegramUsername,
    String? timezone,
    String? additionalInfo,
    String? addressStreet,
    String? addressNumber,
    double? addressLat,
    double? addressLon,
  }) async {
    orders.add({
      'email': clientEmail,
      'phone': clientPhone,
      'individual': individualPrice,
      'legal': legalPrice,
      'rate': pricePerHour,
      'address': address,
    });
    return {'success': true, 'orderId': 'synthetic-order'};
  }
}

Future<void> _open(WidgetTester tester, _ProfileApi api) async {
  dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
  app.gpmApi = api;
  await tester.pumpWidget(
    const MaterialApp(home: Scaffold(body: ClientCreateOrderScreen())),
  );
  await tester.pump();
}

Future<void> _enter(WidgetTester tester, String label, String text) async {
  final field = find.widgetWithText(TextFormField, label);
  await tester.ensureVisible(field);
  await tester.enterText(field, text);
}

Future<void> _fill(WidgetTester tester) async {
  final tomorrow = DateTime.now().add(const Duration(days: 1));
  await _enter(tester, 'Дата',
      '${tomorrow.day.toString().padLeft(2, '0')}.${tomorrow.month.toString().padLeft(2, '0')}.${tomorrow.year}');
  await _enter(tester, 'Время', '19:30');
  await _enter(tester, 'Вид груза', 'Коробки');
  await _enter(tester, 'Описание работ', 'Перенести коробки');
  await _enter(tester, 'Общий вес, кг', '100');
  await _enter(tester, 'Вес одной единицы, кг', '10');
  await _enter(tester, 'Адрес', 'Москва, тестовый адрес, 1');
  await tester.pump(const Duration(milliseconds: 700));
  await tester.pump();
  await _enter(tester, 'Ставка исполнителя в час, ₽', '700');
}

Future<void> _submit(WidgetTester tester) async {
  final button = find.widgetWithText(ElevatedButton, 'Создать заказ');
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();
}

void main() {
  for (final type in ['legal', 'individual']) {
    testWidgets('$type client profile supplies estimate, contacts and budget',
        (tester) async {
      dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
      final api = _ProfileApi(Future.value({
        'client_type': type,
        'email': ' client@example.test ',
        'phone': ' +70000000000 ',
      }));
      await _open(tester, api);
      await tester.pumpAndSettle();
      expect(find.text('Рекомендация: от ${type == 'legal' ? 5200 : 4400} ₽'), findsOneWidget);
      await _fill(tester);
      await _enter(tester, type == 'legal' ? 'Бюджет по счету, ₽' : 'Бюджет к оплате, ₽', '8000');
      await _submit(tester);
      expect(api.orders, hasLength(1));
      expect(api.orders.single, {
        'email': 'client@example.test',
        'phone': '+70000000000',
        'individual': type == 'individual' ? 8000 : null,
        'legal': type == 'legal' ? 8000 : null,
        'rate': 700,
        'address': 'Москва, тестовый адрес, 1',
      });
    });
  }

  testWidgets('delayed profile blocks submission and does not guess client type',
      (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    final pending = Completer<Map<String, dynamic>>();
    final api = _ProfileApi(pending.future);
    await _open(tester, api);
    expect(find.text('Бюджет к оплате, ₽'), findsNothing);
    final button = find.widgetWithText(ElevatedButton, 'Создать заказ');
    expect(tester.widget<ElevatedButton>(button).onPressed, isNull);
    await _enter(tester, 'Описание работ', 'Сохранить введенный текст');
    pending.complete({'client_type': 'legal'});
    await tester.pumpAndSettle();
    expect(find.text('Бюджет по счету, ₽'), findsOneWidget);
    expect(tester.widget<TextFormField>(find.widgetWithText(TextFormField, 'Описание работ')).controller!.text,
        'Сохранить введенный текст');
    expect(tester.widget<ElevatedButton>(button).onPressed, isNotNull);
    expect(api.orders, isEmpty);
  });

  testWidgets('profile error blocks submission until successful retry',
      (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    final pending = Completer<Map<String, dynamic>>();
    final api = _ProfileApi(pending.future);
    await _open(tester, api);
    pending.completeError(StateError('Synthetic profile failure'));
    await tester.pumpAndSettle();
    expect(find.text('Не удалось загрузить профиль клиента'), findsOneWidget);
    final button = find.widgetWithText(ElevatedButton, 'Создать заказ');
    expect(tester.widget<ElevatedButton>(button).onPressed, isNull);
    api.profile = Future.value({'client_type': 'legal'});
    final retry = find.text('Повторить загрузку профиля');
    await tester.ensureVisible(retry);
    await tester.tap(retry);
    await tester.pumpAndSettle();
    expect(api.profileCalls, 2);
    expect(find.text('Бюджет по счету, ₽'), findsOneWidget);
    expect(tester.widget<ElevatedButton>(button).onPressed, isNotNull);
    expect(api.orders, isEmpty);
  });

  testWidgets('profile response after leaving form is ignored', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    final pending = Completer<Map<String, dynamic>>();
    await _open(tester, _ProfileApi(pending.future));
    await tester.pumpWidget(const MaterialApp(home: SizedBox()));
    pending.complete({'client_type': 'legal'});
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('logist does not load own profile as customer or show budget',
      (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    final api = _ProfileApi(Future.value({
      'client_type': 'legal', 'email': 'staff@example.test',
    }), role: 'logist');
    await _open(tester, api);
    await tester.pumpAndSettle();
    expect(api.profileCalls, 0);
    expect(find.text('Предполагаемая стоимость'), findsNothing);
    await _fill(tester);
    await _submit(tester);
    expect(api.orders.single['email'], isEmpty);
    expect(api.orders.single['phone'], isEmpty);
    expect(api.orders.single['legal'], isNull);
    expect(api.orders.single['individual'], isNull);
  });
}

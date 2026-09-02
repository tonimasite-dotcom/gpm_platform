import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/screens/orders/order_draft_edit_screen.dart';

void main() {
  testWidgets('CRM draft editor exposes fields but keeps order number fixed', (
    tester,
  ) async {
    final scheduledAt = DateTime.now()
        .add(const Duration(days: 2))
        .toUtc()
        .toIso8601String();

    await tester.pumpWidget(
      MaterialApp(
        home: OrderDraftEditScreen(
          order: {
            'id': '033/25',
            'external_order_id': '033/25',
            'source': 'external',
            'status': 'NEW',
            'title': 'Заявка № 033/25',
            'city': 'Москва',
            'scheduled_at': scheduledAt,
            'address': 'г Москва, ул. Тестовая, 1',
            'workers_count': 2,
            'hours': 4,
            'min_time': 4,
            'national': 'every',
            'work_mode': 'rate',
          },
        ),
      ),
    );

    expect(find.text('Редактирование заявки'), findsOneWidget);
    expect(find.textContaining('Заявка № 033/25'), findsWidgets);
    expect(
      find.textContaining('Номер и назначенный логист не изменяются'),
      findsOneWidget,
    );
    expect(find.widgetWithText(TextFormField, 'Город'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, 'Адрес'), findsOneWidget);
    expect(
      find.byKey(const Key('order-nationality-field'), skipOffstage: false),
      findsOneWidget,
    );
  });
}

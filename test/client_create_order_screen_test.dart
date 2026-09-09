import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/client/client_create_order_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

void main() {
  testWidgets('order form requires an explicit worker citizenship choice', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = GpmApiService();

    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ClientCreateOrderScreen())),
    );
    await tester.pumpAndSettle();

    expect(find.text('Гражданство исполнителя:'), findsOneWidget);
    expect(find.text('Только РФ'), findsOneWidget);
    expect(find.text('Любое'), findsOneWidget);
    expect(find.text('Не РФ'), findsNothing);
  });

  testWidgets('order form exposes work description and split weight fields', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = GpmApiService();

    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ClientCreateOrderScreen())),
    );
    await tester.pumpAndSettle();

    expect(
      find.widgetWithText(TextFormField, 'Описание работ'),
      findsOneWidget,
    );
    expect(find.widgetWithText(TextFormField, 'Общий вес, кг'), findsOneWidget);
    expect(
      find.widgetWithText(TextFormField, 'Вес одной единицы, кг'),
      findsOneWidget,
    );
    expect(
      find.widgetWithText(TextFormField, 'Вес, кг (необязательно)'),
      findsNothing,
    );
  });
}

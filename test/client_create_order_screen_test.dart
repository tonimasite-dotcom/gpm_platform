import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/client/client_create_order_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

class _RoleApi extends GpmApiService {
  _RoleApi(this.role);
  final String role;

  @override
  String get currentRole => role;
}

void main() {
  testWidgets('payment mode switches the rate field and validates shift rate', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = _RoleApi('logist');
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ClientCreateOrderScreen())),
    );
    await tester.pumpAndSettle();

    expect(find.text('Предполагаемая стоимость'), findsNothing);
    expect(find.text('Бюджет к оплате, ₽'), findsNothing);
    final hourly = find.widgetWithText(
      TextFormField,
      'Ставка исполнителя в час, ₽',
    );
    await tester.ensureVisible(hourly);
    await tester.enterText(hourly, '700');
    await tester.ensureVisible(find.text('Смена'));
    await tester.tap(find.text('Смена'));
    await tester.pumpAndSettle();

    final shift = find.widgetWithText(
      TextFormField,
      'Ставка исполнителя за смену, ₽',
    );
    expect(shift, findsOneWidget);
    expect(hourly, findsNothing);
    expect(tester.widget<TextFormField>(shift).controller!.text, '700');
    await tester.ensureVisible(shift);
    await tester.enterText(shift, '0');
    tester.state<FormState>(find.byType(Form)).validate();
    await tester.pump();
    expect(find.text('Укажите положительную ставку за смену'), findsOneWidget);

    await tester.ensureVisible(find.text('Ставка в час'));
    await tester.tap(find.text('Ставка в час'));
    await tester.pumpAndSettle();
    expect(hourly, findsOneWidget);
    expect(shift, findsNothing);
  });

  testWidgets('client retains the estimated cost section', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = _RoleApi('client');
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ClientCreateOrderScreen())),
    );
    await tester.pumpAndSettle();
    expect(find.text('Предполагаемая стоимость'), findsOneWidget);
    expect(find.text('Бюджет к оплате, ₽'), findsOneWidget);
  });

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

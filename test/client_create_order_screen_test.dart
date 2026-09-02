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
    expect(find.text('РФ'), findsOneWidget);
    expect(find.text('Не РФ'), findsOneWidget);
    expect(find.text('Право на законную работу'), findsNothing);
  });
}

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/worker/worker_dashboard_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

void main() {
  testWidgets('worker dashboard renders the stat row without overflow', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = GpmApiService();

    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: WorkerDashboardScreen())),
    );
    await tester.pumpAndSettle();

    expect(find.text('Кабинет исполнителя'), findsOneWidget);
    expect(find.text('Активные заявки'), findsOneWidget);
    expect(find.text('Рейтинг'), findsOneWidget);
    expect(find.text('Выплаты'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

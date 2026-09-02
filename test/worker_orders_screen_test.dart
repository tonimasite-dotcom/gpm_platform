import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/worker/worker_orders_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

void main() {
  testWidgets('worker who responded sees recruitment as completed', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    final api = GpmApiService();
    app.gpmApi = api;
    await api.updateOrderStatus('1001', 'PROCESSED');
    await api.applyToOrder(
      orderId: '1001',
      workerId: GpmApiService.demoWorkerId,
      workerName: GpmApiService.demoWorkerName,
    );

    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: WorkerOrdersScreen())),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byType(Tab).at(1));
    await tester.pumpAndSettle();

    expect(find.text('👷 Набор исполнителей завершен'), findsNWidgets(2));
    expect(find.textContaining('/2 чел.'), findsNothing);
    expect(find.textContaining('/3 чел.'), findsNothing);
  });
}

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
    expect(find.text('Приведи друга — получи бонус'), findsOneWidget);
    expect(find.byIcon(Icons.card_giftcard_rounded), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('worker referral promo opens a mobile contact sheet', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = GpmApiService();

    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: WorkerDashboardScreen())),
    );
    await tester.pumpAndSettle();

    final promoCard = find.byKey(const Key('worker_referral_promo_card'));
    await tester.ensureVisible(promoCard);
    await tester.tap(promoCard);
    await tester.pumpAndSettle();

    expect(find.byType(BottomSheet), findsOneWidget);
    expect(find.text('Пригласить друга'), findsOneWidget);
    expect(find.text('@GPMHRDaria'), findsOneWidget);
    expect(find.text('@GpmHREkaterina'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('worker referral promo opens a dialog on a wide screen', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(900, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = GpmApiService();

    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: WorkerDashboardScreen())),
    );
    await tester.pumpAndSettle();

    final promoCard = find.byKey(const Key('worker_referral_promo_card'));
    await tester.ensureVisible(promoCard);
    await tester.tap(promoCard);
    await tester.pumpAndSettle();

    expect(find.byType(Dialog), findsOneWidget);
    expect(find.text('@GPMHRDaria'), findsOneWidget);
    expect(find.text('@GpmHREkaterina'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

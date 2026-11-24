import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/worker/worker_home_screen.dart';
import 'package:gpm_platform/screens/worker/worker_dashboard_screen.dart';
import 'package:gpm_platform/screens/worker/worker_profile_screen.dart';
import 'package:gpm_platform/screens/worker/worker_sbp_payout.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'support/load_test_fonts.dart';

class _WorkerUxApi extends GpmApiService {
  Map<String, dynamic> profile = {
    'display_name': 'Тестовый исполнитель',
    'full_name': 'Тестовый исполнитель',
    'phone': '+79000000000',
    'phone_number': '+79000000000',
    'nationality': true,
    'cities': ['Санкт-Петербург'],
    'payout_method': '',
    'identity_status': 'not_submitted',
    'npd_status': 'not_submitted',
  };
  int applications = 0;
  int saves = 0;
  bool failSave = false;
  @override
  Future<Map<String, dynamic>?> getWorkerProfile(String workerId) async =>
      Map.from(profile);
  @override
  Future<bool> updateWorkerProfile(
    String workerId,
    Map<String, dynamic> data,
  ) async {
    saves++;
    if (failSave) return false;
    profile.addAll(data);
    return true;
  }

  @override
  Future<List<Map<String, dynamic>>> getOrdersForWorker(
    String workerId,
  ) async => [
    {
      'id': 'synthetic-home-order',
      'title': 'Разгрузить коробки на складе',
      'status': 'PROCESSED',
      'scheduled_at': DateTime.now().toIso8601String(),
      'city': 'Санкт-Петербург',
      'address': 'Тестовый адрес, 1',
      'workers_count': 2,
      'assigned_count': 0,
      'hours': 4,
      'price_per_hour': 650,
      'min_time': 4,
      if (applications > 0) 'worker_application_status': 'PENDING',
    },
  ];
  @override
  Future<Map<String, dynamic>> applyToOrder({
    required String orderId,
    required String workerId,
    required String workerName,
  }) async {
    applications++;
    return {'success': true};
  }
}

void size(
  WidgetTester tester,
  double width,
  double height, {
  double scale = 1,
}) {
  tester.view.physicalSize = Size(width, height);
  tester.view.devicePixelRatio = 1;
  tester.platformDispatcher.textScaleFactorTestValue = scale;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
}

Future<void> shot(WidgetTester tester, GlobalKey key, String name) async {
  await tester.runAsync(() async {
    final render =
        key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final image = await render.toImage(pixelRatio: 1);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    final file = File('build/worker-ux-shots/$name.png');
    await file.parent.create(recursive: true);
    await file.writeAsBytes(bytes!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  setUpAll(loadMobileTestFonts);
  setUp(() {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
  });
  testWidgets(
    'orders open first with a compact promo and one direct application',
    (tester) async {
      size(tester, 390, 844);
      final api = _WorkerUxApi();
      app.gpmApi = api;
      final key = GlobalKey();
      await tester.pumpWidget(
        RepaintBoundary(
          key: key,
          child: MaterialApp(debugShowCheckedModeBanner: false, 
            theme: buildGpmTheme(),
            home: const WorkerHomeScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(WorkerDashboardScreen), findsNothing);
      expect(find.text('Разгрузить коробки на складе'), findsOneWidget);
      expect(find.text('Откликнуться на заказ'), findsOneWidget);
      final promo = find.byKey(const Key('worker_referral_promo_card'));
      expect(tester.getSize(promo).height, lessThanOrEqualTo(72));
      expect(
        tester.getRect(promo).top,
        lessThan(tester.getRect(find.text('Сегодня')).top),
      );
      await shot(tester, key, 'orders_390');
      await tester.tap(find.text('Откликнуться на заказ'));
      await tester.pumpAndSettle();
      expect(api.applications, 1);
      expect(find.text('Отклик отправлен логисту'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'SBP editor searches banks, saves own phone and reloads details',
    (tester) async {
      size(tester, 390, 844);
      final api = _WorkerUxApi();
      app.gpmApi = api;
      final key = GlobalKey();
      await tester.pumpWidget(
        RepaintBoundary(
          key: key,
          child: MaterialApp(debugShowCheckedModeBanner: false, 
            theme: buildGpmTheme(),
            home: const Scaffold(body: WorkerProfileScreen()),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('СБП'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('СБП'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const Key('worker_sbp_details')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('worker_sbp_details')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('worker_sbp_bank')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('worker_sbp_bank_search')),
        'Сбер',
      );
      await tester.pumpAndSettle();
      expect(find.text('Сбербанк'), findsOneWidget);
      await shot(tester, key, 'bank_search_390');
      await tester.tap(find.text('Сбербанк'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('worker_sbp_use_profile_phone')));
      await tester.pumpAndSettle();
      await shot(tester, key, 'payout_editor_390');
      await tester.tap(find.byKey(const Key('worker_sbp_save')));
      await tester.pumpAndSettle();
      expect(api.saves, 1);
      expect(api.profile['payout_method'], 'sbp');
      expect(api.profile['payout_bank_id'], '100000000111');
      expect(api.profile['payout_phone'], '+79000000000');
      expect(api.profile['phone'], '+79000000000');
      expect(find.byKey(const Key('worker_sbp_save')), findsNothing);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      await tester.pumpWidget(
        MaterialApp(debugShowCheckedModeBanner: false, 
          theme: buildGpmTheme(),
          home: const Scaffold(body: WorkerProfileScreen()),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Сбербанк'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets('failed payout save keeps the editor data for retry', (
    tester,
  ) async {
    size(tester, 390, 844);
    var attempts = 0;
    final key = GlobalKey();
    const details = SbpPayoutDetails(
      bankId: '100000000111',
      bankName: 'Сбербанк',
      phone: '+79000000000',
    );
    await tester.pumpWidget(
      RepaintBoundary(
        key: key,
        child: MaterialApp(debugShowCheckedModeBanner: false, 
          theme: buildGpmTheme(),
          home: Scaffold(
            body: Builder(
              builder: (context) => TextButton(
                onPressed: () => showWorkerSbpPayout(
                  context,
                  details: details,
                  profilePhone: '+79000000000',
                  onSave: (value) async {
                    attempts++;
                    if (attempts == 1) {
                      throw StateError('synthetic unavailable');
                    }
                  },
                ),
                child: const Text('Открыть реквизиты'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Открыть реквизиты'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('worker_sbp_save')));
    await tester.pumpAndSettle();
    expect(
      find.text('Не удалось сохранить реквизиты. Повторите попытку'),
      findsOneWidget,
    );
    expect(find.text('Сбербанк'), findsOneWidget);
    expect(find.text('+7 (900) 000-00-00'), findsOneWidget);
    await tester.tap(find.byKey(const Key('worker_sbp_save')));
    await tester.pumpAndSettle();
    expect(attempts, 2);
    expect(find.byKey(const Key('worker_sbp_save')), findsNothing);
  });
  for (final config in [(320.0, 700.0, 2.0), (900.0, 800.0, 1.0)]) {
    testWidgets('payout dialog fits ${config.$1}px at scale ${config.$3}', (
      tester,
    ) async {
      size(tester, config.$1, config.$2, scale: config.$3);
      final key = GlobalKey();
      await tester.pumpWidget(
        RepaintBoundary(
          key: key,
          child: MaterialApp(debugShowCheckedModeBanner: false, 
            theme: buildGpmTheme(),
            home: Scaffold(
              body: Builder(
                builder: (context) => TextButton(
                  onPressed: () => showWorkerSbpPayout(
                    context,
                    details: const SbpPayoutDetails(
                      bankId: '',
                      bankName: '',
                      phone: '',
                    ),
                    profilePhone: '+79000000000',
                    onSave: (_) async {},
                  ),
                  child: const Text('Открыть реквизиты'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Открыть реквизиты'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await shot(tester, key, 'payout_${config.$1.toInt()}_${config.$3}');
    });
  }
}

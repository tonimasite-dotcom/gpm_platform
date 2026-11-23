import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/screens/worker/worker_home_screen.dart';
import 'package:gpm_platform/screens/worker/worker_referral_promo.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'package:gpm_platform/widgets/gpm_logo.dart';
import 'support/load_test_fonts.dart';
import 'chat_threads_screen_test.dart' show ThreadsService;

double contrast(Color first, Color second) {
  final a = first.computeLuminance();
  final b = second.computeLuminance();
  return ((a > b ? a : b) + .05) / ((a > b ? b : a) + .05);
}

class _DesignOrdersApi extends GpmApiService {
  final bool empty;
  _DesignOrdersApi({this.empty = false});
  @override
  Future<Map<String, dynamic>?> getWorkerProfile(String workerId) async => {
    'display_name': 'Тестовый исполнитель',
    'phone': '+79000000000',
    'payout_method': 'card',
    'card_last4': '1234',
    'cities': ['Санкт-Петербург'],
  };
  @override
  Future<List<Map<String, dynamic>>> getOrdersForWorker(
    String workerId,
  ) async => empty
      ? []
      : [
          {
            'id': 'synthetic-gold-order',
            'title': 'Разгрузить коробки на складе',
            'status': 'PROCESSED',
            'created_at': DateTime.now().toIso8601String(),
            'scheduled_at': DateTime.now().toIso8601String(),
            'city': 'Санкт-Петербург',
            'address': 'Тестовый адрес, 1',
            'workers_count': 2,
            'assigned_count': 0,
            'hours': 4,
            'price_per_hour': 650,
          },
        ];
}

Future<void> captureGold(
  WidgetTester tester,
  GlobalKey key,
  String name,
) async {
  await tester.runAsync(() async {
    final boundary =
        key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final image = await boundary.toImage(pixelRatio: 1);
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    final file = File('build/gold-design-shots/$name.png');
    await file.parent.create(recursive: true);
    await file.writeAsBytes(data!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  setUpAll(loadMobileTestFonts);
  for (final audience in GpmAudience.values) {
    test(
      'enabled controls and selected text remain readable for ${audience.name}',
      () {
        final theme = buildGpmTheme(audience: audience);
        expect(
          theme.chipTheme.labelStyle!.fontFamily,
          theme.textTheme.labelLarge!.fontFamily,
        );
        expect(
          theme.chipTheme.secondaryLabelStyle!.fontFamily,
          theme.textTheme.labelLarge!.fontFamily,
        );
        final button = theme.filledButtonTheme.style!;
        final bg = button.backgroundColor!.resolve({});
        final fg = button.foregroundColor!.resolve({});
        expect(contrast(bg!, fg!), greaterThanOrEqualTo(4.5));
        final segment = theme.segmentedButtonTheme.style!;
        expect(
          contrast(
            segment.backgroundColor!.resolve({WidgetState.selected})!,
            segment.foregroundColor!.resolve({WidgetState.selected})!,
          ),
          greaterThanOrEqualTo(4.5),
        );
        expect(
          contrast(theme.tabBarTheme.labelColor!, GpmColors.surface),
          greaterThanOrEqualTo(4.5),
        );
        expect(
          contrast(theme.colorScheme.error, GpmColors.surface),
          greaterThanOrEqualTo(4.5),
        );
      },
    );
  }
  for (final config in [
    (390.0, 844.0, 1.0, false),
    (1280.0, 800.0, 1.0, true),
    (1280.0, 800.0, 1.0, false),
    (320.0, 700.0, 2.0, false),
  ]) {
    testWidgets(
      'gold worker screen ${config.$1}px text ${config.$3} empty ${config.$4}',
      (tester) async {
        tester.view.physicalSize = Size(config.$1, config.$2);
        tester.view.devicePixelRatio = 1;
        tester.platformDispatcher.textScaleFactorTestValue = config.$3;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
        app.gpmApi = _DesignOrdersApi(empty: config.$4);
        app.chatService = ThreadsService(app.gpmApi);
        final key = GlobalKey();
        await tester.pumpWidget(
          RepaintBoundary(
            key: key,
            child: MaterialApp(
              debugShowCheckedModeBanner: false,
              theme: buildGpmTheme(),
              home: Scaffold(
                appBar: AppBar(
                  titleSpacing: 12,
                  toolbarHeight: config.$3 > 1.4 ? 96 : 64,
                  title: const Row(
                    children: [
                      GpmLogoImage(width: 104),
                      SizedBox(width: 12),
                      Expanded(
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Chip(label: Text('Исполнитель')),
                        ),
                      ),
                    ],
                  ),
                ),
                body: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 1120),
                    child: const WorkerHomeScreen(),
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.runAsync(
          () => precacheImage(
            const AssetImage('assets/images/gpm_logo.png'),
            tester.element(find.byType(GpmLogoImage)),
          ),
        );
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(
          find.byKey(const Key('worker_referral_promo_cta')),
          findsOneWidget,
        );
        if (config.$3 == 1) {
          expect(
            tester
                .getSize(find.byKey(const Key('worker_referral_promo_card')))
                .height,
            lessThanOrEqualTo(96),
          );
        }
        await captureGold(
          tester,
          key,
          'worker_${config.$1.toInt()}_${config.$3}_${config.$4}',
        );
        // Exercise the actual tabs under the same app width and navigation.
        if (!config.$4) {
          final nav = find.byType(BottomNavigationBar);
          await tester.tap(
            find.descendant(of: nav, matching: find.text('Финансы')),
          );
          await tester.pumpAndSettle();
          expect(find.text('Доступно к выводу'), findsOneWidget);
          await captureGold(
            tester,
            key,
            'finance_${config.$1.toInt()}_${config.$3}',
          );
          expect(tester.takeException(), isNull);
          await tester.tap(
            find.descendant(of: nav, matching: find.text('Чаты')),
          );
          await tester.pumpAndSettle();
          expect(find.text('Поиск по всем чатам'), findsOneWidget);
          if (config.$1 > 1000) {
            expect(
              tester.getSize(find.byType(TextField)).width,
              greaterThan(1050),
            );
          }
          await captureGold(
            tester,
            key,
            'chats_${config.$1.toInt()}_${config.$3}',
          );
          expect(tester.takeException(), isNull);
          await tester.tap(
            find.descendant(of: nav, matching: find.text('Профиль')),
          );
          await tester.pumpAndSettle();
          await tester.ensureVisible(find.text('Счет (для самозанятых)'));
          await tester.pumpAndSettle();
          await tester.tap(find.text('Счет (для самозанятых)'));
          await tester.pumpAndSettle();
          await tester.ensureVisible(find.text('Счет для выплат'));
          await tester.pumpAndSettle();
          expect(find.textContaining('Самозанятым по умолчанию'), findsNothing);
          await tester.ensureVisible(find.text('Выплаты'));
          await tester.pumpAndSettle();
          await captureGold(
            tester,
            key,
            'profile_${config.$1.toInt()}_${config.$3}',
          );
          expect(tester.takeException(), isNull);
          await tester.tap(
            find.descendant(of: nav, matching: find.text('Заявки')),
          );
          await tester.pumpAndSettle();
        }
        await tester.tap(find.byKey(const Key('worker_referral_promo_cta')));
        await tester.pumpAndSettle();
        expect(find.text('@GPMHRDaria'), findsOneWidget);
        expect(find.text('@GpmHREkaterina'), findsOneWidget);
        expect(find.byType(WorkerReferralPromoCard), findsOneWidget);
        expect(tester.takeException(), isNull);
        if (config.$3 == 1) {
          await captureGold(
            tester,
            key,
            'referral_${config.$1.toInt()}_${config.$4}',
          );
        }
        await tester.pumpWidget(const SizedBox.shrink());
      },
    );
  }
}

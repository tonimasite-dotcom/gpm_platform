import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/ratings/worker_rating_screen.dart';
import 'package:gpm_platform/screens/client/client_orders_screen.dart';
import 'package:gpm_platform/screens/logist/logist_orders_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';

import '../test/worker_rating_v2_test.dart' show RatingUiApi;
import '../test/worker_rating_order_ui_test.dart' show RatingOrderUiApi;
import '../test/support/load_test_fonts.dart';

void main() {
  testWidgets('capture rating lifecycle screens on synthetic data', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    await tester.runAsync(loadMobileTestFonts);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetViewInsets);
    final output = Directory('rating-previews')..createSync();

    Future<GlobalKey> mount(Widget screen, GpmApiService api, Size size, {double scale = 1}) async {
      await tester.pumpWidget(const SizedBox.shrink());
      app.gpmApi = api;
      tester.view.physicalSize = size;
      tester.view.viewInsets = const FakeViewPadding();
      final key = GlobalKey();
      await tester.pumpWidget(RepaintBoundary(
        key: key,
        child: MaterialApp(
          theme: buildGpmTheme(),
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)),
            child: child!,
          ),
          home: screen,
        ),
      ));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      return key;
    }

    Future<void> see(Finder finder) async {
      if (finder.evaluate().isEmpty) {
        await tester.scrollUntilVisible(finder, 180, scrollable: find.byType(Scrollable).first);
      }
      await tester.ensureVisible(finder);
      await tester.pumpAndSettle();
    }

    Future<void> capture(GlobalKey key, String name) async {
      expect(tester.takeException(), isNull);
      await tester.runAsync(() async {
        final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
        final image = await boundary.toImage(pixelRatio: 1);
        final data = await image.toByteData(format: ui.ImageByteFormat.png);
        File('${output.path}/$name.png').writeAsBytesSync(data!.buffer.asUint8List());
        image.dispose();
      });
    }

    for (final staff in [false, true]) {
      for (final size in [const Size(320, 568), const Size(390, 844), const Size(1360, 800)]) {
        final key = await mount(WorkerRatingScreen(
          workerId: staff ? 'worker-1' : null,
          workerName: staff ? 'Тестовый рабочий' : null,
        ), RatingUiApi(), size);
        await capture(key, '${staff ? 'logist' : 'worker'}-${size.width.toInt()}');
      }
    }
    for (final size in [const Size(320, 568), const Size(390, 844)]) {
      final key = await mount(const WorkerRatingScreen(), RatingUiApi(), size, scale: 2);
      await capture(key, 'worker-${size.width.toInt()}-2x');
    }
    for (final size in [const Size(320, 568), const Size(390, 844), const Size(1360, 800)]) {
      final api = RatingOrderUiApi();
      api.order['created_by_role'] = 'client';
      final key = await mount(const ClientOrderDetailsScreen(orderId: 'job-1'), api, size);
      await see(find.textContaining('Рейтинг: 2'));
      await capture(key, 'client-${size.width.toInt()}');
    }
    for (final size in [const Size(390, 844), const Size(1360, 800)]) {
      final api = RatingOrderUiApi();
      final key = await mount(LogistOrderDetailsScreen(order: api.order, onUpdate: () {}), api, size);
      await see(find.text('Принять выполненную работу'));
      await capture(key, 'acceptance-${size.width.toInt()}');
    }
    for (final size in [const Size(320, 568), const Size(390, 844), const Size(1360, 800)]) {
      final key = await mount(const WorkerRatingScreen(workerId: 'worker-1',
        workerName: 'Тестовый рабочий'), RatingUiApi(), size, scale: size.width == 320 ? 2 : 1);
      await see(find.text('Исправить оценку'));
      await tester.tap(find.text('Исправить оценку'));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Справился хорошо').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextFormField), 'После проверки фактов ошибка исправлена');
      await tester.pumpAndSettle();
      await capture(key, 'correction-${size.width.toInt()}');
    }
    for (final size in [const Size(320, 568), const Size(390, 844)]) {
      final key = await mount(const WorkerRatingScreen(), RatingUiApi(), size, scale: size.width == 320 ? 2 : 1);
      await see(find.text('Оспорить оценку'));
      await tester.tap(find.text('Оспорить оценку'));
      await tester.pumpAndSettle();
      tester.view.viewInsets = const FakeViewPadding(bottom: 260);
      await tester.enterText(find.byType(TextFormField), 'Прошу проверить, работа была выполнена');
      await tester.pumpAndSettle();
      await capture(key, 'appeal-keyboard-${size.width.toInt()}');
    }
    for (final size in [const Size(390, 844), const Size(1360, 800)]) {
      final api = RatingUiApi();
      api.review = {
        'result': 'success', 'rating_delta': 1, 'revision': 2,
        'reason': 'После проверки оценка исправлена', 'reviewed_at': '2026-11-19T13:00:00Z',
        'revisions': [
          {'result': 'fail', 'rating_delta': -2, 'reason': 'Первоначальная оценка',
            'reviewed_at': '2026-11-19T12:00:00Z'},
          {'result': 'success', 'rating_delta': 1, 'reason': 'После проверки оценка исправлена',
            'reviewed_at': '2026-11-19T13:00:00Z'},
        ],
        'appeals': [
          {'revision': 1, 'reason': 'Прошу проверить выполнение', 'status': 'resolved',
            'decision': 'changed', 'resolution': 'Проверка подтвердила выполнение работы'},
        ],
      };
      final key = await mount(const WorkerRatingScreen(), api, size);
      await see(find.text('История изменений (2)'));
      await tester.tap(find.text('История изменений (2)'));
      await tester.pumpAndSettle();
      await capture(key, 'history-${size.width.toInt()}');
    }
    for (final size in [const Size(390, 844), const Size(1360, 800)]) {
      final api = RatingOrderUiApi();
      api.order['applications'] = [];
      api.order['assigned_workers'] = [
        {'id': 'worker-1', 'display_name': 'Тестовый рабочий', 'rating': 17,
          'rating_summary': {'rating': 17, 'review_count': 1,
            'positive_percent': 100, 'has_legacy_balance': true}},
      ];
      final key = await mount(const ClientOrderDetailsScreen(orderId: 'job-1'), api, size);
      await see(find.textContaining('Рейтинг: 17'));
      await capture(key, 'client-legacy-${size.width.toInt()}');
    }
    for (final label in ['Без оценки', 'Оспоренные']) {
      final key = await mount(const Scaffold(body: LogistOrdersScreen()),
        RatingOrderUiApi(), const Size(390, 844));
      await see(find.text(label));
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
      await capture(key, label == 'Без оценки' ? 'queue-unreviewed' : 'queue-appeals');
    }
    await tester.pumpWidget(const SizedBox.shrink());
  });
}

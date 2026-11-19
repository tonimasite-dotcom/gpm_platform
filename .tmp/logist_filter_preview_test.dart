import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/screens/logist/logist_orders_screen.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';

import '../test/support/load_test_fonts.dart';

class PreviewApi extends GpmApiService {
  bool empty = false;
  @override
  Future<List<Map<String, dynamic>>> getOrders() async => empty ? [] : [
    {
      'id': 'preview-001',
      'title': 'Заявка № DEMO-001',
      'address': 'Тестовый адрес, дом 7',
      'status': 'PROCESSED',
      'scheduled_at': '2026-11-20T12:00:00Z',
      'created_at': '2026-11-19T12:00:00Z',
      'workers_count': 2,
      'hours': 4,
      'assigned_worker_ids': <String>[],
      'worker_rate': 450,
    },
  ];

  @override
  Future<List<Map<String, dynamic>>> getApplicationsForOrder(String orderId) async => [];
}

void main() {
  testWidgets('capture order filters at mobile and desktop sizes', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    app.gpmApi = PreviewApi();
    await tester.runAsync(loadMobileTestFonts);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final output = Directory('filter-previews')..createSync();
    for (final size in [const Size(320, 568), const Size(390, 844), const Size(1360, 700)]) {
      for (final scale in [1.0, 2.0]) {
        app.gpmApi = PreviewApi()..empty = scale == 2;
        tester.view.physicalSize = size;
        final key = GlobalKey();
        await tester.pumpWidget(MaterialApp(
          theme: buildGpmTheme(),
          home: MediaQuery(
            data: MediaQueryData(size: size, textScaler: TextScaler.linear(scale)),
            child: RepaintBoundary(
              key: key,
              child: Scaffold(
                appBar: AppBar(title: const Text('GPM · Логист')),
                body: const LogistOrdersScreen(),
              ),
            ),
          ),
        ));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
        await tester.runAsync(() async {
          final image = await boundary.toImage(pixelRatio: 1);
          final data = await image.toByteData(format: ui.ImageByteFormat.png);
          File('${output.path}/orders-${size.width.toInt()}-${scale.toInt()}x.png')
              .writeAsBytesSync(data!.buffer.asUint8List());
          image.dispose();
        });
        await tester.ensureVisible(find.text('В работе'));
        await tester.tap(find.text('В работе'));
        await tester.pumpAndSettle();
        expect(find.text('Нет заказов со статусом "В работе"'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
      }
    }
  });
}

import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'package:gpm_platform/widgets/company_logist_crm_id_card.dart';
import 'support/load_test_fonts.dart';

void main() {
  setUpAll(loadMobileTestFonts);

  testWidgets('external logist has no CRM ID card', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildGpmTheme(),
        home: const Scaffold(body: CompanyLogistCrmIdCard()),
      ),
    );
    expect(find.textContaining('Ваш ID для CRM'), findsNothing);
    expect(find.byTooltip('Скопировать ID для CRM'), findsNothing);
  });

  testWidgets('employee can copy only the short CRM ID', (tester) async {
    Object? copied;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          copied = call.arguments;
        }
        return null;
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        null,
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildGpmTheme(),
        home: const Scaffold(body: CompanyLogistCrmIdCard(crmId: 1)),
      ),
    );
    expect(find.text('Ваш ID для CRM: #1'), findsOneWidget);
    await tester.tap(find.byTooltip('Скопировать ID для CRM'));
    await tester.pumpAndSettle();
    expect(copied, {'text': '#1'});
    expect(find.text('ID скопирован'), findsOneWidget);
  });

  for (final config in [
    (390.0, 600.0, 1.0),
    (900.0, 600.0, 1.0),
    (320.0, 700.0, 2.0),
  ]) {
    testWidgets('CRM card fits ${config.$1}px scale ${config.$3}', (
      tester,
    ) async {
      tester.view.physicalSize = Size(config.$1, config.$2);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      tester.platformDispatcher.textScaleFactorTestValue = config.$3;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      final boundary = GlobalKey();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildGpmTheme(),
          home: Scaffold(
            body: SingleChildScrollView(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: RepaintBoundary(
                  key: boundary,
                  child: const CompanyLogistCrmIdCard(crmId: 1),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final button = find.byTooltip('Скопировать ID для CRM');
      expect(tester.getRect(button).right, lessThanOrEqualTo(config.$1));
      await tester.runAsync(() async {
        final render =
            boundary.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
        final image = await render.toImage(pixelRatio: 1);
        final data = await image.toByteData(format: ui.ImageByteFormat.png);
        final file = File(
          'build/company-logist-crm-id-shots/card_${config.$1.toInt()}_${config.$3}.png',
        );
        await file.parent.create(recursive: true);
        await file.writeAsBytes(data!.buffer.asUint8List());
        image.dispose();
      });
    });
  }
}

import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/registration_preview_main.dart';
import 'support/load_test_fonts.dart';
import 'support/registration_preview_fake.dart';

void main() {
  setUpAll(loadMobileTestFonts);
  for (final config in [(320.0, 568.0, 1.0), (320.0, 568.0, 2.0), (390.0, 844.0, 1.0), (900.0, 800.0, 1.0)]) {
    for (final step in ['phone', 'locations', 'first_name', 'citizenship_ru', 'review', 'completed']) {
      testWidgets('registration preview $step ${config.$1}px scale ${config.$3}', (tester) async {
        tester.view.physicalSize = Size(config.$1, config.$2); tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
        final boundary = GlobalKey();
        final gateway = FakeRegistrationGateway(step: step == 'completed' ? 'review' : step, completed: step == 'completed');
        // MediaQuery must be inside MaterialApp's view-derived MediaQuery.
        await tester.pumpWidget(RepaintBoundary(key: boundary, child: RegistrationPreviewApp(gateway: gateway)));
        await tester.pumpAndSettle();
        final element = tester.element(find.byType(Scaffold));
        if (config.$3 != 1) {
          tester.platformDispatcher.textScaleFactorTestValue = config.$3;
          addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
          await tester.pumpAndSettle();
        }
        expect(MediaQuery.sizeOf(element).width, config.$1);
        Future<void> shot(String part) async {
          final render = boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary;
          final image = await render.toImage(pixelRatio: 1);
          final data = await image.toByteData(format: ui.ImageByteFormat.png);
          final file = File('build/registration-preview-shots/${step}_${config.$1.toInt()}_${config.$3}_$part.png');
          await file.parent.create(recursive: true); await file.writeAsBytes(data!.buffer.asUint8List());
          image.dispose();
        }
        await shot('top');
        final action = step == 'completed' ? find.text('Новая тестовая анкета') : find.byKey(const Key('registration_primary'));
        await tester.ensureVisible(action); await tester.pumpAndSettle();
        await shot('bottom');
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
      });
    }
  }
}

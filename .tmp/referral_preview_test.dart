import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/screens/worker/worker_referral_promo.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import '../test/support/load_test_fonts.dart';

void main() {
  testWidgets('referral dialog phone desktop and large text previews', (tester) async {
    await tester.runAsync(loadMobileTestFonts);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final output = Directory('referral-previews')..createSync();
    for (final size in [const Size(320,568), const Size(360,640),
      const Size(390,844), const Size(768,1024), const Size(1360,800)]) {
      for (final scale in [1.0, 2.0]) {
        await tester.pumpWidget(const SizedBox.shrink());
        tester.view.physicalSize = size;
        final key = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: key, child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: buildGpmTheme(),
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)),
            child: child!,
          ),
          home: Scaffold(body: Builder(builder: (context) => SingleChildScrollView(
            child: Padding(padding: const EdgeInsets.all(16),
              child: Center(child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 760),
                child: WorkerReferralPromoCard(onTap: () => showWorkerReferralPromo(context)),
              )),
            ),
          ))),
        )));
        await tester.runAsync(() async {
          final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
          final image = await boundary.toImage(pixelRatio: 1);
          final data = await image.toByteData(format: ui.ImageByteFormat.png);
          File('${output.path}/card-${size.width.toInt()}-${scale.toInt()}x.png')
            .writeAsBytesSync(data!.buffer.asUint8List());
          image.dispose();
        });
        await tester.ensureVisible(find.text('Подробнее и пригласить'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Подробнее и пригласить'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(find.byIcon(Icons.telegram), findsNWidgets(2));
        Future<void> capture(String suffix) async {
          expect(tester.takeException(), isNull);
          await tester.runAsync(() async {
            final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
            final image = await boundary.toImage(pixelRatio: 1);
            final data = await image.toByteData(format: ui.ImageByteFormat.png);
            File('${output.path}/referral-${size.width.toInt()}-${scale.toInt()}x$suffix.png')
              .writeAsBytesSync(data!.buffer.asUint8List());
            image.dispose();
          });
        }
        await capture('');
        await tester.ensureVisible(find.text('@GpmHREkaterina'));
        await tester.pumpAndSettle();
        await capture('-contacts');
      }
    }
    await tester.pumpWidget(const SizedBox.shrink());
  });
}

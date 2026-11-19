import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/client/client_home_screen.dart';
import 'package:gpm_platform/screens/logist/logist_home_screen.dart';
import 'package:gpm_platform/screens/worker/worker_home_screen.dart';
import 'package:gpm_platform/services/chat_service.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';

import '../test/support/load_test_fonts.dart';

void main() {
  testWidgets('capture navigation for every role on mobile and desktop', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    await tester.runAsync(loadMobileTestFonts);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final output = Directory('navigation-previews')..createSync();
    for (final role in ['client', 'worker', 'logist']) {
      for (final width in [320, 390, 800, 1360]) {
        app.gpmApi = GpmApiService();
        app.chatService = ChatService(api: app.gpmApi);
        tester.view.physicalSize = Size(width.toDouble(), 700);
        final key = GlobalKey();
        final Widget home = switch (role) {
          'client' => const ClientHomeScreen(),
          'worker' => const WorkerHomeScreen(),
          _ => const LogistHomeScreen(),
        };
        await tester.pumpWidget(MaterialApp(
          theme: buildGpmTheme(),
          home: RepaintBoundary(
            key: key,
            child: Scaffold(
              appBar: AppBar(title: Text('GPM · $role')),
              body: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1120),
                  child: home,
                ),
              ),
            ),
          ),
        ));
        await tester.pumpAndSettle();
        final nav = find.byType(BottomNavigationBar);
        await tester.tap(find.descendant(of: nav, matching: find.byIcon(Icons.forum_outlined)));
        await tester.pumpAndSettle();
        expect(tester.widget<BottomNavigationBar>(nav).currentIndex, 2);
        expect(tester.takeException(), isNull);
        await tester.runAsync(() async {
          final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
          final image = await boundary.toImage(pixelRatio: 1);
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          File('${output.path}/$role-$width.png').writeAsBytesSync(bytes!.buffer.asUint8List());
          image.dispose();
        });
        await tester.pumpWidget(const SizedBox.shrink());
      }
    }
  });
}

import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/models/chat_models.dart';
import 'package:gpm_platform/screens/chats/chat_conversation_screen.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'package:gpm_platform/widgets/gpm_surface.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../test/chat_conversation_screen_test.dart' show FakeApi, FakeChatService;
import '../test/support/load_test_fonts.dart';

class PreviewService extends FakeChatService {
  PreviewService(super.api);
  @override
  Future<ChatConversation> getConversation(String id) async {
    final base = await super.getConversation(id);
    return ChatConversation(
      thread: ChatThread(
        id: id,
        orderId: 'demo-001',
        type: ChatThreadType.workerLogist,
        title: 'Тестовая заявка',
        subtitle: '',
        isArchived: archived,
        requiresLogistAttention: !archived,
        updatedAt: DateTime(2026, 11, 19),
      ),
      messages: base.messages,
    );
  }
}

void main() {
  testWidgets('capture rounded conversation surfaces and QR panel', (tester) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    await tester.runAsync(loadMobileTestFonts);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetViewInsets);
    final output = Directory('surface-previews')..createSync();

    Future<void> capture(GlobalKey key, String name) async {
      await tester.runAsync(() async {
        final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
        final image = await boundary.toImage(pixelRatio: 1);
        final data = await image.toByteData(format: ui.ImageByteFormat.png);
        File('${output.path}/$name.png').writeAsBytesSync(data!.buffer.asUint8List());
        image.dispose();
      });
    }

    Future<void> open(ChatRole role, Size size, {bool archived = false, bool keyboard = false, bool expanded = false}) async {
      app.gpmApi = FakeApi()..order = {
        'title': 'Тестовая заявка',
        'address': 'Тестовый адрес, дом 7',
        'workers_count': 2,
        'hours': 4,
        'status': archived ? 'CONVERTED' : 'PROCESSED',
        'scheduled_at': '2026-11-20T12:00:00Z',
      };
      final service = PreviewService(app.gpmApi)..archived = archived;
      service.messages.add(ChatMessage(
        id: 'own', threadId: 'preview', senderRole: role,
        senderName: 'Я', text: 'Принято. Спасибо!',
        createdAt: DateTime(2026, 11, 19, 12, 1),
        isSystem: false, isOwn: true,
      ));
      app.chatService = service;
      tester.view.physicalSize = size;
      tester.view.viewInsets = FakeViewPadding(bottom: keyboard ? 280 : 0);
      final key = GlobalKey();
      await tester.pumpWidget(MaterialApp(
        theme: buildGpmTheme(),
        home: RepaintBoundary(
          key: key,
          child: ChatConversationScreen(threadId: 'preview', role: role),
        ),
      ));
      await tester.pumpAndSettle();
      if (keyboard) {
        await tester.enterText(find.byType(TextField), 'Сообщение с телефона');
        await tester.pumpAndSettle();
        expect(find.text('Сообщение с телефона'), findsOneWidget);
      }
      if (expanded) {
        await tester.tap(find.descendant(of: find.byType(ExpansionTile), matching: find.text('Тестовая заявка')));
        await tester.pumpAndSettle();
        expect(find.text('Тестовый адрес, дом 7'), findsOneWidget);
      }
      if (archived) expect(find.byType(TextField), findsNothing);
      expect(tester.takeException(), isNull);
      final mode = archived ? 'archive' : keyboard ? 'keyboard' : expanded ? 'expanded' : 'normal';
      await capture(key, '${role.name}-${size.width.toInt()}-$mode');
      await tester.pumpWidget(const SizedBox.shrink());
    }

    for (final role in [ChatRole.logist, ChatRole.worker, ChatRole.client]) {
      for (final size in [const Size(320, 568), const Size(390, 844), const Size(1360, 700)]) {
        await open(role, size);
      }
    }
    for (final size in [const Size(320, 568), const Size(390, 844)]) {
      await open(ChatRole.worker, size, keyboard: true);
    }
    for (final size in [const Size(390, 844), const Size(1360, 700)]) {
      await open(ChatRole.logist, size, archived: true);
      await open(ChatRole.logist, size, expanded: true);
    }
    tester.view.viewInsets = FakeViewPadding.zero;
    tester.view.physicalSize = const Size(390, 700);
    final qrKey = GlobalKey();
    await tester.pumpWidget(MaterialApp(
      theme: buildGpmTheme(),
      home: RepaintBoundary(
        key: qrKey,
        child: Scaffold(
          body: Center(
            child: GpmSurface(
              padding: const EdgeInsets.all(12),
              child: QrImageView(data: 'https://example.invalid/demo', size: 220),
            ),
          ),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await capture(qrKey, 'qr-surface');
    await tester.pumpWidget(const SizedBox.shrink());
  });
}

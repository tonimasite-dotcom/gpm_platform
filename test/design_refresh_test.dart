import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/models/chat_models.dart';
import 'package:gpm_platform/screens/auth/login_screen.dart';
import 'package:gpm_platform/screens/chats/chat_threads_screen.dart';
import 'package:gpm_platform/screens/chats/chat_conversation_screen.dart';
import 'package:gpm_platform/screens/worker/worker_dashboard_screen.dart';
import 'package:gpm_platform/screens/worker/worker_home_screen.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'chat_conversation_screen_test.dart' show FakeApi, FakeChatService;
import 'support/load_test_fonts.dart';

class DesignApi extends FakeApi {
  @override
  Future<List<Map<String, dynamic>>> getOrders() async =>
      throw StateError('orders unavailable');
  @override
  Future<List<Map<String, dynamic>>> getOrdersForWorker(
    String workerId,
  ) async => throw StateError('orders unavailable');
  @override
  Future<Map<String, dynamic>> getMyDashboard() async => {
    'profile': {'rating': 5},
    'summary': {
      'active_orders': 2,
      'pending_applications': 0,
      'available_balance': 3500,
    },
  };
}

class DesignChats extends FakeChatService {
  DesignChats(super.api);
  @override
  Future<List<ChatThread>> getThreadsForRole({
    required ChatRole role,
    required List<Map<String, dynamic>> orders,
  }) async => [
    ChatThread(
      id: 'active',
      orderId: '001/26',
      type: ChatThreadType.workerLogist,
      title: 'Заявка № 001/26',
      subtitle: 'Встречаемся у входа в 10:00',
      isArchived: false,
      requiresLogistAttention: false,
      unreadCount: 2,
      updatedAt: DateTime(2026, 11, 18, 10),
    ),
    ChatThread(
      id: 'archive',
      orderId: '002/26',
      type: ChatThreadType.workerLogist,
      title: 'Заявка № 002/26',
      subtitle: 'Спасибо за работу!',
      isArchived: true,
      requiresLogistAttention: false,
      updatedAt: DateTime(2026, 11, 17, 15),
    ),
  ];
}

void main() {
  final boundary = GlobalKey();
  late DesignApi api;
  late DesignChats chats;
  setUpAll(loadMobileTestFonts);
  setUp(() {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    api = DesignApi()
      ..order = {
        'id': '001/26',
        'title': 'Разгрузка на складе',
        'address': 'Москва, Тестовая улица, 10',
        'status': 'IN_PROCESS',
        'workers_count': 2,
        'hours': 4,
      };
    chats = DesignChats(api);
    chats.messages.addAll([
      ChatMessage(
        id: 'own',
        threadId: 'active',
        senderRole: ChatRole.worker,
        senderName: 'Вы',
        text: 'Доброе утро! Буду вовремя.',
        createdAt: DateTime(2026, 11, 18, 9, 30),
        isSystem: false,
        isOwn: true,
      ),
      ChatMessage(
        id: 'reply',
        threadId: 'active',
        senderRole: ChatRole.logist,
        senderName: 'Анна · логист',
        text: 'Отлично, встречаемся у входа. Напишите, когда будете на месте.',
        createdAt: DateTime(2026, 11, 18, 9, 31),
        isSystem: false,
        isOwn: false,
      ),
    ]);
    app.gpmApi = api;
    app.chatService = chats;
  });

  Future<void> open(
    WidgetTester tester,
    Widget child,
    Size size, {
    double scale = 1,
  }) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = size;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        theme: buildGpmTheme(),
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(scale)),
          child: child!,
        ),
        home: RepaintBoundary(key: boundary, child: child),
      ),
    );
    await tester.pumpAndSettle();
    await tester.runAsync(() async {
      for (final element in find.byType(Image).evaluate()) {
        await precacheImage((element.widget as Image).image, element);
      }
    });
    await tester.pumpAndSettle();
  }

  Future<void> capture(WidgetTester tester, String name) async {
    if (!const bool.fromEnvironment('GPM_CAPTURE_DESIGN')) return;
    await tester.runAsync(() async {
      final render =
          boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final image = await render.toImage(pixelRatio: 2);
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      final file = File('snapshots/2026-11-18-ux-messenger/$name.png');
      await file.parent.create(recursive: true);
      await file.writeAsBytes(data!.buffer.asUint8List());
      image.dispose();
    });
  }

  for (final size in [
    const Size(320, 568),
    const Size(360, 640),
    const Size(390, 844),
  ]) {
    testWidgets('role selection fits viewport $size', (tester) async {
      await open(tester, GpmLoginScreen(onSignedIn: () {}), size);
      final scroll = tester.state<ScrollableState>(
        find.byType(Scrollable).first,
      );
      expect(scroll.position.maxScrollExtent, 0);
      expect(find.text('24/7'), findsNothing);
      expect(find.textContaining('Закрытое тестирование'), findsNothing);
      expect(
        tester.getBottomRight(find.text('Логист')).dy,
        lessThan(size.height),
      );
      expect(tester.takeException(), isNull);
      await capture(tester, 'login-${size.width.toInt()}');
    });
  }
  testWidgets('login remains accessible with large text and keyboard', (
    tester,
  ) async {
    await open(
      tester,
      GpmLoginScreen(onSignedIn: () {}),
      const Size(320, 568),
      scale: 2,
    );
    await tester.ensureVisible(find.text('Клиент'));
    await tester.tap(find.text('Клиент'));
    await tester.pumpAndSettle();
    tester.view.viewInsets = const FakeViewPadding(bottom: 240);
    addTearDown(tester.view.resetViewInsets);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Войти'));
    expect(tester.takeException(), isNull);
  });
  testWidgets('chat list works without orders and searches archive globally', (
    tester,
  ) async {
    await open(
      tester,
      const Scaffold(body: ChatThreadsScreen(role: ChatRole.worker)),
      const Size(390, 844),
    );
    expect(find.text('Заявка № 001/26'), findsOneWidget);
    expect(find.text('Заявка № 002/26'), findsNothing);
    await capture(tester, 'chats-active');
    await tester.tap(find.text('Архив · 1'));
    await tester.pumpAndSettle();
    expect(find.text('Заявка № 002/26'), findsOneWidget);
    await capture(tester, 'chats-archive');
    await tester.enterText(find.byType(TextField), '001/26');
    await tester.pumpAndSettle();
    expect(find.text('Заявка № 001/26'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'Спасибо');
    await tester.pumpAndSettle();
    expect(find.text('Заявка № 002/26'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  for (final role in [ChatRole.client, ChatRole.worker, ChatRole.logist]) {
    testWidgets('compact conversation and archive for ${role.name}', (
      tester,
    ) async {
      await open(
        tester,
        ChatConversationScreen(threadId: 'active', role: role),
        const Size(390, 844),
      );
      expect(find.text('Москва, Тестовая улица, 10'), findsNothing);
      await capture(tester, 'conversation-${role.name}');
      await tester.tap(find.byType(ExpansionTile));
      await tester.pumpAndSettle();
      expect(find.text('Москва, Тестовая улица, 10'), findsOneWidget);
      chats.archived = true;
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();
      expect(find.byTooltip('Отправить сообщение'), findsNothing);
      expect(find.textContaining('доступен только для чтения'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    });
  }
  for (final size in [const Size(390, 844), const Size(1024, 768)]) {
    testWidgets('dashboard uses updated visual language $size', (tester) async {
      await open(
        tester,
        Scaffold(body: WorkerDashboardScreen(onOpenOrders: () {})),
        size,
      );
      expect(find.text('Подробнее и пригласить'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await capture(tester, 'dashboard-${size.width.toInt()}');
    });
  }
  testWidgets('chat search survives switching tabs', (tester) async {
    await open(tester, const WorkerHomeScreen(), const Size(390, 844));
    await tester.tap(find.text('Чаты'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Спасибо');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Главная'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Чаты').last);
    await tester.pumpAndSettle();
    expect(find.text('Спасибо'), findsOneWidget);
    expect(find.text('Заявка № 002/26'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('conversation fits small viewport with keyboard and large text', (
    tester,
  ) async {
    await open(
      tester,
      const ChatConversationScreen(threadId: 'active', role: ChatRole.worker),
      const Size(320, 568),
      scale: 2,
    );
    tester.view.viewInsets = const FakeViewPadding(bottom: 240);
    addTearDown(tester.view.resetViewInsets);
    await tester.pumpAndSettle();
    expect(find.byTooltip('Отправить сообщение'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}

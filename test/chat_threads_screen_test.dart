import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/models/chat_models.dart';
import 'package:gpm_platform/screens/chats/chat_threads_screen.dart';

import 'chat_conversation_screen_test.dart' show FakeApi, FakeChatService;

class ThreadsApi extends FakeApi {
  @override
  Future<List<Map<String, dynamic>>> getOrdersForWorker(
    String workerId,
  ) async => [
    {'id': '001/26', 'address': 'Тестовый адрес', 'status': 'IN_PROCESS'},
  ];
}

class ThreadsService extends FakeChatService {
  ThreadsService(super.api);

  String preview = 'Последнее сообщение';
  bool fail = false;

  @override
  Future<List<ChatThread>> getThreadsForRole({
    required ChatRole role,
    required List<Map<String, dynamic>> orders,
  }) async {
    if (fail) throw StateError('offline');
    return [
      ChatThread(
        id: 'chat-001/26-workerLogist',
        orderId: '001/26',
        type: ChatThreadType.workerLogist,
        title: 'Заявка № 001/26',
        subtitle: preview,
        isArchived: false,
        requiresLogistAttention: false,
        unreadCount: 2,
        updatedAt: DateTime.now(),
      ),
    ];
  }
}

void main() {
  late ThreadsService service;

  setUp(() {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    app.gpmApi = ThreadsApi();
    service = ThreadsService(app.gpmApi);
    app.chatService = service;
  });

  Future<void> open(WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: ChatThreadsScreen(role: ChatRole.worker)),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('list shows last message and polling preserves search', (
    tester,
  ) async {
    await open(tester);
    expect(find.text('Последнее сообщение'), findsOneWidget);
    expect(find.text('Тестовый адрес'), findsNothing);
    await tester.enterText(find.byType(TextField), '001/26');
    service.preview = 'Новое сообщение';
    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();
    expect(find.text('Новое сообщение'), findsOneWidget);
    expect(find.text('001/26'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'refresh failure retains conversations and automatically recovers',
    (tester) async {
      await open(tester);
      service.fail = true;
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      expect(find.text('Заявка № 001/26'), findsOneWidget);
      expect(find.textContaining('Не удалось обновить чаты'), findsOneWidget);
      service.fail = false;
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      expect(find.textContaining('Не удалось обновить чаты'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/models/chat_models.dart';
import 'package:gpm_platform/screens/chats/chat_conversation_screen.dart';
import 'package:gpm_platform/services/chat_service.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';

class FakeApi extends GpmApiService {
  Map<String, dynamic>? order;
  @override
  Future<Map<String, dynamic>?> getOrderById(String orderId) async => order;
}

class FakeChatService extends ChatService {
  FakeChatService(GpmApiService api) : super(api: api);

  final messages = <ChatMessage>[
    ChatMessage(
      id: 'existing',
      threadId: 'chat-001/26-workerLogist',
      senderRole: ChatRole.worker,
      senderName: 'Другой исполнитель',
      text: 'Сообщение коллеги',
      createdAt: DateTime(2026, 9, 8, 12),
      isSystem: false,
      isOwn: false,
    ),
  ];
  bool failLoad = false;
  bool archived = false;
  int loads = 0;
  final requests = <String>[];
  Completer<ChatMessage>? sending;
  String? sentText;

  @override
  Future<ChatConversation> getConversation(String threadId) async {
    loads++;
    if (failLoad) throw StateError('offline');
    return ChatConversation(
      thread: ChatThread(
        id: threadId,
        orderId: '001/26',
        type: ChatThreadType.workerLogist,
        title: 'Заявка № 001/26',
        subtitle: '',
        isArchived: archived,
        requiresLogistAttention: false,
        updatedAt: DateTime(2026, 9, 8),
      ),
      messages: List.of(messages),
    );
  }

  @override
  Future<ChatMessage> sendMessage({
    required String threadId,
    required ChatRole senderRole,
    required String senderName,
    required String text,
    String? clientMessageId,
  }) {
    requests.add(clientMessageId!);
    sentText = text;
    sending = Completer<ChatMessage>();
    return sending!.future;
  }

  void acknowledge() {
    final message = ChatMessage(
      id: requests.last,
      threadId: 'chat-001/26-workerLogist',
      senderRole: ChatRole.worker,
      senderName: 'Я',
      text: sentText!,
      createdAt: DateTime.now(),
      isSystem: false,
      isOwn: true,
    );
    messages.add(message);
    sending!.complete(message);
  }
}

void main() {
  late FakeChatService service;

  setUp(() {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=production\n');
    app.gpmApi = FakeApi();
    service = FakeChatService(app.gpmApi);
    app.chatService = service;
  });

  Future<void> open(WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: ChatConversationScreen(
          threadId: 'chat-001/26-workerLogist',
          role: ChatRole.worker,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> close(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox.shrink());
  }

  testWidgets(
    'sending keeps history and next draft visible without reloading',
    (tester) async {
      await open(tester);
      final colleague = tester.widget<SelectableText>(
        find.byWidgetPredicate(
          (widget) =>
              widget is SelectableText && widget.data == 'Сообщение коллеги',
        ),
      );
      expect(colleague.style!.color, GpmColors.black);
      await tester.enterText(find.byType(TextField), 'Первое сообщение');
      await tester.pump();
      await tester.tap(find.byTooltip('Отправить сообщение'));
      await tester.pump();
      expect(find.text('Первое сообщение'), findsOneWidget);
      expect(find.text('Сообщение коллеги'), findsOneWidget);
      expect(find.text('Отправляется…'), findsOneWidget);
      expect(service.loads, 1);
      await tester.enterText(find.byType(TextField), 'Следующий черновик');
      service.acknowledge();
      await tester.pumpAndSettle();
      expect(find.text('Первое сообщение'), findsOneWidget);
      expect(find.text('Отправлено'), findsOneWidget);
      expect(find.text('Следующий черновик'), findsOneWidget);
      expect(service.loads, 1);
      await close(tester);
    },
  );

  testWidgets(
    'failed send retries the same id and never clears a newer draft',
    (tester) async {
      await open(tester);
      await tester.enterText(find.byType(TextField), 'Повторяемое сообщение');
      await tester.pump();
      await tester.tap(find.byTooltip('Отправить сообщение'));
      await tester.pump();
      service.sending!.completeError(StateError('offline'));
      await tester.pumpAndSettle();
      expect(find.text('Не отправлено'), findsOneWidget);
      await tester.enterText(find.byType(TextField), 'Новый черновик');
      await tester.tap(find.text('Повторить'));
      await tester.pump();
      expect(service.requests.length, 2);
      expect(service.requests[0], service.requests[1]);
      service.acknowledge();
      await tester.pumpAndSettle();
      expect(find.text('Повторяемое сообщение'), findsOneWidget);
      expect(find.text('Новый черновик'), findsOneWidget);
      await close(tester);
    },
  );

  testWidgets('polling reconciles a lost acknowledgment without a duplicate', (
    tester,
  ) async {
    await open(tester);
    await tester.enterText(find.byType(TextField), 'Уже на сервере');
    await tester.pump();
    await tester.tap(find.byTooltip('Отправить сообщение'));
    await tester.pump();
    service.messages.add(
      ChatMessage(
        id: service.requests.last,
        threadId: 'chat-001/26-workerLogist',
        senderRole: ChatRole.worker,
        senderName: 'Я',
        text: 'Уже на сервере',
        createdAt: DateTime.now(),
        isSystem: false,
        isOwn: true,
      ),
    );
    service.sending!.completeError(TimeoutException('lost response'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();
    expect(find.text('Уже на сервере'), findsOneWidget);
    expect(find.text('Не отправлено'), findsNothing);
    await close(tester);
  });

  testWidgets('background failure keeps history and recovers automatically', (
    tester,
  ) async {
    await open(tester);
    service.failLoad = true;
    await tester.pump(const Duration(seconds: 3));
    await tester.pump();
    expect(find.text('Сообщение коллеги'), findsOneWidget);
    expect(find.textContaining('Нет обновлений'), findsOneWidget);
    service.failLoad = false;
    await tester.pump(const Duration(seconds: 3));
    await tester.pump();
    expect(find.textContaining('Нет обновлений'), findsNothing);
    await close(tester);
  });

  testWidgets('draft survives navigation and is cleared on logout', (
    tester,
  ) async {
    await open(tester);
    await tester.enterText(find.byType(TextField), 'Сохранённый черновик');
    await close(tester);
    await open(tester);
    expect(find.text('Сохранённый черновик'), findsOneWidget);
    await close(tester);
    await app.gpmApi.logout();
    await open(tester);
    expect(find.text('Сохранённый черновик'), findsNothing);
    await close(tester);
  });

  testWidgets('Enter sends and archived conversations have no composer', (
    tester,
  ) async {
    await open(tester);
    await tester.enterText(find.byType(TextField), 'С клавиатуры');
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    expect(service.sentText, 'С клавиатуры');
    service.acknowledge();
    await tester.pumpAndSettle();
    service.archived = true;
    await tester.pump(const Duration(seconds: 3));
    await tester.pump();
    expect(find.byType(TextField), findsNothing);
    expect(find.textContaining('доступен только для чтения'), findsOneWidget);
    await close(tester);
  });

  testWidgets(
    'search filters messages and closing it restores the conversation',
    (tester) async {
      await open(tester);
      await tester.tap(find.byTooltip('Поиск в переписке'));
      await tester.pump();
      await tester.enterText(find.byType(TextField).first, 'отсутствует');
      await tester.pump();
      expect(find.text('Сообщения не найдены.'), findsOneWidget);
      await tester.tap(find.byTooltip('Закрыть поиск'));
      await tester.pump();
      expect(find.text('Сообщение коллеги'), findsOneWidget);
      await close(tester);
    },
  );

  testWidgets('incoming messages do not move the reader through history', (
    tester,
  ) async {
    service.messages.addAll(
      List.generate(
        50,
        (index) => ChatMessage(
          id: 'history-$index',
          threadId: 'chat-001/26-workerLogist',
          senderRole: ChatRole.worker,
          senderName: 'Коллега',
          text: 'История $index',
          createdAt: DateTime(2026, 9, 8, 13, index),
          isSystem: false,
          isOwn: false,
        ),
      ),
    );
    await open(tester);
    final list = find.byKey(const PageStorageKey('chat-messages'));
    await tester.drag(list, const Offset(0, 350));
    await tester.pumpAndSettle();
    final scroll = tester.widget<ListView>(list).controller!;
    final before = scroll.offset;
    expect(before, greaterThan(80));
    service.messages.add(
      ChatMessage(
        id: 'incoming',
        threadId: 'chat-001/26-workerLogist',
        senderRole: ChatRole.logist,
        senderName: 'Логист',
        text: 'Новое входящее',
        createdAt: DateTime.now(),
        isSystem: false,
        isOwn: false,
      ),
    );
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();
    expect(scroll.offset, before);
    expect(find.text('Новые сообщения'), findsOneWidget);
    await tester.tap(find.text('Новые сообщения'));
    await tester.pumpAndSettle();
    expect(scroll.offset, 0);
    expect(find.text('Новое входящее'), findsOneWidget);
    await close(tester);
  });

  testWidgets('leaving during send and reopening does not stick in sending', (
    tester,
  ) async {
    await open(tester);
    await tester.enterText(find.byType(TextField), 'В пути');
    await tester.pump();
    await tester.tap(find.byTooltip('Отправить сообщение'));
    await tester.pump();
    await close(tester);
    service.acknowledge();
    await tester.pump();
    await open(tester);
    expect(find.text('В пути'), findsOneWidget);
    expect(find.text('Отправляется…'), findsNothing);
    await close(tester);
  });

  testWidgets('Shift Enter does not send and background polling is paused', (
    tester,
  ) async {
    await open(tester);
    await tester.enterText(find.byType(TextField), 'Строка');
    await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
    expect(service.requests, isEmpty);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    final before = service.loads;
    await tester.pump(const Duration(seconds: 6));
    expect(service.loads, before);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(service.loads, greaterThan(before));
    await close(tester);
  });

  testWidgets(
    'mobile composer remains usable with order context and keyboard',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetViewInsets);
      (app.gpmApi as FakeApi).order = {
        'title': 'Синтетическая заявка',
        'address': 'Тестовый адрес',
        'workers_count': 2,
        'hours': 4,
        'status': 'IN_PROCESS',
        'scheduled_at': '2026-09-09T12:00:00Z',
      };
      await open(tester);
      tester.view.viewInsets = const FakeViewPadding(bottom: 300);
      await tester.enterText(find.byType(TextField), 'Сообщение с телефона');
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Сообщение с телефона'), findsOneWidget);
      expect(find.text('Синтетическая заявка'), findsOneWidget);
      await close(tester);
    },
  );
}

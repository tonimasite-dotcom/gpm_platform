import 'dart:convert';

import '../models/chat_models.dart';
import 'demo_storage.dart';

class ChatService {
  static const _storageKey = 'gpm_chat_state_v1';

  final List<ChatThread> _threads = [];
  final List<ChatMessage> _messages = [];

  ChatService() {
    _loadState();
  }

  Future<List<ChatThread>> getThreadsForRole({
    required ChatRole role,
    required List<Map<String, dynamic>> orders,
  }) async {
    _ensureThreadsForOrders(orders);

    final visibleThreads =
        _threads.where((thread) => thread.isVisibleFor(role)).where((thread) {
      if (role == ChatRole.worker) {
        return _isRelevantForDemoWorker(thread, orders);
      }
      return true;
    }).toList();

    visibleThreads.sort((a, b) {
      if (a.requiresLogistAttention != b.requiresLogistAttention) {
        return a.requiresLogistAttention ? -1 : 1;
      }
      return b.updatedAt.compareTo(a.updatedAt);
    });
    return visibleThreads;
  }

  Future<List<ChatMessage>> getMessages(String threadId) async {
    final result = _messages
        .where((message) => message.threadId == threadId)
        .toList()
      ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
    return result;
  }

  Future<ChatThread?> getThreadById(String threadId) async {
    try {
      return _threads.firstWhere((thread) => thread.id == threadId);
    } catch (_) {
      return null;
    }
  }

  Future<void> sendMessage({
    required String threadId,
    required ChatRole senderRole,
    required String senderName,
    required String text,
  }) async {
    final cleanText = text.trim();
    if (cleanText.isEmpty) return;

    final now = DateTime.now();
    _messages.add(
      ChatMessage(
        id: 'msg-${now.microsecondsSinceEpoch}',
        threadId: threadId,
        senderRole: senderRole,
        senderName: senderName,
        text: cleanText,
        createdAt: now,
        isSystem: false,
      ),
    );

    _touchThread(
      threadId,
      updatedAt: now,
      requiresLogistAttention: senderRole != ChatRole.logist &&
          _threadType(threadId) != ChatThreadType.clientWorker,
    );
    if (senderRole != ChatRole.logist) {
      final thread = _threads.firstWhere((thread) => thread.id == threadId);
      _touchThread(threadId, unreadCount: thread.unreadCount + 1);
    }
    _saveState();
  }

  Future<void> requestLogistSupport({
    required String sourceThreadId,
    required String requesterName,
  }) async {
    final sourceThread = await getThreadById(sourceThreadId);
    if (sourceThread == null) return;

    final now = DateTime.now();
    _messages.add(
      ChatMessage(
        id: 'msg-${now.microsecondsSinceEpoch}',
        threadId: sourceThread.id,
        senderRole: ChatRole.system,
        senderName: 'GPM',
        text:
            '$requesterName запросил подключение логиста. Переписка отмечена для проверки поддержки.',
        createdAt: now,
        isSystem: true,
      ),
    );

    _touchThread(
      sourceThread.id,
      updatedAt: now,
      requiresLogistAttention: true,
      unreadCount: sourceThread.unreadCount + 1,
    );

    final supportThreadId =
        _threadId(sourceThread.orderId, ChatThreadType.support);
    if (!_threads.any((thread) => thread.id == supportThreadId)) {
      _threads.add(
        ChatThread(
          id: supportThreadId,
          orderId: sourceThread.orderId,
          type: ChatThreadType.support,
          title: 'Спор по заказу #${sourceThread.orderId}',
          subtitle: 'Клиент, исполнитель и логист GPM',
          isArchived: sourceThread.isArchived,
          requiresLogistAttention: true,
          unreadCount: 1,
          updatedAt: now,
        ),
      );
      _messages.add(
        ChatMessage(
          id: 'msg-${now.microsecondsSinceEpoch + 1}',
          threadId: supportThreadId,
          senderRole: ChatRole.system,
          senderName: 'GPM',
          text:
              'Создан канал поддержки. Логист видит историю обращения и может подключиться к решению ситуации.',
          createdAt: now,
          isSystem: true,
        ),
      );
    } else {
      _touchThread(
        supportThreadId,
        updatedAt: now,
        requiresLogistAttention: true,
        unreadCount: 1,
      );
    }

    _saveState();
  }

  Future<void> resolveLogistAttention(String threadId) async {
    _touchThread(threadId, requiresLogistAttention: false);
    _saveState();
  }

  Future<void> markThreadRead(String threadId) async {
    _touchThread(threadId, unreadCount: 0);
    _saveState();
  }

  void _ensureThreadsForOrders(List<Map<String, dynamic>> orders) {
    var changed = false;

    for (final order in orders) {
      final orderId = order['id']?.toString();
      if (orderId == null || orderId.isEmpty) continue;

      changed = _ensureThread(order, ChatThreadType.clientLogist) || changed;

      if (_isPublishedOrAssigned(order)) {
        changed = _ensureThread(order, ChatThreadType.workerLogist) || changed;
      }

      if (_assignedWorkerIds(order).isNotEmpty) {
        changed = _ensureThread(order, ChatThreadType.clientWorker) || changed;
      }
    }

    if (changed) _saveState();
  }

  bool _ensureThread(Map<String, dynamic> order, ChatThreadType type) {
    final orderId = order['id'].toString();
    final id = _threadId(orderId, type);
    if (_threads.any((thread) => thread.id == id)) return false;

    final createdAt =
        DateTime.tryParse(order['created_at']?.toString() ?? '') ??
            DateTime.now();
    final archived = order['status'] == 'CONVERTED';
    final orderTitle = order['title']?.toString() ?? 'Заказ #$orderId';

    _threads.add(
      ChatThread(
        id: id,
        orderId: orderId,
        type: type,
        title: _titleForType(type, orderTitle),
        subtitle: order['address']?.toString() ?? 'Адрес не указан',
        isArchived: archived,
        requiresLogistAttention: type == ChatThreadType.clientLogist,
        updatedAt: createdAt,
      ),
    );

    _messages.addAll(_seedMessagesForThread(id, order, type, createdAt));
    return true;
  }

  List<ChatMessage> _seedMessagesForThread(
    String threadId,
    Map<String, dynamic> order,
    ChatThreadType type,
    DateTime createdAt,
  ) {
    final orderTitle = order['title']?.toString() ?? 'заказ';
    final messages = <ChatMessage>[
      ChatMessage(
        id: 'msg-$threadId-system-start',
        threadId: threadId,
        senderRole: ChatRole.system,
        senderName: 'GPM',
        text:
            'Чат создан по заказу "$orderTitle". Переписка хранится в GPM для контроля качества и разрешения спорных ситуаций.',
        createdAt: createdAt,
        isSystem: true,
      ),
    ];

    switch (type) {
      case ChatThreadType.clientLogist:
        messages.add(
          ChatMessage(
            id: 'msg-$threadId-logist-hello',
            threadId: threadId,
            senderRole: ChatRole.logist,
            senderName: 'Логист GPM',
            text: 'Приняли заявку. Уточним детали и назначим исполнителей.',
            createdAt: createdAt.add(const Duration(minutes: 2)),
            isSystem: false,
          ),
        );
        break;
      case ChatThreadType.workerLogist:
        messages.add(
          ChatMessage(
            id: 'msg-$threadId-worker-info',
            threadId: threadId,
            senderRole: ChatRole.logist,
            senderName: 'Логист GPM',
            text:
                'Проверьте адрес, время и комментарии по заказу перед выходом.',
            createdAt: createdAt.add(const Duration(minutes: 3)),
            isSystem: false,
          ),
        );
        break;
      case ChatThreadType.clientWorker:
        messages.add(
          ChatMessage(
            id: 'msg-$threadId-client-worker-info',
            threadId: threadId,
            senderRole: ChatRole.system,
            senderName: 'GPM',
            text:
                'Исполнитель назначен. Используйте чат только для рабочих уточнений по этому заказу.',
            createdAt: createdAt.add(const Duration(minutes: 4)),
            isSystem: true,
          ),
        );
        break;
      case ChatThreadType.support:
        break;
    }

    return messages;
  }

  bool _isRelevantForDemoWorker(
    ChatThread thread,
    List<Map<String, dynamic>> orders,
  ) {
    final order =
        orders.where((order) => order['id'].toString() == thread.orderId);
    if (order.isEmpty) return false;

    if (thread.type == ChatThreadType.clientLogist) return false;
    if (thread.type == ChatThreadType.support) {
      return thread.requiresLogistAttention;
    }

    return _isPublishedOrAssigned(order.first);
  }

  bool _isPublishedOrAssigned(Map<String, dynamic> order) {
    final status = order['status']?.toString();
    return status == 'PROCESSED' ||
        status == 'IN_PROCESS' ||
        status == 'DONE_PENDING' ||
        status == 'CONVERTED' ||
        _assignedWorkerIds(order).isNotEmpty;
  }

  List<String> _assignedWorkerIds(Map<String, dynamic> order) {
    final rawIds = order['assigned_worker_ids'];
    if (rawIds is List<String>) return rawIds;
    if (rawIds is List) return rawIds.map((id) => id.toString()).toList();
    return <String>[];
  }

  String _threadId(String orderId, ChatThreadType type) {
    return 'chat-$orderId-${type.name}';
  }

  String _titleForType(ChatThreadType type, String orderTitle) {
    return switch (type) {
      ChatThreadType.clientLogist => orderTitle,
      ChatThreadType.workerLogist => 'Исполнители: $orderTitle',
      ChatThreadType.clientWorker => 'Связь с исполнителем',
      ChatThreadType.support => 'Поддержка GPM',
    };
  }

  ChatThreadType? _threadType(String threadId) {
    try {
      return _threads.firstWhere((thread) => thread.id == threadId).type;
    } catch (_) {
      return null;
    }
  }

  void _touchThread(
    String threadId, {
    DateTime? updatedAt,
    bool? requiresLogistAttention,
    int? unreadCount,
  }) {
    final index = _threads.indexWhere((thread) => thread.id == threadId);
    if (index == -1) return;

    _threads[index] = _threads[index].copyWith(
      updatedAt: updatedAt,
      requiresLogistAttention: requiresLogistAttention,
      unreadCount: unreadCount,
    );
  }

  void _loadState() {
    final rawState = readDemoValue(_storageKey);
    if (rawState == null || rawState.isEmpty) return;

    try {
      final decoded = jsonDecode(rawState);
      if (decoded is! Map<String, dynamic>) return;

      final threads = decoded['threads'];
      if (threads is List) {
        _threads
          ..clear()
          ..addAll(
            threads.map((thread) => ChatThread.fromJson(
                  Map<String, dynamic>.from(thread as Map),
                )),
          );
      }

      final messages = decoded['messages'];
      if (messages is List) {
        _messages
          ..clear()
          ..addAll(
            messages.map((message) => ChatMessage.fromJson(
                  Map<String, dynamic>.from(message as Map),
                )),
          );
      }
    } catch (_) {
      _threads.clear();
      _messages.clear();
    }
  }

  void _saveState() {
    writeDemoValue(
      _storageKey,
      jsonEncode({
        'threads': _threads.map((thread) => thread.toJson()).toList(),
        'messages': _messages.map((message) => message.toJson()).toList(),
      }),
    );
  }
}

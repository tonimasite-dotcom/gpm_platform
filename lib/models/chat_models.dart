enum ChatRole {
  client,
  worker,
  logist,
  system,
}

enum ChatThreadType {
  clientLogist,
  workerLogist,
  clientWorker,
  support,
}

class ChatThread {
  final String id;
  final String orderId;
  final ChatThreadType type;
  final String title;
  final String subtitle;
  final bool isArchived;
  final bool requiresLogistAttention;
  final int unreadCount;
  final DateTime updatedAt;

  const ChatThread({
    required this.id,
    required this.orderId,
    required this.type,
    required this.title,
    required this.subtitle,
    required this.isArchived,
    required this.requiresLogistAttention,
    this.unreadCount = 0,
    required this.updatedAt,
  });

  bool isVisibleFor(ChatRole role) {
    if (role == ChatRole.logist) return true;

    return switch (type) {
      ChatThreadType.clientLogist => role == ChatRole.client,
      ChatThreadType.workerLogist => role == ChatRole.worker,
      ChatThreadType.clientWorker =>
        role == ChatRole.client || role == ChatRole.worker,
      ChatThreadType.support =>
        role == ChatRole.client || role == ChatRole.worker,
    };
  }

  String get typeLabel {
    return switch (type) {
      ChatThreadType.clientLogist => 'Клиент - логист',
      ChatThreadType.workerLogist => 'Исполнитель - логист',
      ChatThreadType.clientWorker => 'Клиент - исполнитель',
      ChatThreadType.support => 'Поддержка GPM',
    };
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'order_id': orderId,
      'type': type.name,
      'title': title,
      'subtitle': subtitle,
      'is_archived': isArchived,
      'requires_logist_attention': requiresLogistAttention,
      'unread_count': unreadCount,
      'updated_at': updatedAt.toUtc().toIso8601String(),
    };
  }

  factory ChatThread.fromJson(Map<String, dynamic> json) {
    return ChatThread(
      id: json['id'].toString(),
      orderId: json['order_id'].toString(),
      type: ChatThreadType.values.firstWhere(
        (type) => type.name == json['type'],
        orElse: () => ChatThreadType.clientLogist,
      ),
      title: json['title']?.toString() ?? 'Чат по заказу',
      subtitle: json['subtitle']?.toString() ?? '',
      isArchived: json['is_archived'] == true,
      requiresLogistAttention: json['requires_logist_attention'] == true,
      unreadCount: (json['unread_count'] as int?) ?? 0,
      updatedAt: DateTime.tryParse(json['updated_at']?.toString() ?? '') ??
          DateTime.now(),
    );
  }

  ChatThread copyWith({
    String? title,
    String? subtitle,
    bool? isArchived,
    bool? requiresLogistAttention,
    int? unreadCount,
    DateTime? updatedAt,
  }) {
    return ChatThread(
      id: id,
      orderId: orderId,
      type: type,
      title: title ?? this.title,
      subtitle: subtitle ?? this.subtitle,
      isArchived: isArchived ?? this.isArchived,
      requiresLogistAttention:
          requiresLogistAttention ?? this.requiresLogistAttention,
      unreadCount: unreadCount ?? this.unreadCount,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}

class ChatMessage {
  final String id;
  final String threadId;
  final ChatRole senderRole;
  final String senderName;
  final String text;
  final DateTime createdAt;
  final bool isSystem;

  const ChatMessage({
    required this.id,
    required this.threadId,
    required this.senderRole,
    required this.senderName,
    required this.text,
    required this.createdAt,
    required this.isSystem,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'thread_id': threadId,
      'sender_role': senderRole.name,
      'sender_name': senderName,
      'text': text,
      'created_at': createdAt.toUtc().toIso8601String(),
      'is_system': isSystem,
    };
  }

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'].toString(),
      threadId: json['thread_id'].toString(),
      senderRole: ChatRole.values.firstWhere(
        (role) => role.name == json['sender_role'],
        orElse: () => ChatRole.system,
      ),
      senderName: json['sender_name']?.toString() ?? 'GPM',
      text: json['text']?.toString() ?? '',
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ??
          DateTime.now(),
      isSystem: json['is_system'] == true,
    );
  }
}

import 'package:flutter/material.dart';

import '../../main.dart' show bitrix24, chatService;
import '../../models/chat_models.dart';
import '../../theme/gpm_theme.dart';

class ChatConversationScreen extends StatefulWidget {
  final String threadId;
  final ChatRole role;

  const ChatConversationScreen({
    super.key,
    required this.threadId,
    required this.role,
  });

  @override
  State<ChatConversationScreen> createState() => _ChatConversationScreenState();
}

class _ChatConversationScreenState extends State<ChatConversationScreen> {
  final _controller = TextEditingController();
  late Future<_ConversationData> _conversationFuture;
  bool _isSending = false;

  @override
  void initState() {
    super.initState();
    chatService.markThreadRead(widget.threadId);
    _conversationFuture = _loadConversation();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<_ConversationData> _loadConversation() async {
    final thread = await chatService.getThreadById(widget.threadId);
    final messages = await chatService.getMessages(widget.threadId);
    if (thread == null) {
      throw StateError('Чат не найден');
    }
    final order = await bitrix24.getOrderById(thread.orderId);
    return _ConversationData(
      thread: thread,
      messages: messages,
      order: order,
    );
  }

  void _refresh() {
    setState(() {
      _conversationFuture = _loadConversation();
    });
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isSending) return;

    setState(() => _isSending = true);
    try {
      await chatService.sendMessage(
        threadId: widget.threadId,
        senderRole: widget.role,
        senderName: _senderName,
        text: text,
      );
      _controller.clear();
      _refresh();
    } finally {
      if (mounted) {
        setState(() => _isSending = false);
      }
    }
  }

  Future<void> _requestSupport() async {
    await chatService.requestLogistSupport(
      sourceThreadId: widget.threadId,
      requesterName: _senderName,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Логисту отправлен запрос на подключение')),
    );
    _refresh();
  }

  Future<void> _sendQuickMessage(String text) async {
    await chatService.sendMessage(
      threadId: widget.threadId,
      senderRole: widget.role,
      senderName: _senderName,
      text: text,
    );
    _refresh();
  }

  Future<void> _resolveAttention() async {
    await chatService.resolveLogistAttention(widget.threadId);
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_ConversationData>(
      future: _conversationFuture,
      builder: (context, snapshot) {
        final title = snapshot.data?.thread.title ?? 'Чат';

        return Scaffold(
          appBar: AppBar(
            title: Text(title),
            actions: [
              if (widget.role == ChatRole.logist &&
                  (snapshot.data?.thread.requiresLogistAttention ?? false))
                TextButton(
                  onPressed: _resolveAttention,
                  child: const Text('Закрыть сигнал'),
                ),
            ],
          ),
          body: _buildBody(snapshot),
        );
      },
    );
  }

  Widget _buildBody(AsyncSnapshot<_ConversationData> snapshot) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const Center(child: CircularProgressIndicator());
    }

    if (snapshot.hasError) {
      return Center(child: Text('Ошибка: ${snapshot.error}'));
    }

    final data = snapshot.data!;
    final canWrite = !data.thread.isArchived;

    return Column(
      children: [
        _ConversationNotice(thread: data.thread, role: widget.role),
        if (data.order != null)
          _OrderContextCard(
            order: data.order!,
            thread: data.thread,
          ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 18),
            itemCount: data.messages.length,
            itemBuilder: (context, index) {
              final message = data.messages[index];
              return _MessageBubble(
                message: message,
                isOwn: message.senderRole == widget.role,
              );
            },
          ),
        ),
        if (canWrite)
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _QuickActions(
                role: widget.role,
                thread: data.thread,
                order: data.order,
                canRequestSupport: _canRequestSupport(data.thread),
                onRequestSupport: _requestSupport,
                onQuickMessage: _sendQuickMessage,
                onResolveAttention: _resolveAttention,
              ),
              _Composer(
                controller: _controller,
                isSending: _isSending,
                onSend: _sendMessage,
              ),
            ],
          )
        else
          const _ArchivedFooter(),
      ],
    );
  }

  bool _canRequestSupport(ChatThread thread) {
    return widget.role != ChatRole.logist &&
        thread.type != ChatThreadType.support &&
        !thread.requiresLogistAttention;
  }

  String get _senderName {
    return switch (widget.role) {
      ChatRole.client => 'Клиент',
      ChatRole.worker => 'Иван Петров',
      ChatRole.logist => 'Логист GPM',
      ChatRole.system => 'GPM',
    };
  }
}

class _ConversationData {
  final ChatThread thread;
  final List<ChatMessage> messages;
  final Map<String, dynamic>? order;

  const _ConversationData({
    required this.thread,
    required this.messages,
    required this.order,
  });
}

class _ConversationNotice extends StatelessWidget {
  final ChatThread thread;
  final ChatRole role;

  const _ConversationNotice({
    required this.thread,
    required this.role,
  });

  @override
  Widget build(BuildContext context) {
    final text = switch (thread.type) {
      ChatThreadType.clientWorker =>
        'Рабочий чат клиента и исполнителя. При споре можно подключить логиста GPM.',
      ChatThreadType.support =>
        'Канал поддержки. Логист фиксирует договоренности и решение спорной ситуации.',
      ChatThreadType.clientLogist =>
        'Канал клиента и логиста по заявке. Здесь уточняются детали заказа.',
      ChatThreadType.workerLogist =>
        'Канал исполнителя и логиста по выходу на заказ и операционным вопросам.',
    };

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: const BoxDecoration(
        color: GpmColors.surface,
        border: Border(bottom: BorderSide(color: GpmColors.line)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            role == ChatRole.logist
                ? Icons.admin_panel_settings_outlined
                : Icons.info_outline,
            color: GpmColors.red,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

class _OrderContextCard extends StatelessWidget {
  final Map<String, dynamic> order;
  final ChatThread thread;

  const _OrderContextCard({
    required this.order,
    required this.thread,
  });

  @override
  Widget build(BuildContext context) {
    final status = _orderStatusText(order['status']);
    final statusColor = _orderStatusColor(order['status']);
    final scheduledAt = _formatScheduledAt(order['scheduled_at']);
    final address = order['address']?.toString() ?? 'Адрес не указан';
    final workers = order['workers_count']?.toString() ?? '';
    final hours = order['hours']?.toString() ?? '';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: GpmColors.line)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  order['title']?.toString() ?? 'Заказ',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              _SmallPill(text: status, color: statusColor),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 10,
            runSpacing: 6,
            children: [
              _FactIcon(icon: Icons.place_outlined, text: address),
              if (scheduledAt.isNotEmpty)
                _FactIcon(icon: Icons.schedule, text: scheduledAt),
              if (workers.isNotEmpty || hours.isNotEmpty)
                _FactIcon(
                  icon: Icons.engineering,
                  text: [
                    if (workers.isNotEmpty) '$workers исполн.',
                    if (hours.isNotEmpty) '$hours ч',
                  ].join(' · '),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _QuickActions extends StatelessWidget {
  final ChatRole role;
  final ChatThread thread;
  final Map<String, dynamic>? order;
  final bool canRequestSupport;
  final VoidCallback onRequestSupport;
  final ValueChanged<String> onQuickMessage;
  final VoidCallback onResolveAttention;

  const _QuickActions({
    required this.role,
    required this.thread,
    required this.order,
    required this.canRequestSupport,
    required this.onRequestSupport,
    required this.onQuickMessage,
    required this.onResolveAttention,
  });

  @override
  Widget build(BuildContext context) {
    final actions = <Widget>[];

    if (role == ChatRole.worker) {
      actions.addAll([
        _ActionButton(
          icon: Icons.location_on_outlined,
          label: 'Я на месте',
          onTap: () => onQuickMessage('Я на месте. Готов начинать работы.'),
        ),
        _ActionButton(
          icon: Icons.task_alt,
          label: 'Работы завершены',
          onTap: () => onQuickMessage('Работы завершены.'),
        ),
      ]);
    }

    if (role == ChatRole.client && order?['status'] == 'DONE_PENDING') {
      actions.add(
        _ActionButton(
          icon: Icons.payments_outlined,
          label: 'Оплатить',
          onTap: () => onQuickMessage('Готов оплатить заказ.'),
        ),
      );
    }

    if (role != ChatRole.logist && canRequestSupport) {
      actions.add(
        _ActionButton(
          icon: Icons.support_agent,
          label: 'Поддержка 24/7',
          onTap: onRequestSupport,
        ),
      );
    }

    if (role == ChatRole.logist && thread.requiresLogistAttention) {
      actions.add(
        _ActionButton(
          icon: Icons.check_circle_outline,
          label: 'Закрыть сигнал',
          onTap: onResolveAttention,
        ),
      );
    }

    if (actions.isEmpty) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      decoration: const BoxDecoration(
        color: GpmColors.surface,
        border: Border(top: BorderSide(color: GpmColors.line)),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(children: actions),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8, bottom: 8),
      child: OutlinedButton.icon(
        onPressed: onTap,
        icon: Icon(icon, size: 18),
        label: Text(label),
      ),
    );
  }
}

class _FactIcon extends StatelessWidget {
  final IconData icon;
  final String text;

  const _FactIcon({
    required this.icon,
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: GpmColors.graphite),
        const SizedBox(width: 4),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 320),
          child: Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: GpmColors.graphite,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }
}

class _SmallPill extends StatelessWidget {
  final String text;
  final Color color;

  const _SmallPill({
    required this.text,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final bool isOwn;

  const _MessageBubble({
    required this.message,
    required this.isOwn,
  });

  @override
  Widget build(BuildContext context) {
    if (message.isSystem) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Center(
          child: Container(
            constraints: const BoxConstraints(maxWidth: 520),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFFEDEDED),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              message.text,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 12, color: GpmColors.graphite),
            ),
          ),
        ),
      );
    }

    final background = isOwn ? GpmColors.red : GpmColors.surface;
    final foreground = isOwn ? Colors.white : GpmColors.black;

    return Align(
      alignment: isOwn ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 560),
        margin: const EdgeInsets.symmetric(vertical: 5),
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 9),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(8),
          border: isOwn ? null : Border.all(color: GpmColors.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              message.senderName,
              style: TextStyle(
                color: foreground.withValues(alpha: 0.85),
                fontSize: 12,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              message.text,
              style: TextStyle(color: foreground, fontSize: 15),
            ),
            const SizedBox(height: 5),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                _formatTime(message.createdAt),
                style: TextStyle(
                  color: foreground.withValues(alpha: 0.7),
                  fontSize: 11,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatTime(DateTime value) {
    return '${value.hour.toString().padLeft(2, '0')}:'
        '${value.minute.toString().padLeft(2, '0')}';
  }
}

class _Composer extends StatelessWidget {
  final TextEditingController controller;
  final bool isSending;
  final VoidCallback onSend;

  const _Composer({
    required this.controller,
    required this.isSending,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
        decoration: const BoxDecoration(
          color: GpmColors.surface,
          border: Border(top: BorderSide(color: GpmColors.line)),
        ),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.newline,
                decoration: const InputDecoration(
                  hintText: 'Сообщение по заказу',
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                ),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              onPressed: isSending ? null : onSend,
              child: isSending
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send),
            ),
          ],
        ),
      ),
    );
  }
}

class _ArchivedFooter extends StatelessWidget {
  const _ArchivedFooter();

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: const BoxDecoration(
          color: GpmColors.surface,
          border: Border(top: BorderSide(color: GpmColors.line)),
        ),
        child: const Text(
          'Заказ завершен. Чат сохранен в архиве и доступен только для чтения.',
          textAlign: TextAlign.center,
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}

String _orderStatusText(dynamic status) {
  return switch (status?.toString()) {
    'NEW' => 'Ищем исполнителей',
    'PROCESSED' => 'Исполнители найдены',
    'IN_PROCESS' => 'В работе',
    'DONE_PENDING' => 'Ждет подтверждения',
    'CONVERTED' => 'Завершен',
    'JUNK' => 'Отменен',
    _ => 'Статус уточняется',
  };
}

Color _orderStatusColor(dynamic status) {
  return switch (status?.toString()) {
    'NEW' => Colors.orange,
    'PROCESSED' => Colors.blue,
    'IN_PROCESS' => Colors.green,
    'DONE_PENDING' => Colors.deepOrange,
    'CONVERTED' => Colors.grey,
    'JUNK' => Colors.red,
    _ => Colors.grey,
  };
}

String _formatScheduledAt(dynamic value) {
  final parsed = DateTime.tryParse(value?.toString() ?? '');
  if (parsed == null) return '';
  final local = parsed.toLocal();
  return '${local.day.toString().padLeft(2, '0')}.'
      '${local.month.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../main.dart' show gpmApi, chatService;
import '../../models/chat_models.dart';
import '../../services/chat_service.dart';
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

class _ChatConversationScreenState extends State<ChatConversationScreen>
    with WidgetsBindingObserver {
  final _controller = TextEditingController();
  final _focus = FocusNode();
  final _scroll = ScrollController();
  late final List<PendingChatMessage> _pending;
  late final String _sessionScope;
  Timer? _timer;
  _ConversationData? _data;
  DateTime? _orderLoadedAt;
  bool _loading = false;
  bool _loadFailed = false;
  bool _actionBusy = false;
  bool _active = true;
  bool _hasNewMessages = false;
  final Set<String> _deferredIds = {};
  bool _searching = false;
  String _query = '';
  int _revision = 0;

  bool get _isSending =>
      _pending.any((item) => item.delivery == ChatDelivery.sending);
  bool get _nearBottom => !_scroll.hasClients || _scroll.offset < 80;
  bool get _sameSession => _sessionScope == chatService.sessionScope;

  @override
  void initState() {
    super.initState();
    _sessionScope = chatService.sessionScope;
    _controller.text = chatService.draft(widget.threadId, widget.role);
    _pending = chatService.outbox(widget.threadId, widget.role);
    _controller.addListener(_saveDraft);
    _scroll.addListener(_onScroll);
    WidgetsBinding.instance.addObserver(this);
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (_active &&
          mounted &&
          _sameSession &&
          TickerMode.of(context) &&
          ModalRoute.of(context)?.isCurrent == true) {
        _refresh();
      }
    });
  }

  void _saveDraft() {
    if (_sameSession) {
      chatService.saveDraft(widget.threadId, widget.role, _controller.text);
    }
  }

  void _onScroll() {
    if (_nearBottom && _hasNewMessages) {
      _goToLatest();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _active = state == AppLifecycleState.resumed;
    if (_active && mounted && ModalRoute.of(context)?.isCurrent == true) {
      _refresh();
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    _controller.dispose();
    _focus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_loading || !_sameSession) return;
    _loading = true;
    final revision = _revision;
    try {
      final conversation = await chatService.getConversation(widget.threadId);
      var order = _data?.order;
      if (_orderLoadedAt == null ||
          DateTime.now().difference(_orderLoadedAt!) >
              const Duration(seconds: 30)) {
        try {
          order = await gpmApi.getOrderById(conversation.thread.orderId);
          _orderLoadedAt = DateTime.now();
        } catch (_) {
          // Order context is supplementary; a failed request must not hide chat.
        }
      }
      if (!mounted || !_sameSession || revision != _revision) return;
      final wasNearBottom = _nearBottom;
      final known = {
        ...?_data?.messages.map((item) => item.id),
        ..._pending.map((item) => item.message.id),
      };
      final hasIncoming =
          _data != null &&
          conversation.messages.any((item) => !known.contains(item.id));
      final ids = conversation.messages.map((item) => item.id).toSet();
      setState(() {
        _pending.removeWhere((item) => ids.contains(item.message.id));
        _data = _ConversationData(
          thread: conversation.thread,
          messages: conversation.messages,
          order: order,
        );
        _loadFailed = false;
        if (hasIncoming && !wasNearBottom) {
          // Buffer incoming items while reading history: inserting below a
          // reversed lazy list would otherwise move the visible messages.
          _deferredIds.addAll(ids.difference(known));
          _hasNewMessages = true;
        }
      });
      if (wasNearBottom) {
        _goToLatest(animate: false);
      }
    } catch (_) {
      if (mounted && _sameSession) setState(() => _loadFailed = true);
    } finally {
      _loading = false;
    }
  }

  void _goToLatest({bool animate = true}) {
    if (_hasNewMessages) {
      setState(() {
        _deferredIds.clear();
        _hasNewMessages = false;
      });
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scroll.hasClients) return;
      if (animate) {
        _scroll.animateTo(
          0,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      } else {
        _scroll.jumpTo(0);
      }
    });
  }

  Future<void> _sendMessage([String? quickText]) async {
    final text = (quickText ?? _controller.text).trim();
    if (text.isEmpty ||
        _isSending ||
        _data?.thread.isArchived != false ||
        !_sameSession) {
      return;
    }
    if (text.length > 2000) {
      _showError('Максимальная длина сообщения — 2000 символов.');
      return;
    }
    final pending = PendingChatMessage(
      ChatMessage(
        id: ChatService.newMessageId(),
        threadId: widget.threadId,
        senderRole: widget.role,
        senderName: _senderName,
        text: text,
        createdAt: DateTime.now(),
        isSystem: false,
        isOwn: true,
      ),
    );
    setState(() => _pending.add(pending));
    if (quickText == null) {
      _controller.clear();
      _focus.requestFocus();
    }
    _goToLatest();
    await _deliver(pending);
  }

  Future<void> _deliver(PendingChatMessage pending) async {
    if (!_sameSession) return;
    setState(() => pending.delivery = ChatDelivery.sending);
    try {
      final message = await chatService.sendMessage(
        threadId: widget.threadId,
        senderRole: widget.role,
        senderName: _senderName,
        text: pending.message.text,
        clientMessageId: pending.message.id,
      );
      if (!_sameSession) return;
      pending.message = message;
      pending.delivery = ChatDelivery.sent;
      // The outbox survives navigation until a fetch observes the acknowledgment.
      if (!mounted) {
        return;
      }
      _revision++;
      setState(() {
        _pending.remove(pending);
        final data = _data!;
        final messages =
            [...data.messages.where((item) => item.id != message.id), message]
              ..sort((a, b) {
                final time = a.createdAt.compareTo(b.createdAt);
                return time == 0 ? a.id.compareTo(b.id) : time;
              });
        _data = _ConversationData(
          thread: data.thread,
          messages: messages,
          order: data.order,
        );
      });
    } catch (_) {
      pending.delivery = ChatDelivery.failed;
      if (mounted && _sameSession) setState(() {});
    }
  }

  void _showError(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _performAction(
    Future<void> Function() action, {
    String? success,
  }) async {
    if (_actionBusy || !_sameSession) return;
    setState(() => _actionBusy = true);
    try {
      await action();
      if (!mounted || !_sameSession) return;
      if (success != null) _showError(success);
      await _refresh();
    } catch (_) {
      _showError(
        'Не удалось выполнить действие. Проверьте соединение и повторите.',
      );
    } finally {
      if (mounted) setState(() => _actionBusy = false);
    }
  }

  Future<void> _requestSupport() => _performAction(
    () => chatService.requestLogistSupport(
      sourceThreadId: widget.threadId,
      requesterName: _senderName,
    ),
    success: 'Логисту отправлен запрос на подключение',
  );

  Future<void> _resolveAttention() =>
      _performAction(() => chatService.resolveLogistAttention(widget.threadId));

  @override
  Widget build(BuildContext context) {
    final data = _data;
    return Scaffold(
      appBar: AppBar(
        title: Text(data?.thread.title ?? 'Чат'),
        actions: [
          IconButton(
            tooltip: _searching ? 'Закрыть поиск' : 'Поиск в переписке',
            icon: Icon(_searching ? Icons.search_off : Icons.search),
            onPressed: () => setState(() {
              _searching = !_searching;
              _query = '';
            }),
          ),
          if (widget.role == ChatRole.logist &&
              (data?.thread.requiresLogistAttention ?? false))
            TextButton(
              onPressed: _actionBusy ? null : _resolveAttention,
              child: const Text('Закрыть сигнал'),
            ),
        ],
      ),
      body: data == null
          ? _loadFailed
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('Не удалось загрузить чат.'),
                        TextButton(
                          onPressed: _refresh,
                          child: const Text('Повторить'),
                        ),
                      ],
                    ),
                  )
                : const Center(child: CircularProgressIndicator())
          : _buildConversation(data),
    );
  }

  Widget _buildConversation(_ConversationData data) {
    final messages =
        [
              ...data.messages,
              ..._pending
                  .where(
                    (pending) => !data.messages.any(
                      (item) => item.id == pending.message.id,
                    ),
                  )
                  .map((pending) => pending.message),
            ]
            .where(
              (message) =>
                  (_searching || !_deferredIds.contains(message.id)) &&
                  message.text.toLowerCase().contains(_query),
            )
            .toList();
    return Column(
      children: [
        _ConversationNotice(thread: data.thread, role: widget.role),
        if (data.order != null)
          _OrderContextCard(order: data.order!, thread: data.thread),
        if (_searching)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: TextField(
              autofocus: true,
              decoration: const InputDecoration(
                hintText: 'Поиск в переписке',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (value) =>
                  setState(() => _query = value.trim().toLowerCase()),
            ),
          ),
        if (_loadFailed)
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Flexible(
                child: Text('Нет обновлений. Проверяем соединение…'),
              ),
              TextButton(onPressed: _refresh, child: const Text('Повторить')),
            ],
          ),
        Expanded(
          child: Stack(
            children: [
              if (messages.isEmpty)
                Center(
                  child: Text(
                    _query.isNotEmpty
                        ? 'Сообщения не найдены.'
                        : 'Сообщений пока нет. Напишите первым.',
                  ),
                )
              else
                ListView.builder(
                  key: const PageStorageKey('chat-messages'),
                  controller: _scroll,
                  reverse: true,
                  padding: const EdgeInsets.fromLTRB(12, 12, 12, 18),
                  itemCount: messages.length,
                  itemBuilder: (context, index) {
                    final position = messages.length - index - 1;
                    final message = messages[position];
                    final pending = _pending
                        .where((item) => item.message.id == message.id)
                        .firstOrNull;
                    final localDate = DateUtils.dateOnly(
                      message.createdAt.toLocal(),
                    );
                    final showDate =
                        position == 0 ||
                        localDate !=
                            DateUtils.dateOnly(
                              messages[position - 1].createdAt.toLocal(),
                            );
                    return Column(
                      key: ValueKey(message.id),
                      children: [
                        if (showDate)
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: 6),
                            child: Text(
                              '${localDate.day.toString().padLeft(2, '0')}.'
                              '${localDate.month.toString().padLeft(2, '0')}.'
                              '${localDate.year}',
                              style: const TextStyle(
                                fontSize: 12,
                                color: GpmColors.graphite,
                              ),
                            ),
                          ),
                        _MessageBubble(
                          message: message,
                          isOwn:
                              message.isOwn ??
                              (!gpmApi.isApiMode &&
                                  message.senderRole == widget.role),
                          delivery: pending?.delivery,
                          onRetry:
                              pending?.delivery == ChatDelivery.failed &&
                                  !_isSending &&
                                  !data.thread.isArchived
                              ? () => _deliver(pending!)
                              : null,
                        ),
                      ],
                    );
                  },
                ),
              if (_hasNewMessages)
                Positioned(
                  bottom: 8,
                  right: 12,
                  child: FilledButton.icon(
                    onPressed: _goToLatest,
                    icon: const Icon(Icons.arrow_downward),
                    label: const Text('Новые сообщения'),
                  ),
                ),
            ],
          ),
        ),
        if (!data.thread.isArchived) ...[
          IgnorePointer(
            ignoring: _actionBusy || _isSending,
            child: _QuickActions(
              role: widget.role,
              thread: data.thread,
              order: data.order,
              canRequestSupport: _canRequestSupport(data.thread),
              onRequestSupport: _requestSupport,
              onQuickMessage: _sendMessage,
              onResolveAttention: _resolveAttention,
            ),
          ),
          _Composer(
            controller: _controller,
            focusNode: _focus,
            isSending: _isSending,
            onSend: _sendMessage,
          ),
        ] else
          const _ArchivedFooter(),
      ],
    );
  }

  bool _canRequestSupport(ChatThread thread) =>
      widget.role != ChatRole.logist &&
      thread.type != ChatThreadType.support &&
      !thread.requiresLogistAttention;

  String get _senderName {
    if (gpmApi.isApiMode && gpmApi.currentUsername.isNotEmpty) {
      return gpmApi.currentUsername;
    }
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

  const _ConversationNotice({required this.thread, required this.role});

  @override
  Widget build(BuildContext context) {
    final text = switch (thread.type) {
      ChatThreadType.clientWorker =>
        'Единый рабочий чат по заявке для согласования деталей и выполнения заказа.',
      ChatThreadType.support =>
        'Канал поддержки. Логист фиксирует договоренности и решение спорной ситуации.',
      ChatThreadType.clientLogist =>
        'Канал клиента и логиста по заявке. Здесь уточняются детали заказа.',
      ChatThreadType.workerLogist =>
        'Единый рабочий чат по заявке с назначенным логистом и исполнителями.',
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

  const _OrderContextCard({required this.order, required this.thread});

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

  const _FactIcon({required this.icon, required this.text});

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

  const _SmallPill({required this.text, required this.color});

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
  final ChatDelivery? delivery;
  final VoidCallback? onRetry;

  const _MessageBubble({
    required this.message,
    required this.isOwn,
    this.delivery,
    this.onRetry,
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
            SelectableText(
              message.text,
              style: TextStyle(color: foreground, fontSize: 15),
            ),
            const SizedBox(height: 5),
            Align(
              alignment: Alignment.centerRight,
              child: Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 8,
                children: [
                  Text(
                    _formatTime(message.createdAt.toLocal()),
                    style: TextStyle(
                      color: foreground.withValues(alpha: 0.7),
                      fontSize: 11,
                    ),
                  ),
                  if (isOwn)
                    Text(switch (delivery) {
                      ChatDelivery.sending => 'Отправляется…',
                      ChatDelivery.failed => 'Не отправлено',
                      ChatDelivery.sent || null => 'Отправлено',
                    }, style: TextStyle(color: foreground, fontSize: 11)),
                  if (onRetry != null)
                    TextButton(
                      onPressed: onRetry,
                      style: TextButton.styleFrom(foregroundColor: foreground),
                      child: const Text('Повторить'),
                    ),
                ],
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
  final FocusNode focusNode;
  final bool isSending;
  final VoidCallback onSend;

  const _Composer({
    required this.controller,
    required this.focusNode,
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
              child: Focus(
                onKeyEvent: (_, event) {
                  if (event is KeyDownEvent &&
                      (event.logicalKey == LogicalKeyboardKey.enter ||
                          event.logicalKey == LogicalKeyboardKey.numpadEnter) &&
                      !HardwareKeyboard.instance.isShiftPressed &&
                      controller.value.composing.isCollapsed) {
                    if (!isSending) onSend();
                    return KeyEventResult.handled;
                  }
                  return KeyEventResult.ignored;
                },
                child: TextField(
                  controller: controller,
                  focusNode: focusNode,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.newline,
                  decoration: const InputDecoration(
                    hintText: 'Сообщение по заказу',
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 12,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Tooltip(
              message: 'Отправить сообщение',
              child: ValueListenableBuilder<TextEditingValue>(
                valueListenable: controller,
                builder: (context, value, _) => FilledButton(
                  onPressed: isSending || value.text.trim().isEmpty
                      ? null
                      : onSend,
                  child: isSending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(
                          Icons.send,
                          semanticLabel: 'Отправить сообщение',
                        ),
                ),
              ),
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

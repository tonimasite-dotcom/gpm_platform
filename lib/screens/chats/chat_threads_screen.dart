import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi, chatService;
import '../../models/chat_models.dart';
import '../../services/gpm_api_service.dart';
import '../../theme/gpm_theme.dart';
import 'chat_conversation_screen.dart';

class ChatThreadsScreen extends StatefulWidget {
  final ChatRole role;

  const ChatThreadsScreen({
    super.key,
    required this.role,
  });

  @override
  State<ChatThreadsScreen> createState() => _ChatThreadsScreenState();
}

class _ChatThreadsScreenState extends State<ChatThreadsScreen> {
  late Future<_ThreadsData> _threadsFuture;
  _ThreadFilter _filter = _ThreadFilter.all;

  @override
  void initState() {
    super.initState();
    _threadsFuture = _loadThreads();
  }

  Future<_ThreadsData> _loadThreads() async {
    final orders = widget.role == ChatRole.worker
        ? await gpmApi.getOrdersForWorker(GpmApiService.demoWorkerId)
        : await gpmApi.getOrders();

    final threads = await chatService.getThreadsForRole(
      role: widget.role,
      orders: orders,
    );
    return _ThreadsData(
      threads: threads,
      ordersById: {
        for (final order in orders) order['id'].toString(): order,
      },
    );
  }

  void _refresh() {
    setState(() {
      _threadsFuture = _loadThreads();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_ThreadsData>(
      future: _threadsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(
              child: Text('Ошибка загрузки чатов: ${snapshot.error}'));
        }

        final data = snapshot.data ?? const _ThreadsData();
        final threads = data.threads;
        final visibleThreads = _applyFilter(threads);
        if (threads.isEmpty) {
          return RefreshIndicator(
            onRefresh: () async => _refresh(),
            child: ListView(
              children: [
                SizedBox(
                  height: MediaQuery.sizeOf(context).height * 0.45,
                  child: Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(
                        _emptyText,
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: GpmColors.graphite),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        }

        return RefreshIndicator(
          onRefresh: () async => _refresh(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
            children: [
              if (widget.role != ChatRole.logist) ...[
                _ChatPolicyBanner(role: widget.role),
                const SizedBox(height: 10),
              ],
              _ChatFilters(
                selected: _filter,
                role: widget.role,
                threads: threads,
                onSelected: (filter) => setState(() => _filter = filter),
              ),
              const SizedBox(height: 10),
              if (visibleThreads.isEmpty)
                _FilteredEmptyState(filter: _filter)
              else
                ...visibleThreads.map(
                  (thread) => _ThreadCard(
                    thread: thread,
                    order: data.ordersById[thread.orderId],
                    role: widget.role,
                    onTap: () async {
                      await Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ChatConversationScreen(
                            threadId: thread.id,
                            role: widget.role,
                          ),
                        ),
                      );
                      _refresh();
                    },
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  List<ChatThread> _applyFilter(List<ChatThread> threads) {
    return switch (_filter) {
      _ThreadFilter.all => threads,
      _ThreadFilter.attention => threads
          .where((thread) =>
              thread.requiresLogistAttention || thread.unreadCount > 0)
          .toList(),
      _ThreadFilter.orders => threads
          .where((thread) =>
              thread.type == ChatThreadType.clientLogist ||
              thread.type == ChatThreadType.workerLogist ||
              thread.type == ChatThreadType.clientWorker)
          .toList(),
      _ThreadFilter.support =>
        threads.where((thread) => thread.type == ChatThreadType.support).toList(),
      _ThreadFilter.archived =>
        threads.where((thread) => thread.isArchived).toList(),
    };
  }

  String get _emptyText {
    return switch (widget.role) {
      ChatRole.client =>
        'Чаты появятся после создания заказа и назначения исполнителей.',
      ChatRole.worker => 'Чаты появятся после отклика или назначения на заказ.',
      ChatRole.logist => 'Активных чатов пока нет.',
      ChatRole.system => 'Чатов нет.',
    };
  }
}

enum _ThreadFilter {
  all,
  attention,
  orders,
  support,
  archived,
}

class _ThreadsData {
  final List<ChatThread> threads;
  final Map<String, Map<String, dynamic>> ordersById;

  const _ThreadsData({
    this.threads = const [],
    this.ordersById = const {},
  });
}

class _ChatFilters extends StatelessWidget {
  final _ThreadFilter selected;
  final ChatRole role;
  final List<ChatThread> threads;
  final ValueChanged<_ThreadFilter> onSelected;

  const _ChatFilters({
    required this.selected,
    required this.role,
    required this.threads,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    final attentionCount = threads
        .where(
          (thread) => thread.requiresLogistAttention || thread.unreadCount > 0,
        )
        .length;
    final orderCount = threads
        .where((thread) =>
            thread.type == ChatThreadType.clientLogist ||
            thread.type == ChatThreadType.workerLogist ||
            thread.type == ChatThreadType.clientWorker)
        .length;
    final supportCount =
        threads.where((thread) => thread.type == ChatThreadType.support).length;
    final archivedCount = threads.where((thread) => thread.isArchived).length;

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          _FilterChipButton(
            label: 'Все',
            count: threads.length,
            selected: selected == _ThreadFilter.all,
            onTap: () => onSelected(_ThreadFilter.all),
          ),
          _FilterChipButton(
            label: role == ChatRole.logist ? 'Требуют ответа' : 'Новые',
            count: attentionCount,
            selected: selected == _ThreadFilter.attention,
            onTap: () => onSelected(_ThreadFilter.attention),
          ),
          _FilterChipButton(
            label: 'По заказам',
            count: orderCount,
            selected: selected == _ThreadFilter.orders,
            onTap: () => onSelected(_ThreadFilter.orders),
          ),
          _FilterChipButton(
            label: 'Поддержка',
            count: supportCount,
            selected: selected == _ThreadFilter.support,
            onTap: () => onSelected(_ThreadFilter.support),
          ),
          _FilterChipButton(
            label: 'Архив',
            count: archivedCount,
            selected: selected == _ThreadFilter.archived,
            onTap: () => onSelected(_ThreadFilter.archived),
          ),
        ],
      ),
    );
  }
}

class _FilterChipButton extends StatelessWidget {
  final String label;
  final int count;
  final bool selected;
  final VoidCallback onTap;

  const _FilterChipButton({
    required this.label,
    required this.count,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected ? GpmColors.red : GpmColors.graphite;

    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(
        label: Text('$label · $count'),
        selected: selected,
        onSelected: (_) => onTap(),
        selectedColor: GpmColors.red.withValues(alpha: 0.12),
        labelStyle: TextStyle(
          color: color,
          fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
        ),
        side: BorderSide(
          color: selected ? GpmColors.red : GpmColors.line,
        ),
        showCheckmark: false,
      ),
    );
  }
}

class _FilteredEmptyState extends StatelessWidget {
  final _ThreadFilter filter;

  const _FilteredEmptyState({required this.filter});

  @override
  Widget build(BuildContext context) {
    final text = switch (filter) {
      _ThreadFilter.attention => 'Чатов, требующих внимания, нет.',
      _ThreadFilter.orders => 'Чатов по заказам пока нет.',
      _ThreadFilter.support => 'Обращений в поддержку пока нет.',
      _ThreadFilter.archived => 'Архивных чатов пока нет.',
      _ThreadFilter.all => 'Чатов пока нет.',
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 16),
      child: Center(
        child: Text(
          text,
          textAlign: TextAlign.center,
          style: const TextStyle(color: GpmColors.graphite),
        ),
      ),
    );
  }
}

class _ThreadCard extends StatelessWidget {
  final ChatThread thread;
  final Map<String, dynamic>? order;
  final ChatRole role;
  final VoidCallback onTap;

  const _ThreadCard({
    required this.thread,
    required this.order,
    required this.role,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final status = _orderStatusText(order?['status']);
    final statusColor = _orderStatusColor(order?['status']);
    final scheduledAt = _formatScheduledAt(order?['scheduled_at']);
    final title = _threadTitle(thread, role, order);
    final subtitle = _threadSubtitle(thread, role, order);

    return Card(
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        leading: _ThreadIcon(thread: thread),
        title: Row(
          children: [
            Expanded(
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
            if (thread.requiresLogistAttention && role == ChatRole.logist)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: GpmColors.red.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'Требует ответа',
                  style: TextStyle(
                    color: GpmColors.red,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            const SizedBox(width: 8),
            Text(
              _formatUpdatedAt(thread.updatedAt),
              style: const TextStyle(
                color: GpmColors.graphite,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 5),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  _MiniPill(
                    text: _threadKindLabel(thread, role),
                    color: GpmColors.black,
                  ),
                  _MiniPill(text: status, color: statusColor),
                  if (scheduledAt.isNotEmpty)
                    _MiniPill(text: scheduledAt, color: GpmColors.graphite),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              if (thread.isArchived) ...[
                const SizedBox(height: 4),
                const Text(
                  'Архив: переписка доступна только для чтения',
                  style: TextStyle(fontSize: 12, color: Colors.grey),
                ),
              ],
            ],
          ),
        ),
        trailing: thread.unreadCount > 0
            ? Badge(
                label: Text('${thread.unreadCount}'),
                backgroundColor: Colors.red,
              )
            : const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }

  String _formatUpdatedAt(DateTime value) {
    final now = DateTime.now();
    final local = value.toLocal();
    if (local.year == now.year &&
        local.month == now.month &&
        local.day == now.day) {
      return '${local.hour.toString().padLeft(2, '0')}:'
          '${local.minute.toString().padLeft(2, '0')}';
    }

    return '${local.day.toString().padLeft(2, '0')}.'
        '${local.month.toString().padLeft(2, '0')}';
  }

  String _threadTitle(
    ChatThread thread,
    ChatRole role,
    Map<String, dynamic>? order,
  ) {
    final orderTitle = order?['title']?.toString();
    return switch (thread.type) {
      ChatThreadType.support => 'Поддержка 24/7',
      ChatThreadType.clientWorker => role == ChatRole.worker
          ? 'Клиент по заказу'
          : 'Исполнитель по заказу',
      ChatThreadType.clientLogist => orderTitle ?? 'Заказ',
      ChatThreadType.workerLogist => 'Координация выхода',
    };
  }

  String _threadSubtitle(
    ChatThread thread,
    ChatRole role,
    Map<String, dynamic>? order,
  ) {
    final address = order?['address']?.toString();
    final workers = order?['workers_count']?.toString();
    final hours = order?['hours']?.toString();
    final parts = [
      if (address != null && address.isNotEmpty) address,
      if (workers != null && workers.isNotEmpty) '$workers исполн.',
      if (hours != null && hours.isNotEmpty) '$hours ч',
    ];
    if (parts.isNotEmpty) return parts.join(' · ');
    return thread.subtitle;
  }

  String _threadKindLabel(ChatThread thread, ChatRole role) {
    return switch (thread.type) {
      ChatThreadType.support => 'Поддержка',
      ChatThreadType.clientWorker => 'Заказ',
      ChatThreadType.clientLogist =>
        role == ChatRole.client ? 'Заказ' : 'Клиент',
      ChatThreadType.workerLogist =>
        role == ChatRole.worker ? 'Заказ' : 'Исполнитель',
    };
  }
}

class _MiniPill extends StatelessWidget {
  final String text;
  final Color color;

  const _MiniPill({
    required this.text,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
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

class _ThreadIcon extends StatelessWidget {
  final ChatThread thread;

  const _ThreadIcon({required this.thread});

  @override
  Widget build(BuildContext context) {
    final icon = switch (thread.type) {
      ChatThreadType.clientLogist => Icons.support_agent,
      ChatThreadType.workerLogist => Icons.engineering,
      ChatThreadType.clientWorker => Icons.forum_outlined,
      ChatThreadType.support => Icons.warning_amber_rounded,
    };
    final color =
        thread.requiresLogistAttention ? GpmColors.red : GpmColors.black;

    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(icon, color: color),
    );
  }
}

class _ChatPolicyBanner extends StatelessWidget {
  final ChatRole role;

  const _ChatPolicyBanner({required this.role});

  @override
  Widget build(BuildContext context) {
    final text = role == ChatRole.logist
        ? 'Логисты видят рабочие переписки по заказам для контроля качества, координации и решения спорных ситуаций.'
        : 'Чаты привязаны к заказам. GPM может подключить логиста для поддержки и разрешения спорных ситуаций.';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF6D8),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE9CE73)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.verified_user_outlined, color: GpmColors.black),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
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

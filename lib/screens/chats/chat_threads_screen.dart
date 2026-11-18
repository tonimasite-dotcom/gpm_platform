import 'dart:async';
import 'package:flutter/material.dart';
import '../../main.dart' show gpmApi, chatService;
import '../../models/chat_models.dart';
import '../../services/gpm_api_service.dart';
import '../../theme/gpm_theme.dart';
import 'chat_conversation_screen.dart';

class ChatThreadsScreen extends StatefulWidget {
  final ChatRole role;
  const ChatThreadsScreen({super.key, required this.role});
  @override
  State<ChatThreadsScreen> createState() => _ChatThreadsScreenState();
}

class _ChatThreadsScreenState extends State<ChatThreadsScreen>
    with WidgetsBindingObserver {
  List<ChatThread>? _threads;
  final _search = TextEditingController();
  Timer? _timer;
  bool _refreshing = false,
      _active = true,
      _conversationOpen = false,
      _refreshFailed = false;
  String _query = '';
  _ThreadFilter _filter = _ThreadFilter.active;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (mounted &&
          _active &&
          !_conversationOpen &&
          TickerMode.of(context) &&
          ModalRoute.of(context)?.isCurrent == true) {
        _refresh();
      }
    });
  }

  @override
  void dispose() {
    _search.dispose();
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _active = state == AppLifecycleState.resumed;
    if (_active && mounted && !_conversationOpen) {
      _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    _refreshing = true;
    try {
      // Production thread metadata is self-contained; order discovery must
      // never prevent access to retained conversations and archives.
      final orders = gpmApi.isApiMode
          ? <Map<String, dynamic>>[]
          : widget.role == ChatRole.worker
          ? await gpmApi.getOrdersForWorker(GpmApiService.demoWorkerId)
          : await gpmApi.getOrders();
      final threads = List<ChatThread>.of(
        await chatService.getThreadsForRole(role: widget.role, orders: orders),
      );
      threads.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
      if (mounted) {
        setState(() {
          _threads = threads;
          _refreshFailed = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _refreshFailed = true);
    } finally {
      _refreshing = false;
    }
  }

  bool _matches(ChatThread t, _ThreadFilter filter) => switch (filter) {
    _ThreadFilter.active => !t.isArchived,
    _ThreadFilter.unread => !t.isArchived && t.unreadCount > 0,
    _ThreadFilter.archived => t.isArchived,
  };
  @override
  Widget build(BuildContext context) {
    final threads = _threads ?? [];
    final visible = threads
        .where(
          (t) => _query.isNotEmpty
              ? '${t.title} ${t.orderId} ${t.subtitle}'.toLowerCase().contains(
                  _query,
                )
              : _matches(t, _filter),
        )
        .toList();
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800),
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            key: PageStorageKey('chat-threads-${widget.role.name}'),
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
            children: [
              Text('Чаты', style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 14),
              TextField(
                controller: _search,
                decoration: InputDecoration(
                  hintText: 'Поиск по всем чатам',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: _query.isEmpty
                      ? null
                      : IconButton(
                          tooltip: 'Очистить поиск',
                          icon: const Icon(Icons.close),
                          onPressed: () => setState(() {
                            _search.clear();
                            _query = '';
                          }),
                        ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                ),
                onChanged: (value) =>
                    setState(() => _query = value.trim().toLowerCase()),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final filter in _ThreadFilter.values)
                    ChoiceChip(
                      label: Text(
                        '${filter.label} · ${threads.where((t) => _matches(t, filter)).length}',
                      ),
                      selected: _query.isEmpty && _filter == filter,
                      showCheckmark: false,
                      selectedColor: GpmColors.brandSoft,
                      labelStyle: TextStyle(
                        color: _filter == filter
                            ? GpmColors.redInk
                            : GpmColors.muted,
                      ),
                      onSelected: (_) => setState(() {
                        _filter = filter;
                        _query = '';
                        _search.clear();
                      }),
                    ),
                ],
              ),
              if (_query.isNotEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text(
                    'Результаты во всех чатах, включая архив',
                    style: TextStyle(color: GpmColors.muted, fontSize: 12),
                  ),
                ),
              if (_refreshFailed)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Text(
                          'Не удалось обновить чаты. Переписка сохранена.',
                        ),
                      ),
                      TextButton(
                        onPressed: _refresh,
                        child: const Text('Повторить'),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 12),
              if (_threads == null && !_refreshFailed)
                const Padding(
                  padding: EdgeInsets.all(48),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (visible.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: 48,
                    horizontal: 20,
                  ),
                  child: Column(
                    children: [
                      Icon(
                        _filter == _ThreadFilter.archived
                            ? Icons.archive_outlined
                            : Icons.forum_outlined,
                        color: GpmColors.muted,
                        size: 36,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        _emptyText,
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: GpmColors.muted),
                      ),
                    ],
                  ),
                )
              else
                Material(
                  color: GpmColors.surface,
                  borderRadius: BorderRadius.circular(20),
                  clipBehavior: Clip.antiAlias,
                  child: Column(
                    children: [
                      for (var i = 0; i < visible.length; i++) ...[
                        if (i > 0) const Divider(height: 1, indent: 76),
                        _ThreadRow(
                          thread: visible[i],
                          onTap: () => _open(visible[i]),
                        ),
                      ],
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _open(ChatThread thread) async {
    _conversationOpen = true;
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) =>
            ChatConversationScreen(threadId: thread.id, role: widget.role),
      ),
    );
    _conversationOpen = false;
    if (mounted) await _refresh();
  }

  String get _emptyText {
    if (_query.isNotEmpty) {
      return 'Ничего не найдено. Попробуйте номер заявки или другое слово.';
    }
    return switch (_filter) {
      _ThreadFilter.archived =>
        'Здесь останутся чаты завершенных и отмененных заявок. История доступна для чтения.',
      _ThreadFilter.unread => 'Все сообщения прочитаны.',
      _ThreadFilter.active =>
        'Чаты появятся после назначения исполнителя на заявку. Закрытые чаты остаются в архиве.',
    };
  }
}

enum _ThreadFilter {
  active('Активные'),
  unread('Непрочитанные'),
  archived('Архив');

  final String label;
  const _ThreadFilter(this.label);
}

class _ThreadRow extends StatelessWidget {
  final ChatThread thread;
  final VoidCallback onTap;
  const _ThreadRow({required this.thread, required this.onTap});
  @override
  Widget build(BuildContext context) => ListTile(
    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
    minVerticalPadding: 12,
    leading: CircleAvatar(
      radius: 23,
      backgroundColor: thread.isArchived ? GpmColors.page : GpmColors.brandSoft,
      child: Icon(
        thread.isArchived ? Icons.archive_outlined : Icons.forum_outlined,
        color: thread.isArchived ? GpmColors.muted : GpmColors.redInk,
        size: 22,
      ),
    ),
    title: Text(
      thread.title,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(
        fontSize: 15,
        fontWeight: thread.unreadCount > 0 ? FontWeight.w800 : FontWeight.w600,
      ),
    ),
    subtitle: Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(
        thread.subtitle.isEmpty ? 'Сообщений пока нет' : thread.subtitle,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(color: GpmColors.muted, fontSize: 13),
      ),
    ),
    trailing: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          _time(thread.updatedAt),
          style: const TextStyle(color: GpmColors.muted, fontSize: 11),
        ),
        const SizedBox(height: 6),
        if (thread.unreadCount > 0)
          Badge(
            label: Text('${thread.unreadCount}'),
            backgroundColor: GpmColors.redAction,
          )
        else if (thread.isArchived)
          const Text(
            'Архив',
            style: TextStyle(fontSize: 11, color: GpmColors.muted),
          )
        else if (thread.requiresLogistAttention)
          const Icon(Icons.priority_high, color: GpmColors.redInk, size: 16),
      ],
    ),
    onTap: onTap,
  );
  String _time(DateTime time) {
    final local = time.toLocal();
    return DateUtils.isSameDay(local, DateTime.now())
        ? '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}'
        : '${local.day.toString().padLeft(2, '0')}.${local.month.toString().padLeft(2, '0')}';
  }
}

import 'package:flutter/material.dart';

import '../../main.dart' show bitrix24, chatService;
import '../../models/chat_models.dart';
import '../../services/bitrix24_service.dart';
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
  late Future<List<ChatThread>> _threadsFuture;

  @override
  void initState() {
    super.initState();
    _threadsFuture = _loadThreads();
  }

  Future<List<ChatThread>> _loadThreads() async {
    final orders = widget.role == ChatRole.worker
        ? await bitrix24.getOrdersForWorker(Bitrix24Service.demoWorkerId)
        : await bitrix24.getOrders();

    return chatService.getThreadsForRole(
      role: widget.role,
      orders: orders,
    );
  }

  void _refresh() {
    setState(() {
      _threadsFuture = _loadThreads();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<ChatThread>>(
      future: _threadsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(child: Text('Ошибка загрузки чатов: ${snapshot.error}'));
        }

        final threads = snapshot.data ?? [];
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
              _ChatPolicyBanner(role: widget.role),
              const SizedBox(height: 10),
              ...threads.map(
                (thread) => _ThreadCard(
                  thread: thread,
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

  String get _emptyText {
    return switch (widget.role) {
      ChatRole.client =>
        'Чаты появятся после создания заказа и назначения исполнителей.',
      ChatRole.worker =>
        'Чаты появятся после отклика или назначения на заказ.',
      ChatRole.logist => 'Активных чатов пока нет.',
      ChatRole.system => 'Чатов нет.',
    };
  }
}

class _ThreadCard extends StatelessWidget {
  final ChatThread thread;
  final ChatRole role;
  final VoidCallback onTap;

  const _ThreadCard({
    required this.thread,
    required this.role,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        leading: _ThreadIcon(thread: thread),
        title: Row(
          children: [
            Expanded(
              child: Text(
                thread.title,
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
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 5),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(thread.typeLabel),
              const SizedBox(height: 3),
              Text(
                thread.subtitle,
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
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
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
    final color = thread.requiresLogistAttention ? GpmColors.red : GpmColors.black;

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

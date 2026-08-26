import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../theme/gpm_theme.dart';

class WorkerDashboardScreen extends StatefulWidget {
  const WorkerDashboardScreen({super.key});

  @override
  State<WorkerDashboardScreen> createState() => _WorkerDashboardScreenState();
}

class _WorkerDashboardScreenState extends State<WorkerDashboardScreen> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = gpmApi.isApiMode ? gpmApi.getMyDashboard() : _demoDashboard();
  }

  Future<Map<String, dynamic>> _demoDashboard() async {
    final orders = await gpmApi.getOrdersForWorker('worker-demo-1');
    final profile = await gpmApi.getWorkerProfile('worker-demo-1') ?? {};
    return {
      'username': profile['full_name'] ?? 'Исполнитель',
      'profile': {...profile, 'profile_completion': 100},
      'summary': {
        'available_orders': orders
            .where((order) => order['status'] == 'PROCESSED')
            .length,
        'pending_applications': orders
            .where((order) => order['worker_application_status'] == 'PENDING')
            .length,
        'active_orders': orders
            .where(
              (order) =>
                  order['is_assigned_to_worker'] == true &&
                  const {
                    'IN_PROCESS',
                    'DONE_PENDING',
                  }.contains(order['status']),
            )
            .length,
        'completed_orders': orders
            .where(
              (order) =>
                  order['is_assigned_to_worker'] == true &&
                  order['status'] == 'CONVERTED',
            )
            .length,
        'available_balance': 0,
      },
      'next_order': null,
    };
  }

  void _reload() {
    setState(() {
      _future = gpmApi.isApiMode ? gpmApi.getMyDashboard() : _demoDashboard();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return _DashboardError(onRetry: _reload);
        }
        final data = snapshot.data ?? const <String, dynamic>{};
        final summary = _asMap(data['summary']);
        final profile = _asMap(data['profile']);
        final nextOrder = data['next_order'] is Map
            ? _asMap(data['next_order'])
            : null;
        final displayName = profile['display_name']?.toString().trim();
        final username = data['username']?.toString() ?? 'Исполнитель';

        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 32),
            children: [
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1180),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _WelcomePanel(
                        name: displayName?.isNotEmpty == true
                            ? displayName!
                            : username,
                        completion: _asInt(profile['profile_completion']),
                      ),
                      const SizedBox(height: 16),
                      LayoutBuilder(
                        builder: (context, constraints) {
                          final columns = constraints.maxWidth >= 900
                              ? 5
                              : constraints.maxWidth >= 560
                              ? 3
                              : 2;
                          return GridView.count(
                            crossAxisCount: columns,
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            crossAxisSpacing: 10,
                            mainAxisSpacing: 10,
                            childAspectRatio: columns == 5 ? 1.55 : 1.45,
                            children: [
                              _MetricCard(
                                icon: Icons.search_outlined,
                                label: 'Доступные',
                                value: '${_asInt(summary['available_orders'])}',
                                color: Colors.blue,
                              ),
                              _MetricCard(
                                icon: Icons.hourglass_top_outlined,
                                label: 'Отклики',
                                value:
                                    '${_asInt(summary['pending_applications'])}',
                                color: Colors.orange,
                              ),
                              _MetricCard(
                                icon: Icons.work_outline,
                                label: 'В работе',
                                value: '${_asInt(summary['active_orders'])}',
                                color: Colors.purple,
                              ),
                              _MetricCard(
                                icon: Icons.task_alt,
                                label: 'Выполнено',
                                value: '${_asInt(summary['completed_orders'])}',
                                color: Colors.green,
                              ),
                              _MetricCard(
                                icon: Icons.account_balance_wallet_outlined,
                                label: 'К выплате',
                                value:
                                    '${_formatMoney(_asInt(summary['available_balance']))} ₽',
                                color: GpmColors.red,
                              ),
                            ],
                          );
                        },
                      ),
                      const SizedBox(height: 16),
                      LayoutBuilder(
                        builder: (context, constraints) {
                          final wide = constraints.maxWidth >= 760;
                          if (wide) {
                            return Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: _NextOrderPanel(order: nextOrder),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: _ProfileReadiness(profile: profile),
                                ),
                              ],
                            );
                          }
                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              _NextOrderPanel(order: nextOrder),
                              const SizedBox(height: 16),
                              _ProfileReadiness(profile: profile),
                            ],
                          );
                        },
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _WelcomePanel extends StatelessWidget {
  final String name;
  final int completion;

  const _WelcomePanel({required this.name, required this.completion});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: GpmColors.line),
      ),
      child: Row(
        children: [
          const CircleAvatar(
            radius: 27,
            backgroundColor: GpmColors.red,
            foregroundColor: Colors.white,
            child: Icon(Icons.engineering_outlined, size: 29),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Здравствуйте, $name',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 5),
                const Text(
                  'Заказы, отклики и расчёты по вашему аккаунту',
                  style: TextStyle(color: GpmColors.graphite),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: completion == 100
                  ? Colors.green.withValues(alpha: .1)
                  : Colors.orange.withValues(alpha: .12),
              borderRadius: BorderRadius.circular(30),
            ),
            child: Text(
              'Профиль $completion%',
              style: TextStyle(
                color: completion == 100
                    ? Colors.green[800]
                    : Colors.orange[900],
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _MetricCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: color, size: 24),
          const Spacer(),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
          ),
          Text(label, style: const TextStyle(color: GpmColors.graphite)),
        ],
      ),
    );
  }
}

class _NextOrderPanel extends StatelessWidget {
  final Map<String, dynamic>? order;

  const _NextOrderPanel({required this.order});

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Ближайший заказ',
      icon: Icons.event_available_outlined,
      child: order == null
          ? const _CleanEmptyState(
              icon: Icons.event_busy_outlined,
              title: 'Назначенных заказов пока нет',
              subtitle: 'Новые заявки появятся во вкладке «Заказы».',
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  order!['title']?.toString() ?? 'Заказ',
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 12),
                _Fact(
                  icon: Icons.schedule_outlined,
                  text: _formatDate(order!['scheduled_at']),
                ),
                if ((order!['city']?.toString() ?? '').isNotEmpty)
                  _Fact(
                    icon: Icons.location_city_outlined,
                    text: order!['city'].toString(),
                  ),
                _Fact(
                  icon: Icons.info_outline,
                  text: _statusLabel(order!['status']?.toString()),
                ),
              ],
            ),
    );
  }
}

class _ProfileReadiness extends StatelessWidget {
  final Map<String, dynamic> profile;

  const _ProfileReadiness({required this.profile});

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Статус профиля',
      icon: Icons.verified_user_outlined,
      child: Column(
        children: [
          _StatusLine(
            label: 'Основные данные',
            ready: _asInt(profile['profile_completion']) == 100,
            value: '${_asInt(profile['profile_completion'])}%',
          ),
          _StatusLine(
            label: 'Личность',
            ready: profile['identity_status'] == 'verified',
            value: _verificationLabel(profile['identity_status']),
          ),
          _StatusLine(
            label: 'Право на работу',
            ready: profile['work_status'] == 'verified',
            value: _verificationLabel(profile['work_status']),
          ),
          _StatusLine(
            label: 'Статус НПД',
            ready: profile['npd_status'] == 'verified',
            value: _verificationLabel(profile['npd_status']),
          ),
        ],
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;

  const _Panel({required this.title, required this.icon, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: GpmColors.red),
              const SizedBox(width: 9),
              Text(title, style: Theme.of(context).textTheme.titleLarge),
            ],
          ),
          const SizedBox(height: 18),
          child,
        ],
      ),
    );
  }
}

class _StatusLine extends StatelessWidget {
  final String label;
  final bool ready;
  final String value;

  const _StatusLine({
    required this.label,
    required this.ready,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Icon(
            ready ? Icons.check_circle : Icons.radio_button_unchecked,
            size: 20,
            color: ready ? Colors.green : Colors.grey,
          ),
          const SizedBox(width: 9),
          Expanded(child: Text(label)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}

class _Fact extends StatelessWidget {
  final IconData icon;
  final String text;

  const _Fact({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        children: [
          Icon(icon, size: 18, color: GpmColors.graphite),
          const SizedBox(width: 8),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

class _CleanEmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  const _CleanEmptyState({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Center(
        child: Column(
          children: [
            Icon(icon, color: Colors.grey[400], size: 38),
            const SizedBox(height: 10),
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: const TextStyle(color: GpmColors.graphite),
            ),
          ],
        ),
      ),
    );
  }
}

class _DashboardError extends StatelessWidget {
  final VoidCallback onRetry;

  const _DashboardError({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_outlined, size: 44),
            const SizedBox(height: 12),
            const Text('Не удалось загрузить кабинет'),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Повторить'),
            ),
          ],
        ),
      ),
    );
  }
}

Map<String, dynamic> _asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return <String, dynamic>{};
}

int _asInt(dynamic value) => int.tryParse(value?.toString() ?? '') ?? 0;

String _formatMoney(int value) {
  return value.toString().replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ' ',
  );
}

String _formatDate(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (date == null) return 'Дата уточняется';
  final day = date.day.toString().padLeft(2, '0');
  final month = date.month.toString().padLeft(2, '0');
  final hour = date.hour.toString().padLeft(2, '0');
  final minute = date.minute.toString().padLeft(2, '0');
  return '$day.$month.${date.year}, $hour:$minute';
}

String _statusLabel(String? status) => switch (status) {
  'NEW' => 'На проверке',
  'PROCESSED' => 'Открыт для откликов',
  'IN_PROCESS' => 'В работе',
  'DONE_PENDING' => 'Ожидает подтверждения',
  'CONVERTED' => 'Завершён',
  _ => 'Статус уточняется',
};

String _verificationLabel(dynamic status) => switch (status?.toString()) {
  'verified' => 'Подтверждено',
  'pending' => 'На проверке',
  'rejected' => 'Нужно исправить',
  _ => 'Не заполнено',
};

import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../services/gpm_api_service.dart';
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
    _future = _loadDashboard();
  }

  Future<Map<String, dynamic>> _loadDashboard() async {
    if (gpmApi.isApiMode) return gpmApi.getMyDashboard();

    final orders = await gpmApi.getOrdersForWorker(GpmApiService.demoWorkerId);
    final profile =
        await gpmApi.getWorkerProfile(GpmApiService.demoWorkerId) ?? {};
    return {
      'profile': profile,
      'summary': {
        'pending_applications': orders
            .where((order) => order['worker_application_status'] == 'PENDING')
            .length,
        'active_orders': orders
            .where(
              (order) =>
                  order['is_assigned_to_worker'] == true &&
                  const {
                    'PROCESSED',
                    'IN_PROCESS',
                    'DONE_PENDING',
                  }.contains(order['status']),
            )
            .length,
        'available_balance': 0,
      },
    };
  }

  Future<void> _reload() async {
    setState(() => _future = _loadDashboard());
    await _future;
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
        final activeApplications =
            _asInt(summary['active_orders']) +
            _asInt(summary['pending_applications']);

        return RefreshIndicator(
          onRefresh: _reload,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(14, 16, 14, 32),
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: GpmColors.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: GpmColors.line),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Кабинет исполнителя',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Берите доступные заявки, отслеживайте назначенные '
                      'смены и контролируйте выплаты.',
                      style: TextStyle(color: GpmColors.graphite),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(
                      child: _DashboardStat(
                        icon: Icons.assignment_outlined,
                        accent: GpmColors.red,
                        label: 'Активные заявки',
                        value: '$activeApplications',
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _DashboardStat(
                        icon: Icons.star_outline,
                        accent: GpmColors.yellow,
                        label: 'Рейтинг',
                        value: '${_asInt(profile['rating'])}',
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _DashboardStat(
                        icon: Icons.account_balance_wallet_outlined,
                        accent: GpmColors.graphite,
                        label: 'Выплаты',
                        value:
                            '${_formatMoney(_asInt(summary['available_balance']))} ₽',
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _DashboardStat extends StatelessWidget {
  final IconData icon;
  final Color accent;
  final String label;
  final String value;

  const _DashboardStat({
    required this.icon,
    required this.accent,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: accent.withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: accent, size: 20),
          const SizedBox(height: 8),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              style: const TextStyle(
                color: GpmColors.black,
                fontSize: 20,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              color: GpmColors.graphite,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _DashboardError extends StatelessWidget {
  final Future<void> Function() onRetry;

  const _DashboardError({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('Не удалось загрузить кабинет исполнителя'),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: onRetry, child: const Text('Повторить')),
        ],
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

int _asInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.round();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

String _formatMoney(int value) {
  return value.toString().replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ' ',
  );
}

import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;

class LogistAnalyticsScreen extends StatefulWidget {
  const LogistAnalyticsScreen({super.key});

  @override
  State<LogistAnalyticsScreen> createState() => _LogistAnalyticsScreenState();
}

class _LogistAnalyticsScreenState extends State<LogistAnalyticsScreen> {
  late Future<_AnalyticsData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_AnalyticsData> _load() async {
    final orders = await gpmApi.getOrders();
    final applicationsByOrder = <String, int>{};
    var totalApplications = 0;
    var pendingApplications = 0;

    for (final order in orders) {
      final id = order['id']?.toString() ?? '';
      if (id.isEmpty) continue;
      final applications = await gpmApi.getApplicationsForOrder(id);
      applicationsByOrder[id] = applications.length;
      totalApplications += applications.length;
      pendingApplications += applications
          .where((application) => application['status'] == 'PENDING')
          .length;
    }

    return _AnalyticsData(
      orders: orders,
      applicationsByOrder: applicationsByOrder,
      totalApplications: totalApplications,
      pendingApplications: pendingApplications,
    );
  }

  void _refresh() {
    setState(() {
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_AnalyticsData>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(
            child: Text('Ошибка загрузки аналитики: ${snapshot.error}'),
          );
        }

        final data = snapshot.data ?? _AnalyticsData.empty();

        return RefreshIndicator(
          onRefresh: () async => _refresh(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Аналитика',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Обновить',
                    onPressed: _refresh,
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _KpiGrid(data: data),
              const SizedBox(height: 16),
              _Section(
                title: 'Статусы заказов',
                child: _StatusBreakdown(data: data),
              ),
              const SizedBox(height: 16),
              _Section(
                title: 'Загрузка исполнителями',
                child: _WorkforcePanel(data: data),
              ),
              const SizedBox(height: 16),
              _Section(
                title: 'Источники и формат работ',
                child: _SourceAndModePanel(data: data),
              ),
              const SizedBox(height: 16),
              _Section(
                title: 'Ближайшие заявки',
                child: _UpcomingOrders(data: data),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _KpiGrid extends StatelessWidget {
  final _AnalyticsData data;

  const _KpiGrid({required this.data});

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: MediaQuery.of(context).size.width > 720 ? 4 : 2,
      childAspectRatio: MediaQuery.of(context).size.width > 720 ? 2.4 : 1.75,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 10,
      mainAxisSpacing: 10,
      children: [
        _KpiCard(
          icon: Icons.assignment_outlined,
          label: 'Всего заказов',
          value: data.totalOrders.toString(),
          color: Colors.indigo,
        ),
        _KpiCard(
          icon: Icons.cloud_done_outlined,
          label: 'Внешние',
          value: data.crmOrders.toString(),
          color: Colors.blue,
        ),
        _KpiCard(
          icon: Icons.groups_outlined,
          label: 'Нужно людей',
          value: data.requiredWorkers.toString(),
          color: Colors.orange,
        ),
        _KpiCard(
          icon: Icons.how_to_reg_outlined,
          label: 'Назначено',
          value: data.assignedWorkers.toString(),
          color: Colors.green,
        ),
        _KpiCard(
          icon: Icons.mark_email_unread_outlined,
          label: 'Отклики',
          value: data.totalApplications.toString(),
          color: Colors.purple,
        ),
        _KpiCard(
          icon: Icons.pending_actions_outlined,
          label: 'Ждут решения',
          value: data.pendingApplications.toString(),
          color: Colors.deepOrange,
        ),
        _KpiCard(
          icon: Icons.payments_outlined,
          label: 'Средняя ставка',
          value: data.averageRate == 0 ? '-' : '${data.averageRate} ₽',
          color: Colors.teal,
        ),
        _KpiCard(
          icon: Icons.warning_amber_outlined,
          label: 'Недобор',
          value: data.workerShortage.toString(),
          color: data.workerShortage > 0 ? Colors.red : Colors.green,
        ),
      ],
    );
  }
}

class _KpiCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _KpiCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.black12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Icon(icon, color: color),
            Text(
              value,
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
            ),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final Widget child;

  const _Section({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.black12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}

class _StatusBreakdown extends StatelessWidget {
  final _AnalyticsData data;

  const _StatusBreakdown({required this.data});

  @override
  Widget build(BuildContext context) {
    final entries = data.statusCounts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    if (entries.isEmpty) return const Text('Заказов пока нет');

    return Column(
      children: entries
          .map(
            (entry) => _ProgressRow(
              label: _statusText(entry.key),
              value: entry.value,
              total: data.totalOrders,
              color: _statusColor(entry.key),
            ),
          )
          .toList(),
    );
  }
}

class _WorkforcePanel extends StatelessWidget {
  final _AnalyticsData data;

  const _WorkforcePanel({required this.data});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _ProgressRow(
          label: 'Назначено людей',
          value: data.assignedWorkers,
          total: data.requiredWorkers == 0 ? 1 : data.requiredWorkers,
          color: Colors.green,
        ),
        _ProgressRow(
          label: 'Недобор людей',
          value: data.workerShortage,
          total: data.requiredWorkers == 0 ? 1 : data.requiredWorkers,
          color: data.workerShortage > 0 ? Colors.red : Colors.green,
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: Text(
            'Отклики: ${data.totalApplications}, ждут решения: ${data.pendingApplications}',
          ),
        ),
      ],
    );
  }
}

class _SourceAndModePanel extends StatelessWidget {
  final _AnalyticsData data;

  const _SourceAndModePanel({required this.data});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _ProgressRow(
          label: 'Внешняя система',
          value: data.crmOrders,
          total: data.totalOrders == 0 ? 1 : data.totalOrders,
          color: Colors.indigo,
        ),
        _ProgressRow(
          label: 'Ручные',
          value: data.manualOrders,
          total: data.totalOrders == 0 ? 1 : data.totalOrders,
          color: Colors.blueGrey,
        ),
        const Divider(height: 20),
        _ProgressRow(
          label: 'Ставка',
          value: data.rateOrders,
          total: data.totalOrders == 0 ? 1 : data.totalOrders,
          color: Colors.teal,
        ),
        _ProgressRow(
          label: 'Смена',
          value: data.shiftOrders,
          total: data.totalOrders == 0 ? 1 : data.totalOrders,
          color: Colors.orange,
        ),
      ],
    );
  }
}

class _UpcomingOrders extends StatelessWidget {
  final _AnalyticsData data;

  const _UpcomingOrders({required this.data});

  @override
  Widget build(BuildContext context) {
    final upcoming = data.upcomingOrders.take(5).toList();
    if (upcoming.isEmpty) return const Text('Ближайших заявок нет');

    return Column(
      children: upcoming
          .map(
            (order) => ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(
                order['title']?.toString() ?? 'Заказ',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              subtitle: Text(_formatSchedule(order['scheduled_at'])),
              trailing: _MiniStatus(status: order['status']),
            ),
          )
          .toList(),
    );
  }
}

class _ProgressRow extends StatelessWidget {
  final String label;
  final int value;
  final int total;
  final Color color;

  const _ProgressRow({
    required this.label,
    required this.value,
    required this.total,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final progress = total <= 0 ? 0.0 : (value / total).clamp(0.0, 1.0);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          SizedBox(
            width: 150,
            child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 8,
                backgroundColor: color.withValues(alpha: 0.12),
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 34,
            child: Text(
              value.toString(),
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniStatus extends StatelessWidget {
  final dynamic status;

  const _MiniStatus({required this.status});

  @override
  Widget build(BuildContext context) {
    final color = _statusColor(status);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Text(
          _statusText(status),
          style: TextStyle(fontSize: 11, color: color),
        ),
      ),
    );
  }
}

class _AnalyticsData {
  final List<Map<String, dynamic>> orders;
  final Map<String, int> applicationsByOrder;
  final int totalApplications;
  final int pendingApplications;

  const _AnalyticsData({
    required this.orders,
    required this.applicationsByOrder,
    required this.totalApplications,
    required this.pendingApplications,
  });

  factory _AnalyticsData.empty() {
    return const _AnalyticsData(
      orders: [],
      applicationsByOrder: {},
      totalApplications: 0,
      pendingApplications: 0,
    );
  }

  int get totalOrders => orders.length;

  int get crmOrders =>
      orders.where(gpmApi.isExternalOrder).length;

  int get manualOrders => totalOrders - crmOrders;

  int get rateOrders =>
      orders.where((order) => order['work_mode'] == 'rate').length;

  int get shiftOrders =>
      orders.where((order) => order['work_mode'] == 'shift').length;

  int get requiredWorkers => orders.fold(
        0,
        (sum, order) => sum + _readInt(order['workers_count']),
      );

  int get assignedWorkers => orders.fold(0, (sum, order) {
        final ids = order['assigned_worker_ids'];
        return sum + (ids is List ? ids.length : 0);
      });

  int get workerShortage {
    final value = requiredWorkers - assignedWorkers;
    return value < 0 ? 0 : value;
  }

  int get averageRate {
    final rates = orders
        .map((order) => _readInt(order['price_per_hour']))
        .where((value) => value > 0)
        .toList();
    if (rates.isEmpty) return 0;
    return (rates.reduce((a, b) => a + b) / rates.length).round();
  }

  Map<String, int> get statusCounts {
    final result = <String, int>{};
    for (final order in orders) {
      final status = order['status']?.toString() ?? 'UNKNOWN';
      result[status] = (result[status] ?? 0) + 1;
    }
    return result;
  }

  List<Map<String, dynamic>> get upcomingOrders {
    final list = orders.where((order) {
      final scheduledAt = DateTime.tryParse(order['scheduled_at']?.toString() ?? '');
      return scheduledAt != null;
    }).toList();
    list.sort(
      (a, b) => (a['scheduled_at'] ?? '').toString().compareTo(
            (b['scheduled_at'] ?? '').toString(),
          ),
    );
    return list;
  }
}

int _readInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.round();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

String _formatSchedule(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '');
  if (date == null) return 'Дата не указана';
  final local = date.toLocal();
  return '${local.day.toString().padLeft(2, '0')}.'
      '${local.month.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

String _statusText(dynamic status) {
  switch (status?.toString()) {
    case 'NEW':
      return 'На модерации';
    case 'PROCESSED':
      return 'Одобрен';
    case 'IN_PROCESS':
      return 'В работе';
    case 'DONE_PENDING':
      return 'На подтверждении';
    case 'CONVERTED':
      return 'Завершен';
    case 'JUNK':
      return 'Отклонен';
    default:
      return 'Неизвестно';
  }
}

Color _statusColor(dynamic status) {
  switch (status?.toString()) {
    case 'NEW':
      return Colors.orange;
    case 'PROCESSED':
      return Colors.blue;
    case 'IN_PROCESS':
      return Colors.green;
    case 'DONE_PENDING':
      return Colors.deepOrange;
    case 'CONVERTED':
      return Colors.grey;
    case 'JUNK':
      return Colors.red;
    default:
      return Colors.grey;
  }
}

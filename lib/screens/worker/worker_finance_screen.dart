import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../services/gpm_api_service.dart';
import '../../theme/gpm_theme.dart';

class WorkerFinanceScreen extends StatefulWidget {
  const WorkerFinanceScreen({super.key});

  @override
  State<WorkerFinanceScreen> createState() => _WorkerFinanceScreenState();
}

class _WorkerFinanceScreenState extends State<WorkerFinanceScreen> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = gpmApi.isApiMode ? gpmApi.getMyFinance() : _loadDemoFinance();
  }

  Future<Map<String, dynamic>> _loadDemoFinance() async {
    final orders = await gpmApi.getOrdersForWorker(GpmApiService.demoWorkerId);
    final transactions = orders
        .where(
          (order) =>
              order['is_assigned_to_worker'] == true &&
              const {'DONE_PENDING', 'CONVERTED'}.contains(order['status']),
        )
        .map((order) {
          final amount = _orderAmount(order);
          return {
            'id': 'demo-${order['id']}',
            'order_id': order['id'],
            'title': order['title'] ?? 'Выполненный заказ',
            'amount': amount,
            'status': order['status'] == 'CONVERTED' ? 'available' : 'pending',
            'date': order['scheduled_at'] ?? order['created_at'],
          };
        })
        .toList();
    final available = transactions
        .where((item) => item['status'] == 'available')
        .fold<int>(0, (sum, item) => sum + _asInt(item['amount']));
    final pending = transactions
        .where((item) => item['status'] == 'pending')
        .fold<int>(0, (sum, item) => sum + _asInt(item['amount']));
    return {
      'available': available,
      'pending': pending,
      'total_accrued': available,
      'currency': 'RUB',
      'transactions': transactions,
      'payout': {'configured': false, 'method': ''},
    };
  }

  void _reload() {
    setState(() {
      _future = gpmApi.isApiMode ? gpmApi.getMyFinance() : _loadDemoFinance();
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
          return _FinanceError(onRetry: _reload);
        }
        final data = snapshot.data ?? const <String, dynamic>{};
        final payout = _asMap(data['payout']);
        final transactions = (data['transactions'] as List? ?? const [])
            .whereType<Map>()
            .map(
              (item) =>
                  item.map((key, value) => MapEntry(key.toString(), value)),
            )
            .toList();

        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 32),
            children: [
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1050),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _BalancePanel(
                        available: _asInt(data['available']),
                        pending: _asInt(data['pending']),
                        total: _asInt(data['total_accrued']),
                        payoutConfigured: payout['configured'] == true,
                        payoutMethod: payout['method']?.toString() ?? '',
                      ),
                      const SizedBox(height: 16),
                      _TransactionsPanel(transactions: transactions),
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

class _BalancePanel extends StatelessWidget {
  final int available;
  final int pending;
  final int total;
  final bool payoutConfigured;
  final String payoutMethod;

  const _BalancePanel({
    required this.available,
    required this.pending,
    required this.total,
    required this.payoutConfigured,
    required this.payoutMethod,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
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
              const CircleAvatar(
                backgroundColor: GpmColors.red,
                foregroundColor: Colors.white,
                child: Icon(Icons.account_balance_wallet_outlined),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Финансы',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const Text(
                      'Начисления по подтверждённым заказам',
                      style: TextStyle(color: GpmColors.graphite),
                    ),
                  ],
                ),
              ),
              _PayoutStatus(configured: payoutConfigured, method: payoutMethod),
            ],
          ),
          const SizedBox(height: 24),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              _MoneyCard(
                label: 'Доступно к выплате',
                value: available,
                icon: Icons.payments_outlined,
                color: Colors.green,
              ),
              _MoneyCard(
                label: 'На подтверждении',
                value: pending,
                icon: Icons.schedule_outlined,
                color: Colors.orange,
              ),
              _MoneyCard(
                label: 'Начислено всего',
                value: total,
                icon: Icons.account_balance_outlined,
                color: Colors.blue,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MoneyCard extends StatelessWidget {
  final String label;
  final int value;
  final IconData icon;
  final Color color;

  const _MoneyCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 250,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .07),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: .2)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: const TextStyle(color: GpmColors.graphite)),
                const SizedBox(height: 4),
                Text(
                  '${_formatMoney(value)} ₽',
                  style: const TextStyle(
                    fontSize: 21,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PayoutStatus extends StatelessWidget {
  final bool configured;
  final String method;

  const _PayoutStatus({required this.configured, required this.method});

  @override
  Widget build(BuildContext context) {
    final text = configured
        ? method == 'account'
              ? 'Счёт настроен'
              : 'Карта настроена'
        : 'Добавьте реквизиты';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
      decoration: BoxDecoration(
        color: configured
            ? Colors.green.withValues(alpha: .1)
            : Colors.orange.withValues(alpha: .12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: configured ? Colors.green[800] : Colors.orange[900],
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _TransactionsPanel extends StatelessWidget {
  final List<Map<String, dynamic>> transactions;

  const _TransactionsPanel({required this.transactions});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'История начислений',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          if (transactions.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 36),
              child: Center(
                child: Column(
                  children: [
                    Icon(
                      Icons.receipt_long_outlined,
                      size: 42,
                      color: Colors.grey,
                    ),
                    SizedBox(height: 10),
                    Text(
                      'Начислений пока нет',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'Они появятся после подтверждения выполненного заказа.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: GpmColors.graphite),
                    ),
                  ],
                ),
              ),
            )
          else
            ...transactions.map((transaction) {
              final available = transaction['status'] == 'available';
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: CircleAvatar(
                  backgroundColor: (available ? Colors.green : Colors.orange)
                      .withValues(alpha: .1),
                  child: Icon(
                    available ? Icons.done : Icons.schedule,
                    color: available ? Colors.green : Colors.orange,
                  ),
                ),
                title: Text(
                  transaction['title']?.toString() ?? 'Заказ',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                subtitle: Text(
                  '${_formatDate(transaction['date'])} · '
                  '${available ? 'доступно' : 'на подтверждении'}',
                ),
                trailing: Text(
                  '+${_formatMoney(_asInt(transaction['amount']))} ₽',
                  style: const TextStyle(
                    color: Colors.green,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}

class _FinanceError extends StatelessWidget {
  final VoidCallback onRetry;

  const _FinanceError({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off_outlined, size: 44),
          const SizedBox(height: 12),
          const Text('Не удалось загрузить начисления'),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Повторить'),
          ),
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

int _asInt(dynamic value) => int.tryParse(value?.toString() ?? '') ?? 0;

int _orderAmount(Map<String, dynamic> order) {
  final fixed = int.tryParse(order['individual_price']?.toString() ?? '');
  if (fixed != null) return fixed;
  final rate = int.tryParse(order['price_per_hour']?.toString() ?? '') ?? 0;
  final hours = int.tryParse(order['hours']?.toString() ?? '') ?? 0;
  return rate * hours;
}

String _formatMoney(int value) => value.toString().replaceAllMapped(
  RegExp(r'\B(?=(\d{3})+(?!\d))'),
  (_) => ' ',
);

String _formatDate(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (date == null) return 'Дата не указана';
  return '${date.day.toString().padLeft(2, '0')}.'
      '${date.month.toString().padLeft(2, '0')}.${date.year}';
}

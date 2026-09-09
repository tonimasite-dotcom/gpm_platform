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
    _future = _loadFinance();
  }

  Future<Map<String, dynamic>> _loadFinance() async {
    if (gpmApi.isApiMode) return gpmApi.getMyFinance();

    final orders = await gpmApi.getOrdersForWorker(GpmApiService.demoWorkerId);
    final transactions = orders
        .where(
          (order) =>
              order['is_assigned_to_worker'] == true &&
              const {'DONE_PENDING', 'CONVERTED'}.contains(order['status']),
        )
        .map(
          (order) => {
            'id': 'demo-${order['id']}',
            'title': order['title'] ?? 'Выполненный заказ',
            'amount': _orderAmount(order),
            'status': order['status'] == 'CONVERTED' ? 'available' : 'pending',
            'date': order['scheduled_at'] ?? order['created_at'],
          },
        )
        .toList();
    final available = transactions
        .where((item) => item['status'] == 'available')
        .fold<int>(0, (sum, item) => sum + _asInt(item['amount']));
    return {'available': available, 'transactions': transactions};
  }

  Future<void> _reload() async {
    setState(() => _future = _loadFinance());
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
          return Center(
            child: OutlinedButton(
              onPressed: _reload,
              child: const Text('Не удалось загрузить. Повторить'),
            ),
          );
        }

        final data = snapshot.data ?? const <String, dynamic>{};
        final transactions = (data['transactions'] as List? ?? const [])
            .whereType<Map>()
            .map(
              (item) =>
                  item.map((key, value) => MapEntry(key.toString(), value)),
            )
            .toList();
        final completedCount = transactions
            .where((item) => item['status'] == 'available')
            .length;

        return RefreshIndicator(
          onRefresh: _reload,
          child: ListView(
            padding: const EdgeInsets.only(bottom: 32),
            children: [
              Container(
                width: double.infinity,
                margin: const EdgeInsets.all(14),
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: GpmColors.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: GpmColors.line),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Доступно к выводу',
                      style: TextStyle(
                        color: GpmColors.graphite,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 10,
                      ),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFFF6D8),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFFE9CE73)),
                      ),
                      child: Text(
                        '${_formatMoney(_asInt(data['available']))} ₽',
                        style: const TextStyle(
                          color: GpmColors.black,
                          fontSize: 26,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Завершенных заказов: $completedCount',
                      style: const TextStyle(color: GpmColors.graphite),
                    ),
                    const SizedBox(height: 14),
                    const SizedBox(
                      width: double.infinity,
                      child: FilledButton(
                        onPressed: null,
                        child: Text('Вывести деньги'),
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Вывод средств скоро будет доступен',
                      style: TextStyle(color: GpmColors.graphite, fontSize: 12),
                    ),
                  ],
                ),
              ),
              const Padding(
                padding: EdgeInsets.fromLTRB(14, 14, 14, 8),
                child: Text(
                  'История начислений',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
              if (transactions.isEmpty)
                const SizedBox(
                  height: 240,
                  child: Center(child: Text('Начислений пока нет')),
                )
              else
                ...transactions.map(
                  (transaction) => _TransactionTile(transaction: transaction),
                ),
            ],
          ),
        );
      },
    );
  }
}

class _TransactionTile extends StatelessWidget {
  final Map<String, dynamic> transaction;

  const _TransactionTile({required this.transaction});

  @override
  Widget build(BuildContext context) {
    final available = transaction['status'] == 'available';
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: (available ? Colors.green : Colors.orange)
              .withValues(alpha: 0.1),
          child: Icon(
            available ? Icons.arrow_downward : Icons.schedule,
            color: available ? Colors.green : Colors.orange,
            size: 18,
          ),
        ),
        title: Text(transaction['title']?.toString() ?? 'Начисление'),
        subtitle: Text(available ? 'Доступно к выводу' : 'На подтверждении'),
        trailing: Text(
          '+${_formatMoney(_asInt(transaction['amount']))} ₽',
          style: const TextStyle(
            color: Colors.green,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

int _orderAmount(Map<String, dynamic> order) {
  // Worker payout is derived from the performer rate, not the client-facing
  // price (individual_price / legal_price) — that would show GPM's margin as
  // the worker's earnings.
  final hours = _asInt(order['hours']);
  final rate = _asInt(order['price_per_hour']) != 0
      ? _asInt(order['price_per_hour'])
      : _asInt(order['price_state']) != 0
      ? _asInt(order['price_state'])
      : _asInt(order['price_regular']);
  return rate * hours;
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

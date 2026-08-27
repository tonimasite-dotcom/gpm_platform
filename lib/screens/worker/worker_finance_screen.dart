import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../services/gpm_api_service.dart';

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
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  gradient: const LinearGradient(
                    colors: [Color(0xFF5B4FFF), Color(0xFF8A7FFF)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 8,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Доступно к выводу',
                      style: TextStyle(color: Colors.white70),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '${_formatMoney(_asInt(data['available']))} ₽',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Завершенных заказов: $completedCount',
                      style: const TextStyle(color: Colors.white70),
                    ),
                    const SizedBox(height: 12),
                    const SizedBox(
                      width: double.infinity,
                      child: FilledButton.tonal(
                        onPressed: null,
                        child: Text('Вывести деньги'),
                      ),
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
  final fixed = _asInt(order['individual_price']);
  if (fixed > 0) return fixed;
  return _asInt(order['price_per_hour']) * _asInt(order['hours']);
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

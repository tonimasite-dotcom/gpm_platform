import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../services/gpm_api_service.dart';

class WorkerFinanceScreen extends StatefulWidget {
  const WorkerFinanceScreen({super.key});

  @override
  State<WorkerFinanceScreen> createState() => _WorkerFinanceScreenState();
}

class _WorkerFinanceScreenState extends State<WorkerFinanceScreen> {
  late Future<List<Map<String, dynamic>>> _ordersFuture;

  @override
  void initState() {
    super.initState();
    _ordersFuture = _loadCompletedOrders();
  }

  Future<List<Map<String, dynamic>>> _loadCompletedOrders() async {
    final orders = await gpmApi.getOrdersForWorker(GpmApiService.demoWorkerId);
    return orders
        .where(
          (order) =>
              order['is_assigned_to_worker'] == true &&
              order['status'] == 'CONVERTED',
        )
        .toList();
  }

  int _incomeForOrder(Map<String, dynamic> order) {
    final hours = order['hours'] as int? ?? 1;
    return hours * 600;
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _ordersFuture,
      builder: (context, snapshot) {
        final orders = snapshot.data ?? [];
        final balance = orders.fold<int>(
          0,
          (sum, order) => sum + _incomeForOrder(order),
        );

        return Column(
          children: [
            Container(
              width: double.infinity,
              margin: const EdgeInsets.all(16),
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
                    style: TextStyle(fontSize: 14, color: Colors.white70),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${_formatMoney(balance)} ₽',
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Завершенных заказов: ${orders.length}',
                    style: const TextStyle(fontSize: 13, color: Colors.white70),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.tonal(
                      style: FilledButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: const Color(0xFF5B4FFF),
                      ),
                      onPressed: balance == 0
                          ? null
                          : () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Запрос выплаты пока демо.'),
                                ),
                              );
                            },
                      child: const Text('Вывести деньги'),
                    ),
                  ),
                ],
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'История начислений',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
            ),
            Expanded(
              child: snapshot.connectionState == ConnectionState.waiting
                  ? const Center(child: CircularProgressIndicator())
                  : orders.isEmpty
                      ? const Center(child: Text('Начислений пока нет'))
                      : RefreshIndicator(
                          onRefresh: () async {
                            setState(() {
                              _ordersFuture = _loadCompletedOrders();
                            });
                          },
                          child: ListView.builder(
                            itemCount: orders.length,
                            itemBuilder: (context, index) {
                              final order = orders[index];
                              final amount = _incomeForOrder(order);

                              return Card(
                                margin: const EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 4,
                                ),
                                child: ListTile(
                                  leading: CircleAvatar(
                                    backgroundColor:
                                        Colors.green.withValues(alpha: 0.1),
                                    child: const Icon(
                                      Icons.arrow_downward,
                                      color: Colors.green,
                                      size: 18,
                                    ),
                                  ),
                                  title: Text(
                                    order['title'] ?? 'Завершенный заказ',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  subtitle: Text('${order['hours']} ч × 600 ₽'),
                                  trailing: Text(
                                    '+${_formatMoney(amount)} ₽',
                                    style: const TextStyle(
                                      color: Colors.green,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
            ),
          ],
        );
      },
    );
  }
}

String _formatMoney(int value) {
  final chars = value.toString().split('').reversed.toList();
  final groups = <String>[];
  for (var i = 0; i < chars.length; i += 3) {
    groups.add(chars.skip(i).take(3).toList().reversed.join());
  }
  return groups.reversed.join(' ');
}

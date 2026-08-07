import 'package:flutter/material.dart';

import '../../main.dart' show supabase;

enum _SortMode { dateDesc, dateAsc, byStatus, byWorkers }

class ClientOrdersScreen extends StatefulWidget {
  const ClientOrdersScreen({super.key});

  @override
  State<ClientOrdersScreen> createState() => _ClientOrdersScreenState();
}

class _ClientOrdersScreenState extends State<ClientOrdersScreen> {
  _SortMode _sortMode = _SortMode.dateDesc;

  Color _statusColor(String status) {
    if (status.contains('модерации')) return Colors.orange;
    if (status.contains('работе')) return Colors.blue;
    if (status.contains('Завершен')) return Colors.green;
    if (status.contains('Отменен')) return Colors.red;
    return Colors.grey;
  }

  void _showSortSheet() {
    showModalBottomSheet(
      context: context,
      builder: (_) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _SortTile(
            title: 'По дате (сначала новые)',
            selected: _sortMode == _SortMode.dateDesc,
            onTap: () {
              setState(() => _sortMode = _SortMode.dateDesc);
              Navigator.pop(context);
            },
          ),
          _SortTile(
            title: 'По дате (сначала старые)',
            selected: _sortMode == _SortMode.dateAsc,
            onTap: () {
              setState(() => _sortMode = _SortMode.dateAsc);
              Navigator.pop(context);
            },
          ),
          _SortTile(
            title: 'По статусу',
            selected: _sortMode == _SortMode.byStatus,
            onTap: () {
              setState(() => _sortMode = _SortMode.byStatus);
              Navigator.pop(context);
            },
          ),
          _SortTile(
            title: 'По количеству грузчиков',
            selected: _sortMode == _SortMode.byWorkers,
            onTap: () {
              setState(() => _sortMode = _SortMode.byWorkers);
              Navigator.pop(context);
            },
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _sorted(List<Map<String, dynamic>> orders) {
    final list = [...orders];
    switch (_sortMode) {
      case _SortMode.dateDesc:
        list.sort((a, b) => (b['created_at']?.toString() ?? '')
            .compareTo(a['created_at']?.toString() ?? ''));
      case _SortMode.dateAsc:
        list.sort((a, b) => (a['created_at']?.toString() ?? '')
            .compareTo(b['created_at']?.toString() ?? ''));
      case _SortMode.byStatus:
        list.sort((a, b) => (a['status']?.toString() ?? '')
            .compareTo(b['status']?.toString() ?? ''));
      case _SortMode.byWorkers:
        list.sort(
          (a, b) => _readInt(
            b['workers_count'],
          ).compareTo(_readInt(a['workers_count'])),
        );
    }
    return list;
  }

  int _readInt(Object? value) {
    if (value is int) return value;
    return int.tryParse(value?.toString() ?? '') ?? 0;
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: supabase
          .from('orders')
          .select()
          .order('created_at', ascending: false)
          .execute(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(
            child: Text('Ошибка загрузки: ${snapshot.error}'),
          );
        }

        final orders = _sorted(
          (snapshot.data ?? [])
              .where(
                (order) => order['source']?.toString().toLowerCase() != 'crm',
              )
              .toList(),
        );

        if (orders.isEmpty) {
          return const Center(
            child: Text(
              'У вас пока нет заказов.',
              textAlign: TextAlign.center,
            ),
          );
        }

        return Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: IconButton(
                icon: const Icon(Icons.sort),
                tooltip: 'Сортировка',
                onPressed: _showSortSheet,
              ),
            ),
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.all(8),
                itemCount: orders.length,
                itemBuilder: (context, index) {
                  final order = orders[index];
                  final status = order['status'] as String? ?? 'Неизвестно';
                  final color = _statusColor(status);

                  return Card(
                    elevation: 2,
                    margin: const EdgeInsets.symmetric(vertical: 6),
                    child: ListTile(
                      title: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              order['title'] ?? 'Заказ',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: color.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              status,
                              style: TextStyle(fontSize: 11, color: color),
                            ),
                          ),
                        ],
                      ),
                      subtitle: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SizedBox(height: 4),
                          Text(
                            '${order['workers_count']} грузчиков, ${order['hours']} ч',
                          ),
                          const SizedBox(height: 2),
                          Text(
                            order['address'] ?? '',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) =>
                                ClientOrderDetailsScreen(orderId: order['id']),
                          ),
                        );
                      },
                    ),
                  );
                },
              ),
            ),
          ],
        );
      },
    );
  }
}

class _SortTile extends StatelessWidget {
  final String title;
  final bool selected;
  final VoidCallback onTap;

  const _SortTile({
    required this.title,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(title),
      trailing: selected ? const Icon(Icons.check) : null,
      onTap: onTap,
    );
  }
}

class ClientOrderDetailsScreen extends StatelessWidget {
  final String orderId;

  const ClientOrderDetailsScreen({super.key, required this.orderId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Детали заказа'),
      ),
      body: FutureBuilder<Map<String, dynamic>?>(
        future: supabase.from('orders').select().eq('id', orderId).single(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError || !snapshot.hasData) {
            return const Center(child: Text('Ошибка загрузки заказа'));
          }

          final order = snapshot.data!;

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  order['title'] ?? 'Заказ',
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(order['address'] ?? ''),
                const SizedBox(height: 4),
                Text(
                  '${order['workers_count']} грузчиков, ${order['hours']} ч',
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    const Text('Статус: '),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.blue.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        order['status'] ?? '',
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.blue,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                const Text(
                  'Описание:',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(order['description'] ?? 'Нет описания'),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text(
                            'Функция изменения/отмены заказа пока демо.',
                          ),
                        ),
                      );
                    },
                    child: const Text('Изменить / отменить заказ'),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

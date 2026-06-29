import 'package:flutter/material.dart';
import '../../main.dart';

class LogistOrdersScreen extends StatefulWidget {
  const LogistOrdersScreen({super.key});

  @override
  State<LogistOrdersScreen> createState() => _LogistOrdersScreenState();
}

class _LogistOrdersScreenState extends State<LogistOrdersScreen> {
  String _selectedFilter = 'Все';

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                FilterChip(
                  label: 'Все',
                  isSelected: _selectedFilter == 'Все',
                  onTap: () => setState(() => _selectedFilter = 'Все'),
                ),
                const SizedBox(width: 8),
                FilterChip(
                  label: 'На модерации',
                  isSelected: _selectedFilter == 'На модерации',
                  onTap: () => setState(() => _selectedFilter = 'На модерации'),
                ),
                const SizedBox(width: 8),
                FilterChip(
                  label: 'Одобрен',
                  isSelected: _selectedFilter == 'Одобрен',
                  onTap: () => setState(() => _selectedFilter = 'Одобрен'),
                ),
                const SizedBox(width: 8),
                FilterChip(
                  label: 'В работе',
                  isSelected: _selectedFilter == 'В работе',
                  onTap: () => setState(() => _selectedFilter = 'В работе'),
                ),
                const SizedBox(width: 8),
                FilterChip(
                  label: 'Завершен',
                  isSelected: _selectedFilter == 'Завершен',
                  onTap: () => setState(() => _selectedFilter = 'Завершен'),
                ),
              ],
            ),
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: _selectedFilter == 'Все'
                ? supabase
                    .from('orders')
                    .select()
                    .order('created_at', ascending: false)
                    .execute()
                : supabase
                    .from('orders')
                    .select()
                    .eq('status', _selectedFilter)
                    .order('created_at', ascending: false)
                    .execute(),
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }

              if (snapshot.hasError) {
                return Center(
                  child: Text('Ошибка: ${snapshot.error}'),
                );
              }

              final orders = snapshot.data ?? [];

              if (orders.isEmpty) {
                return Center(
                  child: Text(
                    _selectedFilter == 'Все'
                        ? 'Заказов пока нет'
                        : 'Нет заказов со статусом "$_selectedFilter"',
                    textAlign: TextAlign.center,
                  ),
                );
              }

              return ListView.builder(
                padding: const EdgeInsets.all(8),
                itemCount: orders.length,
                itemBuilder: (context, index) {
                  final order = orders[index];
                  return LogistOrderCard(
                    order: order,
                    onUpdate: () => setState(() {}),
                  );
                },
              );
            },
          ),
        ),
      ],
    );
  }
}

class FilterChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const FilterChip({
    super.key,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF5B4FFF) : Colors.grey[200],
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : Colors.black87,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}

class LogistOrderCard extends StatelessWidget {
  final Map<String, dynamic> order;
  final VoidCallback onUpdate;

  const LogistOrderCard({
    super.key,
    required this.order,
    required this.onUpdate,
  });

  Color _statusColor(String status) {
    if (status.contains('модерации')) return Colors.orange;
    if (status.contains('Одобрен')) return Colors.blue;
    if (status.contains('работе')) return Colors.green;
    if (status.contains('Завершен')) return Colors.grey;
    return Colors.grey;
  }

  @override
  Widget build(BuildContext context) {
    final status = order['status'] as String? ?? 'Неизвестно';
    final color = _statusColor(status);

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
      child: Column(
        children: [
          ListTile(
            title: Row(
              children: [
                Expanded(
                  child: Text(
                    order['title'] ?? 'Заказ',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
                Text(order['address'] ?? ''),
                const SizedBox(height: 2),
                Text(
                    '${order['workers_count']} грузчиков × ${order['hours']} ч'),
              ],
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => LogistOrderDetailsScreen(
                      order: order, onUpdate: onUpdate),
                ),
              );
            },
          ),
          if (status == 'На модерации')
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () async {
                        await supabase
                            .from('orders')
                            .eq('id', order['id'])
                            .update({'status': 'Отклонён'});
                        onUpdate();
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.red,
                      ),
                      child: const Text('Отклонить'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () async {
                        await supabase
                            .from('orders')
                            .eq('id', order['id'])
                            .update({'status': 'Одобрен'});
                        onUpdate();
                      },
                      child: const Text('Одобрить'),
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

class LogistOrderDetailsScreen extends StatelessWidget {
  final Map<String, dynamic> order;
  final VoidCallback onUpdate;

  const LogistOrderDetailsScreen({
    super.key,
    required this.order,
    required this.onUpdate,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Детали заказа')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              order['title'] ?? 'Заказ',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Text('📍 ${order['address'] ?? ''}'),
            const SizedBox(height: 8),
            Text('👷 ${order['workers_count']} грузчиков'),
            const SizedBox(height: 8),
            Text('⏱️ ${order['hours']} часов'),
            const SizedBox(height: 8),
            Text('📋 Статус: ${order['status']}'),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 16),
            const Text(
              'Описание:',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(order['description'] ?? 'Нет описания'),
          ],
        ),
      ),
    );
  }
}

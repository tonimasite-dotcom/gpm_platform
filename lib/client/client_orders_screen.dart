import 'package:flutter/material.dart';
import '../main.dart' show supabase;

class ClientOrdersScreen extends StatelessWidget {
  const ClientOrdersScreen({super.key});

  Color _statusColor(String status) {
    if (status.contains('модерации')) return Colors.orange;
    if (status.contains('работе')) return Colors.blue;
    if (status.contains('Завершен')) return Colors.green;
    if (status.contains('Отменён')) return Colors.red;
    return Colors.grey;
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

        final orders = snapshot.data ?? [];

        if (orders.isEmpty) {
          return const Center(
            child: Text(
              'У вас пока нет заказов.\nСоздайте первый заказ во вкладке "Создать"',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16),
            ),
          );
        }

        return ListView.builder(
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
                          horizontal: 8, vertical: 4),
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
                        '👷 ${order['workers_count']} грузчиков × ${order['hours']} ч'),
                    const SizedBox(height: 2),
                    Text(
                      '📍 ${order['address'] ?? ''}',
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
        );
      },
    );
  }
}

// === ДЕТАЛЬНЫЙ ЭКРАН ЗАКАЗА ===
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
                      fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    const Text('📋 Статус: '),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.blue.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        order['status'] ?? '',
                        style:
                            const TextStyle(fontSize: 12, color: Colors.blue),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text('📍 ${order['address'] ?? ''}'),
                const SizedBox(height: 8),
                Text(
                    '👷 ${order['workers_count']} грузчиков × ${order['hours']} ч'),
                const SizedBox(height: 24),
                const Divider(),
                const SizedBox(height: 16),
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
                              'Функция изменения/отмены заказа будет добавлена позже'),
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

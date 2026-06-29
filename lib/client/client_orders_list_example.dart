import 'package:flutter/material.dart';
import '../main.dart';

class ClientOrdersListExample extends StatefulWidget {
  const ClientOrdersListExample({super.key});

  @override
  State<ClientOrdersListExample> createState() =>
      _ClientOrdersListExampleState();
}

class _ClientOrdersListExampleState extends State<ClientOrdersListExample> {
  late Future<List<Map<String, dynamic>>> _ordersFuture;

  @override
  void initState() {
    super.initState();
    _ordersFuture = bitrix24.getOrders();
  }

  Future<void> _updateStatus(String orderId, String newStatus) async {
    final success = await bitrix24.updateOrderStatus(orderId, newStatus);
    if (success && mounted) {
      setState(() {
        _ordersFuture = bitrix24.getOrders();
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Статус обновлён')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _ordersFuture,
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
          return const Center(
            child: Text('Нет заказов'),
          );
        }

        return ListView.builder(
          itemCount: orders.length,
          itemBuilder: (context, index) {
            final order = orders[index];
            return Card(
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: ListTile(
                title: Text(order['title'] ?? 'Заказ'),
                subtitle: Text(
                  'ID: ${order['id']}\nТелефон: ${order['phone'] ?? 'N/A'}',
                ),
                trailing: PopupMenuButton(
                  onSelected: (value) {
                    _updateStatus(order['id'].toString(), value);
                  },
                  itemBuilder: (BuildContext context) => [
                    const PopupMenuItem(
                      value: 'NEW',
                      child: Text('Новый'),
                    ),
                    const PopupMenuItem(
                      value: 'IN_PROGRESS',
                      child: Text('В процессе'),
                    ),
                    const PopupMenuItem(
                      value: 'WON',
                      child: Text('Завершён'),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}

import 'package:flutter/material.dart';
import '../../main.dart';

class WorkerOrdersScreen extends StatefulWidget {
  const WorkerOrdersScreen({super.key});

  @override
  State<WorkerOrdersScreen> createState() => _WorkerOrdersScreenState();
}

class _WorkerOrdersScreenState extends State<WorkerOrdersScreen> {
  bool isLoadingAvailable = true;
  bool isLoadingActive = true;
  bool isLoadingHistory = true;

  List<Map<String, dynamic>> availableOrders = [];
  List<Map<String, dynamic>> activeOrders = [];
  List<Map<String, dynamic>> historyOrders = [];

  @override
  void initState() {
    super.initState();
    loadOrders();
  }

  Future<void> loadOrders() async {
    await Future.wait([
      loadAvailableOrders(),
      loadActiveOrders(),
      loadHistoryOrders(),
    ]);
  }

  Future<void> loadAvailableOrders() async {
    setState(() => isLoadingAvailable = true);
    try {
      final data = await supabase
          .from('orders')
          .select()
          .or('status.eq.На модерации,status.eq.Одобрен')
          .order('created_at', ascending: false)
          .execute();

      setState(() {
        availableOrders = List<Map<String, dynamic>>.from(data);
        isLoadingAvailable = false;
      });
    } catch (e) {
      setState(() => isLoadingAvailable = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка загрузки: $e')),
        );
      }
    }
  }

  Future<void> loadActiveOrders() async {
    setState(() => isLoadingActive = true);
    try {
      final data = await supabase
          .from('orders')
          .select()
          .eq('status', 'В работе')
          .order('created_at', ascending: false)
          .execute();

      setState(() {
        activeOrders = List<Map<String, dynamic>>.from(data);
        isLoadingActive = false;
      });
    } catch (e) {
      setState(() => isLoadingActive = false);
    }
  }

  Future<void> loadHistoryOrders() async {
    setState(() => isLoadingHistory = true);
    try {
      final data = await supabase
          .from('orders')
          .select()
          .eq('status', 'Завершен')
          .order('created_at', ascending: false)
          .limit(10)
          .execute();

      setState(() {
        historyOrders = List<Map<String, dynamic>>.from(data);
        isLoadingHistory = false;
      });
    } catch (e) {
      setState(() => isLoadingHistory = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Column(
        children: [
          const TabBar(
            labelColor: Colors.black,
            tabs: [
              Tab(text: 'Доступные'),
              Tab(text: 'В работе'),
              Tab(text: 'История'),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: [
                // Доступные заказы
                RefreshIndicator(
                  onRefresh: loadAvailableOrders,
                  child: isLoadingAvailable
                      ? const Center(child: CircularProgressIndicator())
                      : OrdersList(
                          orders: availableOrders,
                          emptyText: 'Нет доступных заказов',
                        ),
                ),
                // В работе
                RefreshIndicator(
                  onRefresh: loadActiveOrders,
                  child: isLoadingActive
                      ? const Center(child: CircularProgressIndicator())
                      : OrdersList(
                          orders: activeOrders,
                          emptyText: 'Нет активных заказов',
                        ),
                ),
                // История
                RefreshIndicator(
                  onRefresh: loadHistoryOrders,
                  child: isLoadingHistory
                      ? const Center(child: CircularProgressIndicator())
                      : OrdersList(
                          orders: historyOrders,
                          emptyText: 'История пуста',
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

class OrdersList extends StatelessWidget {
  final List<Map<String, dynamic>> orders;
  final String emptyText;

  const OrdersList({
    super.key,
    required this.orders,
    required this.emptyText,
  });

  @override
  Widget build(BuildContext context) {
    if (orders.isEmpty) {
      return Center(child: Text(emptyText));
    }

    return ListView.builder(
      padding: const EdgeInsets.all(8),
      itemCount: orders.length,
      itemBuilder: (context, index) {
        final order = orders[index];
        return Card(
          elevation: 2,
          margin: const EdgeInsets.symmetric(vertical: 6),
          child: ListTile(
            title: Text(order['title'] ?? order['description'] ?? 'Заказ'),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                Text('📍 ${order['address'] ?? ''}'),
                const SizedBox(height: 4),
                Text(
                  '👷 ${order['workers_count']} чел. × ${order['hours']} ч',
                ),
                const SizedBox(height: 4),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.orange.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    order['status'] ?? '',
                    style: const TextStyle(fontSize: 11, color: Colors.orange),
                  ),
                ),
              ],
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => WorkerOrderDetailsScreen(order: order),
                ),
              );
            },
          ),
        );
      },
    );
  }
}

class WorkerOrderDetailsScreen extends StatefulWidget {
  final Map<String, dynamic> order;

  const WorkerOrderDetailsScreen({super.key, required this.order});

  @override
  State<WorkerOrderDetailsScreen> createState() =>
      _WorkerOrderDetailsScreenState();
}

class _WorkerOrderDetailsScreenState extends State<WorkerOrderDetailsScreen> {
  bool isApplying = false;

  Future<void> applyToOrder() async {
    setState(() => isApplying = true);

    try {
      // 1. Изменяем статус заказа на "В работе"
      await supabase
          .from('orders')
          .eq('id', widget.order['id'])
          .update({'status': 'В работе'});

      if (!mounted) return;

      // 2. Показываем успешное сообщение
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('✅ Вы успешно записались на заказ!'),
          backgroundColor: Colors.green,
        ),
      );

      // 3. Возвращаемся назад
      Navigator.pop(context);
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Ошибка: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => isApplying = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final orderId = widget.order['id']?.toString() ?? '';
    final shortOrderId = orderId.length > 8 ? orderId.substring(0, 8) : orderId;

    return Scaffold(
      appBar: AppBar(
        title: Text('Заказ #$shortOrderId'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.order['title'] ?? widget.order['description'] ?? 'Заказ',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Text('📍 ${widget.order['address'] ?? ''}'),
            const SizedBox(height: 8),
            Text('👷 ${widget.order['workers_count']} грузчиков'),
            const SizedBox(height: 8),
            Text('⏱️ ${widget.order['hours']} часов'),
            const SizedBox(height: 8),
            Row(
              children: [
                const Text('📋 Статус: '),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.orange.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    widget.order['status'] ?? '',
                    style: const TextStyle(fontSize: 12, color: Colors.orange),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 16),
            const Text(
              'Описание:',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(widget.order['description'] ?? 'Нет описания'),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: isApplying ? null : applyToOrder,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF5B4FFF),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: isApplying
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text(
                        'Откликнуться на заказ',
                        style: TextStyle(fontSize: 16),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

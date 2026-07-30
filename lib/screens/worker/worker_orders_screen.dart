import 'package:flutter/material.dart';

import '../../main.dart' show bitrix24;
import '../../services/bitrix24_service.dart';

class WorkerOrdersScreen extends StatefulWidget {
  const WorkerOrdersScreen({super.key});

  @override
  State<WorkerOrdersScreen> createState() => _WorkerOrdersScreenState();
}

class _WorkerOrdersScreenState extends State<WorkerOrdersScreen> {
  bool isLoading = true;
  List<Map<String, dynamic>> availableOrders = [];
  List<Map<String, dynamic>> activeOrders = [];
  List<Map<String, dynamic>> historyOrders = [];

  @override
  void initState() {
    super.initState();
    loadOrders();
  }

  Future<void> loadOrders() async {
    setState(() => isLoading = true);

    try {
      final orders = await bitrix24.getOrdersForWorker(
        Bitrix24Service.demoWorkerId,
      );

      if (!mounted) return;
      setState(() {
        availableOrders = orders.where(_isAvailableForWorker).toList();
        activeOrders = orders.where(_isActiveForWorker).toList();
        historyOrders = orders.where(_isHistoryForWorker).toList();
        isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка загрузки: $e')),
      );
    }
  }

  bool _isAvailableForWorker(Map<String, dynamic> order) {
    final status = order['status'];
    final applicationStatus = order['worker_application_status'];
    return status == 'PROCESSED' &&
        applicationStatus == null &&
        _matchesNationalityRequirement(order);
  }

  bool _matchesNationalityRequirement(Map<String, dynamic> order) {
    final national = order['national'] ?? order['nationality'];
    final requiresRussianCitizenship =
        national == true || national == 'yes' || national == 'ru';
    if (!requiresRussianCitizenship) return true;

    final worker = bitrix24.getWorkerProfileSync(Bitrix24Service.demoWorkerId);
    return worker?['nationality'] == true;
  }

  bool _isActiveForWorker(Map<String, dynamic> order) {
    final status = order['status'];
    final applicationStatus = order['worker_application_status'];
    final isAssigned = order['is_assigned_to_worker'] == true;
    return applicationStatus == 'PENDING' ||
        (isAssigned &&
            (status == 'PROCESSED' ||
                status == 'IN_PROCESS' ||
                status == 'DONE_PENDING'));
  }

  bool _isHistoryForWorker(Map<String, dynamic> order) {
    final status = order['status'];
    return order['is_assigned_to_worker'] == true && status == 'CONVERTED';
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return DefaultTabController(
      length: 3,
      child: Column(
        children: [
          const TabBar(
            labelColor: Colors.black,
            tabs: [
              Tab(text: 'Доступные'),
              Tab(text: 'Мои'),
              Tab(text: 'История'),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: [
                RefreshIndicator(
                  onRefresh: loadOrders,
                  child: OrdersList(
                    orders: availableOrders,
                    emptyText: 'Нет доступных заказов',
                    onChanged: loadOrders,
                  ),
                ),
                RefreshIndicator(
                  onRefresh: loadOrders,
                  child: OrdersList(
                    orders: activeOrders,
                    emptyText: 'Нет активных откликов и заказов',
                    onChanged: loadOrders,
                  ),
                ),
                RefreshIndicator(
                  onRefresh: loadOrders,
                  child: OrdersList(
                    orders: historyOrders,
                    emptyText: 'История пуста',
                    onChanged: loadOrders,
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
  final VoidCallback onChanged;

  const OrdersList({
    super.key,
    required this.orders,
    required this.emptyText,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    if (orders.isEmpty) {
      return ListView(
        children: [
          SizedBox(
            height: MediaQuery.sizeOf(context).height * 0.45,
            child: Center(child: Text(emptyText)),
          ),
        ],
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(8),
      itemCount: orders.length,
      itemBuilder: (context, index) {
        final order = orders[index];
        final statusText = _workerStatusText(order);
        final color = _workerStatusColor(order);

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
                Text('🗓 ${_formatSchedule(order['scheduled_at'])}'),
                const SizedBox(height: 4),
                Text(
                  '👷 ${order['assigned_count'] ?? 0}/${order['workers_count']} чел. × ${order['hours']} ч',
                ),
                const SizedBox(height: 4),
                _StatusPill(text: statusText, color: color),
              ],
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () async {
              await Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => WorkerOrderDetailsScreen(order: order),
                ),
              );
              onChanged();
            },
          ),
        );
      },
    );
  }

  String _workerStatusText(Map<String, dynamic> order) {
    final orderStatus = order['status']?.toString();
    if (orderStatus == 'DONE_PENDING' || orderStatus == 'CONVERTED') {
      return _orderStatusText(orderStatus);
    }

    final applicationStatus = order['worker_application_status'];
    if (applicationStatus == 'PENDING') return 'Отклик на рассмотрении';
    if (applicationStatus == 'APPROVED') return 'Вы назначены';
    if (applicationStatus == 'REJECTED') return 'Отклик отклонен';
    return _orderStatusText(order['status']?.toString());
  }

  Color _workerStatusColor(Map<String, dynamic> order) {
    final orderStatus = order['status']?.toString();
    if (orderStatus == 'DONE_PENDING' || orderStatus == 'CONVERTED') {
      return _orderStatusColor(orderStatus);
    }

    final applicationStatus = order['worker_application_status'];
    if (applicationStatus == 'PENDING') return Colors.orange;
    if (applicationStatus == 'APPROVED') return Colors.green;
    if (applicationStatus == 'REJECTED') return Colors.red;
    return _orderStatusColor(order['status']?.toString());
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
  late Map<String, dynamic> order;
  bool isApplying = false;
  bool isCompleting = false;

  @override
  void initState() {
    super.initState();
    order = Map<String, dynamic>.from(widget.order);
  }

  Future<void> applyToOrder() async {
    setState(() => isApplying = true);

    try {
      final result = await bitrix24.applyToOrder(
        orderId: order['id'].toString(),
        workerId: Bitrix24Service.demoWorkerId,
        workerName: Bitrix24Service.demoWorkerName,
      );

      if (!mounted) return;

      if (result['success'] == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Отклик отправлен логисту'),
            backgroundColor: Colors.green,
          ),
        );
        Navigator.pop(context);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result['error']?.toString() ?? 'Ошибка отклика'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка: $e'), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => isApplying = false);
    }
  }

  Future<void> completeOrder() async {
    setState(() => isCompleting = true);

    try {
      final success = await bitrix24.updateOrderStatus(
        order['id'].toString(),
        'DONE_PENDING',
      );

      if (!mounted) return;

      if (success) {
        setState(() => order['status'] = 'DONE_PENDING');
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Заказ отправлен логисту на подтверждение'),
            backgroundColor: Colors.green,
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Не удалось завершить заказ'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка: $e'), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => isCompleting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final orderId = order['id']?.toString() ?? '';
    final shortOrderId = orderId.length > 8 ? orderId.substring(0, 8) : orderId;
    final applicationStatus = order['worker_application_status'];
    final canApply = applicationStatus == null && order['status'] == 'PROCESSED';
    final isAssigned = order['is_assigned_to_worker'] == true;
    final canComplete =
        isAssigned &&
            (order['status'] == 'PROCESSED' || order['status'] == 'IN_PROCESS');

    return Scaffold(
      appBar: AppBar(title: Text('Заказ #$shortOrderId')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              order['title'] ?? order['description'] ?? 'Заказ',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            _OrderFact(label: 'Город', value: order['city']),
            _OrderFact(label: 'Номер заказа', value: order['external_order_id'] ?? order['id']),
            _OrderFact(label: 'Дата и время выполнения работ', value: _formatSchedule(order['scheduled_at'])),
            _OrderFact(label: 'Кол-во людей', value: order['workers_count']),
            _OrderFact(label: 'Гражданство РФ', value: _nationalText(order)),
            _OrderFact(label: 'Режим работы', value: _workModeText(order)),
            _OrderFact(label: 'Метро', value: order['metro']),
            _OrderFact(label: 'Адрес', value: order['address']),
            if (order['work_mode'] == 'shift')
              _OrderFact(label: 'Описание смены', value: order['shift_description'])
            else ...[
              _OrderFact(label: 'Ставка (штатный постоянного графика)', value: order['price_regular']),
              _OrderFact(label: 'Ставка (штатный свободного графика)', value: order['price_state']),
              _OrderFact(label: 'Ставка (наемник)', value: order['price_per_hour']),
              _OrderFact(label: 'Минимальная оплата', value: _minPayText(order)),
            ],
            const SizedBox(height: 8),
            _StatusPill(
              text: _workerStatusText(order),
              color: _workerStatusColor(order),
            ),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 16),
            const Text(
              'Описание:',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(order['description'] ?? 'Нет описания'),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _primaryAction(canApply, canComplete),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF5B4FFF),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: isApplying || isCompleting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : Text(_primaryActionText(canApply, canComplete)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  VoidCallback? _primaryAction(bool canApply, bool canComplete) {
    if (canApply && !isApplying) return applyToOrder;
    if (canComplete && !isCompleting) return completeOrder;
    return null;
  }

  String _primaryActionText(bool canApply, bool canComplete) {
    if (canApply) return 'Откликнуться на заказ';
    if (canComplete) return 'Завершить заказ';
    if (order['status'] == 'DONE_PENDING') {
      return 'Ждет подтверждения логиста';
    }
    if (order['status'] == 'CONVERTED') return 'Заказ завершен';
    return 'Отклик уже создан';
  }
}

class _StatusPill extends StatelessWidget {
  final String text;
  final Color color;

  const _StatusPill({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(text, style: TextStyle(fontSize: 11, color: color)),
    );
  }
}

class _OrderFact extends StatelessWidget {
  final String label;
  final dynamic value;

  const _OrderFact({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final text = value?.toString().trim() ?? '';
    if (text.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text('$label: $text'),
    );
  }
}

String _nationalText(Map<String, dynamic> order) {
  final value = order['national'] ?? order['nationality'];
  if (value == true || value == 'yes' || value == 'ru') return 'Да';
  return 'Необязательно';
}

String _minPayText(Map<String, dynamic> order) {
  final value = order['min_time'] ?? order['hours'];
  if (value == null) return '';
  return '$value часа';
}

String _workModeText(Map<String, dynamic> order) {
  switch (order['work_mode']?.toString()) {
    case 'rate':
      return 'Ставка';
    case 'shift':
      return 'Смена';
    default:
      return '';
  }
}

String _workerStatusText(Map<String, dynamic> order) {
  final orderStatus = order['status']?.toString();
  if (orderStatus == 'DONE_PENDING' || orderStatus == 'CONVERTED') {
    return _orderStatusText(orderStatus);
  }

  final applicationStatus = order['worker_application_status'];
  if (applicationStatus == 'PENDING') return 'Отклик на рассмотрении';
  if (applicationStatus == 'APPROVED') return 'Вы назначены';
  if (applicationStatus == 'REJECTED') return 'Отклик отклонен';
  return _orderStatusText(order['status']?.toString());
}

Color _workerStatusColor(Map<String, dynamic> order) {
  final orderStatus = order['status']?.toString();
  if (orderStatus == 'DONE_PENDING' || orderStatus == 'CONVERTED') {
    return _orderStatusColor(orderStatus);
  }

  final applicationStatus = order['worker_application_status'];
  if (applicationStatus == 'PENDING') return Colors.orange;
  if (applicationStatus == 'APPROVED') return Colors.green;
  if (applicationStatus == 'REJECTED') return Colors.red;
  return _orderStatusColor(order['status']?.toString());
}

String _orderStatusText(String? status) {
  switch (status) {
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

String _formatSchedule(dynamic value) {
  final raw = value?.toString();
  if (raw == null || raw.isEmpty) return 'Дата не указана';

  final dateTime = DateTime.tryParse(raw)?.toLocal();
  if (dateTime == null) return raw;

  final day = dateTime.day.toString().padLeft(2, '0');
  final month = dateTime.month.toString().padLeft(2, '0');
  final hour = dateTime.hour.toString().padLeft(2, '0');
  final minute = dateTime.minute.toString().padLeft(2, '0');
  return '$day.$month $hour:$minute';
}

Color _orderStatusColor(String? status) {
  switch (status) {
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

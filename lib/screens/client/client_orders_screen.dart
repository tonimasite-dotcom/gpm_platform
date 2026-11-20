import 'package:flutter/material.dart';
import '../../widgets/worker_rating.dart';
import '../../widgets/adaptive_buttons.dart';

import '../../main.dart' show gpmApi;
import '../../utils/order_display.dart';
import '../../utils/client_order_sort.dart';
import '../orders/client_order_sort_sheet.dart';
import '../attendance/order_attendance.dart';
import '../orders/order_draft_edit_screen.dart';

class ClientOrdersScreen extends StatefulWidget {
  const ClientOrdersScreen({super.key});

  @override
  State<ClientOrdersScreen> createState() => _ClientOrdersScreenState();
}

class _ClientOrdersScreenState extends State<ClientOrdersScreen> {
  List<ClientOrderSort> _sortPriorities = [ClientOrderSort.dateDesc];
  late Future<List<Map<String, dynamic>>> _ordersFuture;

  @override
  void initState() {
    super.initState();
    _ordersFuture = gpmApi.getOrders();
  }

  Future<void> _showSortSheet() async {
    final result = await showClientOrderSortSheet(context, _sortPriorities);
    if (!mounted || result == null) return;
    setState(() => _sortPriorities = result);
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
          return Center(child: Text('Ошибка загрузки: ${snapshot.error}'));
        }

        final orders = sortClientOrders(
          (snapshot.data ?? []).where((order) {
            final source = order['source']?.toString().toLowerCase();
            return source != 'external' && source != 'crm';
          }).toList(),
          _sortPriorities,
        );

        if (orders.isEmpty) {
          return const Center(
            child: Text('У вас пока нет заказов.', textAlign: TextAlign.center),
          );
        }

        return Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(8, 4, 8, 4),
                child: OutlinedButton(
                  onPressed: _showSortSheet,
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.sort, size: 20),
                      SizedBox(width: 8),
                      Flexible(child: Text('Сортировка')),
                      SizedBox(width: 4),
                      Icon(Icons.expand_more, size: 20),
                    ],
                  ),
                ),
              ),
            ),
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.all(8),
                itemCount: orders.length,
                itemBuilder: (context, index) {
                  final order = orders[index];
                  final status = orderStatusText(order['status']);
                  final color = orderStatusColor(order['status']);

                  return Card(
                    shape: orderCardShape,
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
                              borderRadius: BorderRadius.circular(3),
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
                          Text(formatOrderSchedule(order['scheduled_at'])),
                          const SizedBox(height: 2),
                          Text(
                            order['address'] ?? '',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            workerRateText(order),
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          const SizedBox(height: 5),
                          OrderPublishedAtMarker(
                            createdAt: order['created_at'],
                          ),
                        ],
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () async {
                        await Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) =>
                                ClientOrderDetailsScreen(orderId: order['id']),
                          ),
                        );
                        if (mounted) {
                          setState(() => _ordersFuture = gpmApi.getOrders());
                        }
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

class ClientOrderDetailsScreen extends StatefulWidget {
  final String orderId;

  const ClientOrderDetailsScreen({super.key, required this.orderId});

  @override
  State<ClientOrderDetailsScreen> createState() =>
      _ClientOrderDetailsScreenState();
}

class _ClientOrderDetailsScreenState extends State<ClientOrderDetailsScreen> {
  late Future<Map<String, dynamic>?> _orderFuture;
  String? _pendingAction;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _orderFuture = gpmApi.getOrderById(widget.orderId);
  }

  Future<void> _decideApplication(String applicationId, bool approve) async {
    setState(() => _pendingAction = applicationId);
    final result = approve
        ? await gpmApi.approveApplication(
            orderId: widget.orderId,
            applicationId: applicationId,
          )
        : await gpmApi.rejectApplication(
            applicationId,
            orderId: widget.orderId,
          );
    if (!mounted) return;
    if (result['success'] == true) {
      setState(() {
        _pendingAction = null;
        _reload();
      });
      return;
    }
    setState(() => _pendingAction = null);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          result['error']?.toString() ?? 'Не удалось изменить отклик',
        ),
      ),
    );
  }

  Future<void> _acceptWork() async {
    setState(() => _pendingAction = 'accept-work');
    final success = await gpmApi.updateOrderStatus(widget.orderId, 'CONVERTED');
    if (!mounted) return;
    if (success) {
      setState(() {
        _pendingAction = null;
        _reload();
      });
      return;
    }
    setState(() => _pendingAction = null);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Не удалось принять выполненную работу')),
    );
  }

  Future<void> _editDraft(Map<String, dynamic> order) async {
    final updated = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => OrderDraftEditScreen(order: order)),
    );
    if (updated == true && mounted) {
      setState(_reload);
    }
  }

  Future<void> _publishDraft() async {
    setState(() => _pendingAction = 'publish-draft');
    final success = await gpmApi.updateOrderStatus(widget.orderId, 'PROCESSED');
    if (!mounted) return;
    setState(() {
      _pendingAction = null;
      if (success) _reload();
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          success
              ? 'Заказ опубликован и доступен исполнителям'
              : 'Не удалось опубликовать заказ',
        ),
        backgroundColor: success ? Colors.green : Colors.red,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Детали заказа')),
      body: FutureBuilder<Map<String, dynamic>?>(
        future: _orderFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError || !snapshot.hasData) {
            return const Center(child: Text('Ошибка загрузки заказа'));
          }

          final order = snapshot.data!;
          final allApplications = (order['applications'] as List? ?? const [])
              .whereType<Map>()
              .map((application) => Map<String, dynamic>.from(application))
              .toList();
          final applications = allApplications
              .where((application) => application['status'] == 'PENDING')
              .toList();
          final assignedIds =
              (order['assigned_worker_ids'] as List? ?? const [])
                  .map((id) => id.toString())
                  .toSet();
          final assignedApplications = allApplications
              .where(
                (application) =>
                    assignedIds.contains(application['worker_id']?.toString()),
              )
              .toList();
          for (final worker
              in (order['assigned_workers'] as List? ?? const [])
                  .whereType<Map>()) {
            if (!assignedApplications.any(
              (item) =>
                  item['worker_id']?.toString() == worker['id']?.toString(),
            )) {
              assignedApplications.add({
                'worker_id': worker['id'],
                'worker_name':
                    worker['display_name'] ??
                    worker['full_name'] ??
                    'Исполнитель',
                'worker': Map<String, dynamic>.from(worker),
              });
            }
          }
          final status = order['status']?.toString() ?? '';

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
                const SizedBox(height: 4),
                Text(
                  'Дата и время: '
                  '${formatOrderSchedule(order['scheduled_at'])}',
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
                        color: orderStatusColor(
                          order['status'],
                        ).withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(3),
                      ),
                      child: Text(
                        orderStatusText(order['status']),
                        style: TextStyle(
                          fontSize: 12,
                          color: orderStatusColor(order['status']),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                OrderAttendancePanel(
                  orderId: widget.orderId,
                  allowClientConfirmation: true,
                ),
                const SizedBox(height: 24),
                const Text(
                  'Описание:',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(order['description'] ?? 'Нет описания'),
                if (assignedApplications.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  const Text(
                    'Назначенные исполнители',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  for (final application in assignedApplications)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              application['worker_name']?.toString() ??
                                  'Исполнитель',
                            ),
                            const SizedBox(height: 4),
                            WorkerPublicRating(
                              worker: application['worker'] is Map
                                  ? Map<String, dynamic>.from(
                                      application['worker'] as Map,
                                    )
                                  : {},
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
                if (applications.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  const Text(
                    'Отклики исполнителей',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  ...applications.map((application) {
                    final applicationId = application['id']?.toString() ?? '';
                    final workerName =
                        application['worker_name']?.toString() ?? 'Исполнитель';
                    final loading = _pendingAction == applicationId;
                    return Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(workerName),
                            const SizedBox(height: 4),
                            WorkerPublicRating(
                              worker: application['worker'] is Map
                                  ? Map<String, dynamic>.from(
                                      application['worker'] as Map,
                                    )
                                  : {},
                            ),
                            const SizedBox(height: 8),
                            GpmActionButtons(
                              children: [
                                FilledButton(
                                  onPressed: loading || applicationId.isEmpty
                                      ? null
                                      : () => _decideApplication(
                                          applicationId,
                                          true,
                                        ),
                                  child: const Text('Принять'),
                                ),
                                OutlinedButton(
                                  onPressed: loading || applicationId.isEmpty
                                      ? null
                                      : () => _decideApplication(
                                          applicationId,
                                          false,
                                        ),
                                  child: const Text('Отклонить'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  }),
                ],
                if (status == 'DONE_PENDING') ...[
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _pendingAction == null ? _acceptWork : null,
                      child: const Text('Принять выполненную работу'),
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                if (status == 'NEW') ...[
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: _pendingAction == null
                          ? () => _editDraft(order)
                          : null,
                      child: const GpmButtonContent(
                        icon: Icon(Icons.edit_outlined),
                        label: Text('Редактировать'),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _pendingAction == null ? _publishDraft : null,
                      child: const GpmButtonContent(
                        icon: Icon(Icons.publish_outlined),
                        label: Text('Опубликовать'),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../../main.dart' show bitrix24;
import '../../theme/gpm_theme.dart';
import '../client/client_create_order_screen.dart';

class LogistOrdersScreen extends StatefulWidget {
  const LogistOrdersScreen({super.key});

  @override
  State<LogistOrdersScreen> createState() => _LogistOrdersScreenState();
}

class _LogistOrdersScreenState extends State<LogistOrdersScreen> {
  String _selectedFilter = 'Все';
  late Future<List<Map<String, dynamic>>> _ordersFuture;

  @override
  void initState() {
    super.initState();
    _ordersFuture = _loadOrders();
  }

  Future<List<Map<String, dynamic>>> _loadOrders() async {
    final orders = await bitrix24.getOrders();
    final result = <Map<String, dynamic>>[];

    for (final order in orders) {
      final applications = await bitrix24.getApplicationsForOrder(
        order['id'].toString(),
      );
      final copy = Map<String, dynamic>.from(order);
      final assignedIds = copy['assigned_worker_ids'];
      copy['applications_count'] = applications.length;
      copy['pending_applications_count'] = applications
          .where((application) => application['status'] == 'PENDING')
          .length;
      copy['assigned_count'] = assignedIds is List ? assignedIds.length : 0;
      result.add(copy);
    }

    result.sort(
      (a, b) => (b['created_at'] ?? '').toString().compareTo(
            (a['created_at'] ?? '').toString(),
          ),
    );
    return result;
  }

  void _refresh() {
    setState(() {
      _ordersFuture = _loadOrders();
    });
  }

  Future<void> _openCreateOrder() async {
    final created = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => const ClientCreateOrderScreen(
          publishImmediately: true,
          closeOnSuccess: true,
          title: 'Новая заявка',
          submitText: 'Опубликовать заявку',
        ),
      ),
    );

    if (created == true) {
      _refresh();
    }
  }

  Future<void> _createDemoCrmOrder() async {
    final result = await bitrix24.createDemoCrmOrder();
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          result['success'] == true
              ? 'CRM-заявка получена и отправлена на модерацию'
              : result['error']?.toString() ?? 'Не удалось принять CRM-заявку',
        ),
        backgroundColor: result['success'] == true ? Colors.green : Colors.red,
      ),
    );

    if (result['success'] == true) {
      _refresh();
    }
  }

  List<Map<String, dynamic>> _filterOrders(List<Map<String, dynamic>> orders) {
    if (_selectedFilter == 'Все') return orders;
    return orders
        .where((order) => _orderStatusText(order['status']) == _selectedFilter)
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: _openCreateOrder,
                  icon: const Icon(Icons.add),
                  label: const Text('Создать'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _createDemoCrmOrder,
                  icon: const Icon(Icons.cloud_download_outlined),
                  label: const Text('Из CRM'),
                ),
              ),
            ],
          ),
        ),
        Container(
          color: GpmColors.surface,
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _FilterChip(
                  label: 'Все',
                  isSelected: _selectedFilter == 'Все',
                  onTap: () => setState(() => _selectedFilter = 'Все'),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'На модерации',
                  isSelected: _selectedFilter == 'На модерации',
                  onTap: () => setState(() => _selectedFilter = 'На модерации'),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'Одобрен',
                  isSelected: _selectedFilter == 'Одобрен',
                  onTap: () => setState(() => _selectedFilter = 'Одобрен'),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'В работе',
                  isSelected: _selectedFilter == 'В работе',
                  onTap: () => setState(() => _selectedFilter = 'В работе'),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'На подтверждении',
                  isSelected: _selectedFilter == 'На подтверждении',
                  onTap: () =>
                      setState(() => _selectedFilter = 'На подтверждении'),
                ),
                const SizedBox(width: 8),
                _FilterChip(
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
            future: _ordersFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }

              if (snapshot.hasError) {
                return Center(child: Text('Ошибка: ${snapshot.error}'));
              }

              final orders = _filterOrders(snapshot.data ?? []);

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

              return RefreshIndicator(
                onRefresh: () async => _refresh(),
                child: ListView.builder(
                  padding: const EdgeInsets.all(8),
                  itemCount: orders.length,
                  itemBuilder: (context, index) {
                    final order = orders[index];
                    return LogistOrderCard(order: order, onUpdate: _refresh);
                  },
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _FilterChip({
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
          color: isSelected ? GpmColors.red : Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? GpmColors.red : GpmColors.line,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : GpmColors.black,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}

class LogistOrderCard extends StatefulWidget {
  final Map<String, dynamic> order;
  final VoidCallback onUpdate;

  const LogistOrderCard({
    super.key,
    required this.order,
    required this.onUpdate,
  });

  @override
  State<LogistOrderCard> createState() => _LogistOrderCardState();
}

class _LogistOrderCardState extends State<LogistOrderCard> {
  late Map<String, dynamic> order;

  @override
  void initState() {
    super.initState();
    order = Map<String, dynamic>.from(widget.order);
  }

  @override
  void didUpdateWidget(covariant LogistOrderCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.order['id'] != widget.order['id'] ||
        oldWidget.order['status'] != widget.order['status']) {
      order = Map<String, dynamic>.from(widget.order);
    }
  }

  Future<void> _updateOrderStatus(
    BuildContext context,
    String status,
    String successText,
  ) async {
    final success = await bitrix24.updateOrderStatus(
      order['id'].toString(),
      status,
    );

    if (!context.mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(success ? successText : 'Не удалось обновить заказ'),
        backgroundColor: success ? Colors.green : Colors.red,
      ),
    );

    if (success) {
      setState(() => order['status'] = status);
      widget.onUpdate();
    }
  }

  Future<void> _refreshOrderSnapshot() async {
    final freshOrder = await bitrix24.getOrderById(order['id'].toString());
    final applications = await bitrix24.getApplicationsForOrder(
      order['id'].toString(),
    );

    if (!mounted || freshOrder == null) return;

    setState(() {
      order = Map<String, dynamic>.from(freshOrder);
      final assignedIds = order['assigned_worker_ids'];
      order['applications_count'] = applications.length;
      order['pending_applications_count'] = applications
          .where((application) => application['status'] == 'PENDING')
          .length;
      order['assigned_count'] = assignedIds is List ? assignedIds.length : 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final status = _orderStatusText(order['status']);
    final color = _orderStatusColor(order['status']);
    final pendingCount = order['pending_applications_count'] ?? 0;
    final assignedCount = order['assigned_count'] ?? 0;
    final isCrmOrder = order['source'] == 'crm';

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
                if (isCrmOrder) ...[
                  const _StatusPill(text: 'CRM', color: Colors.indigo),
                  const SizedBox(width: 6),
                ],
                _StatusPill(text: status, color: color),
              ],
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                Text(order['address'] ?? ''),
                const SizedBox(height: 2),
                Text('🗓 ${_formatSchedule(order['scheduled_at'])}'),
                const SizedBox(height: 2),
                Text(
                  '$assignedCount/${order['workers_count']} грузчиков × ${order['hours']} ч',
                ),
                const SizedBox(height: 2),
                Text(
                  pendingCount == 0
                      ? 'Новых откликов нет'
                      : 'Новых откликов: $pendingCount',
                  style: TextStyle(
                    color: pendingCount == 0 ? Colors.grey[600] : Colors.orange,
                    fontWeight:
                        pendingCount == 0 ? FontWeight.normal : FontWeight.bold,
                  ),
                ),
              ],
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () async {
              await Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => LogistOrderDetailsScreen(
                    order: order,
                    onUpdate: widget.onUpdate,
                  ),
                ),
              );
              await _refreshOrderSnapshot();
              widget.onUpdate();
            },
          ),
          if (order['status'] == 'NEW')
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () async {
                        await _updateOrderStatus(
                          context,
                          'JUNK',
                          'Заказ отклонен',
                        );
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
                        await _updateOrderStatus(
                          context,
                          'PROCESSED',
                          'Заказ одобрен и доступен исполнителям',
                        );
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

class LogistOrderDetailsScreen extends StatefulWidget {
  final Map<String, dynamic> order;
  final VoidCallback onUpdate;

  const LogistOrderDetailsScreen({
    super.key,
    required this.order,
    required this.onUpdate,
  });

  @override
  State<LogistOrderDetailsScreen> createState() =>
      _LogistOrderDetailsScreenState();
}

class _LogistOrderDetailsScreenState extends State<LogistOrderDetailsScreen> {
  late Future<List<Map<String, dynamic>>> _applicationsFuture;
  late Map<String, dynamic> order;
  bool _isUpdating = false;

  @override
  void initState() {
    super.initState();
    order = Map<String, dynamic>.from(widget.order);
    _applicationsFuture = _loadApplications();
  }

  Future<List<Map<String, dynamic>>> _loadApplications() {
    return bitrix24.getApplicationsForOrder(order['id'].toString());
  }

  Future<void> _refreshDetails() async {
    final freshOrder = await bitrix24.getOrderById(order['id'].toString());
    final applications = await bitrix24.getApplicationsForOrder(
      order['id'].toString(),
    );

    if (!mounted) return;

    setState(() {
      if (freshOrder != null) {
        order = Map<String, dynamic>.from(freshOrder);
        final assignedIds = order['assigned_worker_ids'];
        order['assigned_count'] = assignedIds is List ? assignedIds.length : 0;
        order['pending_applications_count'] = applications
            .where((application) => application['status'] == 'PENDING')
            .length;
      }
      _applicationsFuture = Future.value(applications);
    });
    widget.onUpdate();
  }

  Future<void> _approve(String applicationId) async {
    await _runAction(
      () => bitrix24.approveApplication(
        orderId: order['id'].toString(),
        applicationId: applicationId,
      ),
      'Исполнитель подтвержден',
    );
  }

  Future<void> _reject(String applicationId) async {
    await _runAction(
      () => bitrix24.rejectApplication(applicationId),
      'Отклик отклонен',
    );
  }

  Future<void> _confirmCompletion(String result) async {
    final workerId = _assignedWorkerId();
    if (workerId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('В заказе нет назначенного исполнителя'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    await _runAction(
      () => bitrix24.completeOrderWithResult(
        orderId: order['id'].toString(),
        workerId: workerId,
        result: result,
      ),
      'Заказ завершен',
    );
  }

  String? _assignedWorkerId() {
    final ids = order['assigned_worker_ids'];
    if (ids is List && ids.isNotEmpty) return ids.first.toString();
    return null;
  }

  Future<void> _runAction(
    Future<Map<String, dynamic>> Function() action,
    String successText,
  ) async {
    setState(() => _isUpdating = true);
    final result = await action();

    if (!mounted) return;
    setState(() => _isUpdating = false);

    if (result['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(successText), backgroundColor: Colors.green),
      );
      await _refreshDetails();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result['error']?.toString() ?? 'Ошибка действия'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _orderStatusText(order['status']);
    final color = _orderStatusColor(order['status']);
    final isCrmOrder = order['source'] == 'crm';

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
            if (isCrmOrder) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  const _StatusPill(text: 'Источник: CRM', color: Colors.indigo),
                  _StatusPill(
                    text: '№ ${order['external_order_id'] ?? order['id']}',
                    color: Colors.blueGrey,
                  ),
                ],
              ),
            ],
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
            const SizedBox(height: 8),
            _StatusPill(text: status, color: color),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 16),
            const Text(
              'Описание:',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(order['description'] ?? 'Нет описания'),
            const SizedBox(height: 24),
            const Text(
              'Отклики исполнителей',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            FutureBuilder<List<Map<String, dynamic>>>(
              future: _applicationsFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }

                final applications = snapshot.data ?? [];
                if (applications.isEmpty) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text('Откликов пока нет'),
                  );
                }

                return Column(
                  children: applications
                      .map(
                        (application) => _ApplicationCard(
                          application: application,
                          isUpdating: _isUpdating,
                          onApprove: () => _approve(application['id'].toString()),
                          onReject: () => _reject(application['id'].toString()),
                        ),
                      )
                      .toList(),
                );
              },
            ),
            if (order['status'] == 'DONE_PENDING') ...[
              const SizedBox(height: 24),
              const Text(
                'Оценка исполнителя',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed:
                        _isUpdating ? null : () => _confirmCompletion('success'),
                    icon: const Icon(Icons.thumb_up_alt_outlined),
                    label: const Text('Справился'),
                  ),
                  OutlinedButton.icon(
                    onPressed:
                        _isUpdating ? null : () => _confirmCompletion('fail'),
                    icon: const Icon(Icons.thumb_down_alt_outlined),
                    label: const Text('Не справился'),
                  ),
                  OutlinedButton.icon(
                    onPressed:
                        _isUpdating ? null : () => _confirmCompletion('neutral'),
                    icon: const Icon(Icons.remove_circle_outline),
                    label: const Text('Нейтрально'),
                  ),
                  OutlinedButton.icon(
                    onPressed:
                        _isUpdating ? null : () => _confirmCompletion('good'),
                    icon: const Icon(Icons.report_gmailerrorred_outlined),
                    label: const Text('С нареканиями'),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ApplicationCard extends StatelessWidget {
  final Map<String, dynamic> application;
  final bool isUpdating;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  const _ApplicationCard({
    required this.application,
    required this.isUpdating,
    required this.onApprove,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    final status = application['status']?.toString();
    final isPending = status == 'PENDING';
    final worker = application['worker'] is Map
        ? Map<String, dynamic>.from(application['worker'])
        : <String, dynamic>{};
    final priorityGroup = worker['priority_group'] is int
        ? worker['priority_group'] as int
        : 0;
    final hasPassport = worker['passport']?.toString().isNotEmpty == true;
    final hasInn = worker['inn']?.toString().isNotEmpty == true;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const CircleAvatar(child: Icon(Icons.person)),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    worker['full_name'] ?? application['worker_name'] ?? 'Исполнитель',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                _StatusPill(
                  text: _applicationStatusText(status),
                  color: _applicationStatusColor(status),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _StatusPill(
                  text: 'Группа $priorityGroup',
                  color: _priorityColor(priorityGroup),
                ),
                _StatusPill(
                  text: worker['employment_type'] == 'state'
                      ? 'Штатный'
                      : 'Подрядчик',
                  color: worker['employment_type'] == 'state'
                      ? Colors.purple
                      : Colors.blue,
                ),
                _StatusPill(
                  text: worker['nationality'] == true ? 'РФ' : 'Не РФ',
                  color: worker['nationality'] == true
                      ? Colors.green
                      : Colors.orange,
                ),
                _StatusPill(
                  text: hasPassport ? 'Паспорт OK' : 'Паспорт нет',
                  color: hasPassport ? Colors.green : Colors.orange,
                ),
                _StatusPill(
                  text: hasInn ? 'Самозанятый' : 'Без ИНН',
                  color: hasInn ? Colors.green : Colors.grey,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '${worker['phone_number'] ?? ''} · ${worker['telegram'] ?? ''}',
              style: TextStyle(color: Colors.grey[700]),
            ),
            const SizedBox(height: 4),
            Text(
              'Рейтинг: ${worker['rating'] ?? 0} · Успешно: ${worker['success_requests'] ?? 0} · Срывы: ${worker['fail_requests'] ?? 0}',
              style: TextStyle(color: Colors.grey[700]),
            ),
            if (isPending) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: isUpdating ? null : onReject,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.red,
                      ),
                      child: const Text('Отклонить'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: isUpdating ? null : onApprove,
                      child: const Text('Подтвердить'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
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

String _orderStatusText(dynamic status) {
  switch (status?.toString()) {
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

Color _orderStatusColor(dynamic status) {
  switch (status?.toString()) {
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

String _applicationStatusText(String? status) {
  switch (status) {
    case 'PENDING':
      return 'Новый';
    case 'APPROVED':
      return 'Подтвержден';
    case 'REJECTED':
      return 'Отклонен';
    default:
      return 'Неизвестно';
  }
}

Color _applicationStatusColor(String? status) {
  switch (status) {
    case 'PENDING':
      return Colors.orange;
    case 'APPROVED':
      return Colors.green;
    case 'REJECTED':
      return Colors.red;
    default:
      return Colors.grey;
  }
}

Color _priorityColor(int group) {
  if (group == 1) return Colors.purple;
  if (group >= 2 && group <= 4) return Colors.green;
  if (group >= 5 && group <= 7) return Colors.blue;
  if (group == 8) return Colors.orange;
  return Colors.grey;
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

import 'dart:convert';

import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'demo_storage.dart';

class Bitrix24Service {
  static const demoWorkerId = 'worker-demo-1';
  static const demoWorkerName = 'Иван Петров';

  late String _webhook;
  final List<Map<String, dynamic>> _demoOrders = [
    {
      'id': '1001',
      'title': 'Переезд офиса',
      'status': 'NEW',
      'address': 'ул. Ленина, 10',
      'workers_count': 3,
      'hours': 4,
      'description': 'Перевезти мебель и технику',
      'created_at': '2026-06-24T09:00:00.000Z',
      'assigned_worker_ids': <String>[],
    },
    {
      'id': '1002',
      'title': 'Разгрузка склада',
      'status': 'IN_PROCESS',
      'address': 'пр. Мира, 55',
      'workers_count': 2,
      'hours': 3,
      'description': 'Разгрузить фуру с товаром',
      'created_at': '2026-06-23T12:00:00.000Z',
      'assigned_worker_ids': <String>[demoWorkerId],
    },
    {
      'id': '1003',
      'title': 'Подъём стройматериалов',
      'status': 'CONVERTED',
      'address': 'ул. Строителей, 7',
      'workers_count': 4,
      'hours': 6,
      'description': 'Поднять кирпич на 5 этаж',
      'created_at': '2026-06-22T08:30:00.000Z',
      'assigned_worker_ids': <String>[demoWorkerId],
    },
  ];

  final List<Map<String, dynamic>> _demoApplications = [
    {
      'id': 'app-1002-1',
      'order_id': '1002',
      'worker_id': demoWorkerId,
      'worker_name': demoWorkerName,
      'status': 'APPROVED',
      'created_at': '2026-06-23T12:15:00.000Z',
    },
    {
      'id': 'app-1003-1',
      'order_id': '1003',
      'worker_id': demoWorkerId,
      'worker_name': demoWorkerName,
      'status': 'APPROVED',
      'created_at': '2026-06-22T08:45:00.000Z',
    },
  ];

  final Map<String, Map<String, dynamic>> _demoWorkers = {
    demoWorkerId: {
      'id': demoWorkerId,
      'full_name': demoWorkerName,
      'phone_number': '+7 900 123-45-67',
      'telegram': '@ivan_loader',
      'date_birth': '15.04.1994',
      'nationality': true,
      'cities': <String>['Москва', 'Химки'],
      'tools': {'straps': true, 'tools': true},
      'employment_type': 'contract',
      'inn': '772812345678',
      'passport': '4512 345678',
      'card_last4': '',
      'mark': 'Нет',
      'success_requests': 8,
      'fail_requests': 1,
      'rating': 14,
    },
  };

  Bitrix24Service() {
    _webhook = dotenv.env['BITRIX24_WEBHOOK'] ?? '';
    // Не бросаем исключение если webhook не задан — работаем в демо-режиме
    if (!isConfigured) {
      _loadDemoState();
    }
  }

  bool get isConfigured => _webhook.isNotEmpty;

  Future<Map<String, dynamic>> createOrder({
    required String title,
    required String address,
    required int workersCount,
    required int hours,
    required String description,
    required String clientEmail,
    required String clientPhone,
    String? scheduledAt,
    String? city,
    String source = 'manual',
    String? externalOrderId,
    String? metro,
    String? national,
    int? minTime,
    int? pricePerHour,
    int? priceRegular,
    int? priceState,
    String? nationality,
    String? workerCategory,
    String? workMode,
    String? shiftDescription,
  }) async {
    // Демо-режим если webhook не настроен
    if (!isConfigured) {
      final orderId = DateTime.now().microsecondsSinceEpoch.toString();
      _demoOrders.insert(0, {
        'id': orderId,
        'title': title,
        'status': 'NEW',
        'address': address,
        'workers_count': workersCount,
        'hours': hours,
        'description': description,
        'client_email': clientEmail,
        'client_phone': clientPhone,
        'scheduled_at': scheduledAt,
        'city': city,
        'source': source,
        'external_order_id': externalOrderId,
        'metro': metro,
        'national': national,
        'min_time': minTime,
        'price_per_hour': pricePerHour,
        'price_regular': priceRegular,
        'price_state': priceState,
        'nationality': nationality,
        'worker_category': workerCategory,
        'work_mode': workMode,
        'shift_description': shiftDescription,
        'created_at': DateTime.now().toUtc().toIso8601String(),
        'assigned_worker_ids': <String>[],
      });
      _saveDemoState();
      return {'success': true, 'orderId': orderId};
    }

    try {
      // HTTP запрос к Bitrix24 (реализация через dart:io если нужно)
      return {'success': true, 'orderId': '1'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<List<Map<String, dynamic>>> getOrders() async {
    if (!isConfigured) {
      return _demoOrders
          .map((order) => Map<String, dynamic>.from(order))
          .toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> createDemoCrmOrder() async {
    final now = DateTime.now();
    const externalOrderId = 'CRM-DEMO-1001';

    final existingIndex = _demoOrders.indexWhere(
      (order) => order['external_order_id'] == externalOrderId,
    );
    if (existingIndex != -1) {
      return {'success': true, 'orderId': _demoOrders[existingIndex]['id']};
    }

    return createOrder(
      title: 'Разгрузка склада',
      address: 'ул. Складская, 18',
      workersCount: 3,
      hours: 4,
      description:
          'Разгрузить машину, перенести коробки на склад, нужен аккуратный подъем.',
      clientEmail: 'crm@gpm.ru',
      clientPhone: '',
      scheduledAt:
          now.add(const Duration(days: 1, hours: 2)).toUtc().toIso8601String(),
      city: 'Москва',
      source: 'crm',
      externalOrderId: externalOrderId,
      metro: 'Динамо',
      national: 'yes',
      minTime: 4,
      pricePerHour: 400,
      priceRegular: 450,
      priceState: 450,
      nationality: 'ru',
      workMode: 'shift',
      shiftDescription: 'Дневная смена 09:00-18:00, 5000 руб за смену',
    );
  }

  Future<Map<String, dynamic>?> getOrderById(String leadId) async {
    final orders = await getOrders();
    try {
      return orders.firstWhere((o) => o['id'] == leadId);
    } catch (_) {
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> getOrdersForWorker(String workerId) async {
    final orders = await getOrders();
    return orders.map((order) => _withWorkerMeta(order, workerId)).toList();
  }

  Future<List<Map<String, dynamic>>> getApplicationsForOrder(
    String orderId,
  ) async {
    return _demoApplications
        .where((application) => application['order_id'] == orderId)
        .map((application) {
      final copy = Map<String, dynamic>.from(application);
      final worker = getWorkerProfileSync(copy['worker_id'].toString());
      if (worker != null) {
        copy['worker'] = worker;
      }
      return copy;
    }).toList();
  }

  Map<String, dynamic>? getWorkerProfileSync(String workerId) {
    final worker = _demoWorkers[workerId];
    if (worker == null) return null;

    final copy = Map<String, dynamic>.from(worker);
    copy['priority_group'] = calculatePriorityGroup(copy);
    copy['priority_label'] = priorityGroupLabel(copy['priority_group'] as int);
    return copy;
  }

  Future<Map<String, dynamic>?> getWorkerProfile(String workerId) async {
    return getWorkerProfileSync(workerId);
  }

  Future<bool> updateWorkerProfile(
    String workerId,
    Map<String, dynamic> data,
  ) async {
    final worker = _demoWorkers[workerId];
    if (worker == null) return false;

    worker.addAll(data);
    _saveDemoState();
    return true;
  }

  int calculatePriorityGroup(Map<String, dynamic> worker) {
    if (worker['employment_type'] == 'state') return 1;

    final isRussian = worker['nationality'] == true;
    final hasPassport = (worker['passport']?.toString().isNotEmpty ?? false);
    final hasInn = (worker['inn']?.toString().isNotEmpty ?? false);

    if (isRussian && hasPassport && hasInn) return 2;
    if (isRussian && hasInn) return 3;
    if (hasInn && hasPassport) return 4;
    if (hasInn) return 5;
    if (isRussian && hasPassport) return 6;
    if (hasPassport) return 7;
    if (isRussian) return 8;
    return 0;
  }

  String priorityGroupLabel(int group) {
    switch (group) {
      case 1:
        return 'Штатный';
      case 2:
        return 'РФ, паспорт, самозанятый';
      case 3:
        return 'РФ, самозанятый';
      case 4:
        return 'Паспорт, самозанятый';
      case 5:
        return 'Самозанятый';
      case 6:
        return 'РФ, паспорт';
      case 7:
        return 'Паспорт';
      case 8:
        return 'РФ';
      default:
        return 'Остальные';
    }
  }

  Future<Map<String, dynamic>> applyToOrder({
    required String orderId,
    required String workerId,
    required String workerName,
  }) async {
    final order = await getOrderById(orderId);
    if (order == null) {
      return {'success': false, 'error': 'Заявка не найдена'};
    }

    final existing = _demoApplications.where(
      (application) =>
          application['order_id'] == orderId &&
          application['worker_id'] == workerId,
    );
    if (existing.isNotEmpty) {
      return {'success': true, 'applicationId': existing.first['id']};
    }

    final applicationId = DateTime.now().microsecondsSinceEpoch.toString();
    _demoApplications.insert(0, {
      'id': applicationId,
      'order_id': orderId,
      'worker_id': workerId,
      'worker_name': workerName,
      'status': 'PENDING',
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
    _saveDemoState();

    return {'success': true, 'applicationId': applicationId};
  }

  Future<Map<String, dynamic>> approveApplication({
    required String orderId,
    required String applicationId,
  }) async {
    final orderIndex =
        _demoOrders.indexWhere((order) => order['id'] == orderId);
    if (orderIndex == -1) {
      return {'success': false, 'error': 'Заявка не найдена'};
    }

    final applicationIndex = _demoApplications.indexWhere(
      (application) => application['id'] == applicationId,
    );
    if (applicationIndex == -1) {
      return {'success': false, 'error': 'Отклик не найден'};
    }

    final order = _demoOrders[orderIndex];
    final assignedWorkerIds = _assignedWorkerIds(order);
    final workersCount = order['workers_count'] as int? ?? 1;
    final workerId = _demoApplications[applicationIndex]['worker_id'] as String;

    if (!assignedWorkerIds.contains(workerId) &&
        assignedWorkerIds.length >= workersCount) {
      return {'success': false, 'error': 'Все места уже закрыты'};
    }

    _demoApplications[applicationIndex]['status'] = 'APPROVED';
    if (!assignedWorkerIds.contains(workerId)) {
      assignedWorkerIds.add(workerId);
    }
    order['assigned_worker_ids'] = assignedWorkerIds;
    order['status'] =
        assignedWorkerIds.length >= workersCount ? 'IN_PROCESS' : 'PROCESSED';
    _saveDemoState();

    return {'success': true};
  }

  Future<Map<String, dynamic>> rejectApplication(String applicationId) async {
    final applicationIndex = _demoApplications.indexWhere(
      (application) => application['id'] == applicationId,
    );
    if (applicationIndex == -1) {
      return {'success': false, 'error': 'Отклик не найден'};
    }

    _demoApplications[applicationIndex]['status'] = 'REJECTED';
    _saveDemoState();
    return {'success': true};
  }

  Future<Map<String, dynamic>> completeOrderWithResult({
    required String orderId,
    required String workerId,
    required String result,
  }) async {
    final orderIndex =
        _demoOrders.indexWhere((order) => order['id'] == orderId);
    if (orderIndex == -1) {
      return {'success': false, 'error': 'Заявка не найдена'};
    }

    final worker = _demoWorkers[workerId];
    if (worker == null) {
      return {'success': false, 'error': 'Исполнитель не найден'};
    }

    switch (result) {
      case 'success':
        worker['success_requests'] =
            (worker['success_requests'] as int? ?? 0) + 1;
        worker['rating'] = (worker['rating'] as int? ?? 0) + 2;
        break;
      case 'fail':
        worker['fail_requests'] = (worker['fail_requests'] as int? ?? 0) + 1;
        worker['rating'] = (worker['rating'] as int? ?? 0) - 2;
        break;
      case 'good':
        worker['rating'] = (worker['rating'] as int? ?? 0) + 1;
        break;
      case 'neutral':
        break;
      default:
        return {'success': false, 'error': 'Неизвестная оценка'};
    }

    _demoOrders[orderIndex]['status'] = 'CONVERTED';
    _saveDemoState();
    return {'success': true};
  }

  Future<bool> updateOrderStatus(String leadId, String newStatus) async {
    if (!isConfigured) {
      final index = _demoOrders.indexWhere((order) => order['id'] == leadId);
      if (index == -1) return false;
      _demoOrders[index]['status'] = newStatus;
      _saveDemoState();
    }
    return true;
  }

  Future<Map<String, dynamic>> createContact({
    required String name,
    required String email,
    required String phone,
    required String role,
  }) async {
    return {
      'success': true,
      'contactId': DateTime.now().millisecondsSinceEpoch.toString()
    };
  }

  Future<List<Map<String, dynamic>>> getContacts() async {
    return [];
  }

  Future<bool> addComment(String leadId, String comment) async {
    return true;
  }

  Future<Map<String, dynamic>> createDeal({
    required String title,
    required int amount,
    required String contactId,
  }) async {
    return {'success': true, 'dealId': '1'};
  }

  Future<Map<String, dynamic>> getFinancialStats() async {
    return {'totalIncome': 125000, 'totalDeals': 47, 'averageDeal': 2659};
  }

  Map<String, dynamic> _withWorkerMeta(
    Map<String, dynamic> order,
    String workerId,
  ) {
    final copy = Map<String, dynamic>.from(order);
    final assignedWorkerIds = _assignedWorkerIds(copy);
    final workerApplications = _demoApplications.where(
      (application) =>
          application['order_id'] == copy['id'] &&
          application['worker_id'] == workerId,
    );
    final applications = _demoApplications.where(
      (application) => application['order_id'] == copy['id'],
    );

    copy['assigned_worker_ids'] = assignedWorkerIds;
    copy['assigned_count'] = assignedWorkerIds.length;
    copy['applications_count'] = applications.length;
    copy['worker_application_status'] =
        workerApplications.isEmpty ? null : workerApplications.first['status'];
    copy['is_assigned_to_worker'] = assignedWorkerIds.contains(workerId);
    return copy;
  }

  List<String> _assignedWorkerIds(Map<String, dynamic> order) {
    final rawIds = order['assigned_worker_ids'];
    if (rawIds is List<String>) return List<String>.from(rawIds);
    if (rawIds is List) return rawIds.map((id) => id.toString()).toList();
    return <String>[];
  }

  void _loadDemoState() {
    final rawState = readDemoValue('gpm_demo_state_v1');
    if (rawState == null || rawState.isEmpty) return;

    try {
      final decoded = jsonDecode(rawState);
      if (decoded is! Map<String, dynamic>) return;

      final orders = decoded['orders'];
      if (orders is List) {
        _demoOrders
          ..clear()
          ..addAll(orders.map((order) {
            final copy = Map<String, dynamic>.from(order);
            if (copy['source'] == 'crm' &&
                copy['title'] == 'Разгрузка из CRM') {
              copy['title'] = 'Разгрузка склада';
            }
            final description = copy['description']?.toString();
            if (copy['source'] == 'crm' &&
                description != null &&
                description.startsWith('CRM: ')) {
              copy['description'] = description.substring(5);
            }
            return copy;
          }));
      }

      final applications = decoded['applications'];
      if (applications is List) {
        _demoApplications
          ..clear()
          ..addAll(
            applications.map(
              (application) => Map<String, dynamic>.from(application),
            ),
          );
      }

      final workers = decoded['workers'];
      if (workers is Map) {
        _demoWorkers
          ..clear()
          ..addAll(
            workers.map(
              (key, value) => MapEntry(
                key.toString(),
                Map<String, dynamic>.from(value as Map),
              ),
            ),
          );
      }
      _normalizeDemoCrmOrders();
      _saveDemoState();
    } catch (_) {
      // If demo state is malformed, keep bundled seed data.
    }
  }

  void _normalizeDemoCrmOrders() {
    final seenDemoCrmOrderIds = <String>{};
    final normalizedOrders = <Map<String, dynamic>>[];

    for (final order in _demoOrders) {
      final copy = Map<String, dynamic>.from(order);
      final isCrm = copy['source'] == 'crm';

      if (isCrm && copy['title'] == 'Разгрузка из CRM') {
        copy['title'] = 'Разгрузка склада';
      }

      final description = copy['description']?.toString();
      if (isCrm && description != null && description.startsWith('CRM: ')) {
        copy['description'] = description.substring(5);
      }

      if (isCrm &&
          copy['title'] == 'Разгрузка склада' &&
          copy['address'] == 'ул. Складская, 18') {
        copy['external_order_id'] = 'CRM-DEMO-1001';
        if (seenDemoCrmOrderIds.contains('CRM-DEMO-1001')) {
          continue;
        }
        seenDemoCrmOrderIds.add('CRM-DEMO-1001');
      }

      normalizedOrders.add(copy);
    }

    _demoOrders
      ..clear()
      ..addAll(normalizedOrders);
  }

  void _saveDemoState() {
    if (isConfigured) return;

    writeDemoValue(
      'gpm_demo_state_v1',
      jsonEncode({
        'orders': _demoOrders,
        'applications': _demoApplications,
        'workers': _demoWorkers,
      }),
    );
  }
}

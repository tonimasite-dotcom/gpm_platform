import 'bitrix24_service.dart';

/// Compatibility layer для старого кода который использует Supabase API
class SupabaseCompatibilityLayer {
  final Bitrix24Service _bitrix24;

  SupabaseCompatibilityLayer(this._bitrix24);

  QueryBuilder from(String table) {
    return QueryBuilder(this, table);
  }
}

class QueryBuilder {
  final SupabaseCompatibilityLayer _compat;
  final String _table;
  String? _filterColumn;
  dynamic _filterValue;
  String? _orderColumn;
  bool _ascending = true;
  int? _limitCount;
  String? _orFilter;

  QueryBuilder(this._compat, this._table);

  QueryBuilder select([String? columns]) => this;

  QueryBuilder eq(String column, dynamic value) {
    _filterColumn = column;
    _filterValue = value;
    return this;
  }

  QueryBuilder or(String filter) {
    _orFilter = filter;
    return this;
  }

  QueryBuilder order(String column, {bool ascending = true}) {
    _orderColumn = column;
    _ascending = ascending;
    return this;
  }

  QueryBuilder limit(int count) {
    _limitCount = count;
    return this;
  }

  Future<void> insert(Map<String, dynamic> data) async {
    final result = await _compat._bitrix24.createOrder(
      title: data['title'] ?? 'Заказ грузчиков',
      address: data['address'] ?? '',
      workersCount: data['workers_count'] ?? 1,
      hours: data['hours'] ?? 1,
      description: data['description'] ?? '',
      clientEmail: data['client_email'] ?? 'client@gpm.ru',
      clientPhone: data['client_phone'] ?? '',
    );
    if (result['success'] != true) {
      throw StateError(
          result['error']?.toString() ?? 'Не удалось создать заказ');
    }
  }

  Future<void> update(Map<String, dynamic> data) async {
    if (_filterColumn == 'id' && _filterValue != null) {
      final newStatus = data['status'] as String?;
      if (newStatus != null) {
        final success = await _compat._bitrix24.updateOrderStatus(
          _filterValue.toString(),
          _mapStatusToBitrix(newStatus),
        );
        if (!success) {
          throw StateError('Заказ не найден');
        }
      }
    }
  }

  String _mapStatusToBitrix(String status) {
    switch (status) {
      case 'Одобрен':
        return 'PROCESSED';
      case 'В работе':
        return 'IN_PROCESS';
      case 'Завершен':
        return 'CONVERTED';
      case 'На подтверждении':
        return 'DONE_PENDING';
      case 'Отклонён':
        return 'JUNK';
      default:
        return 'NEW';
    }
  }

  Future<List<Map<String, dynamic>>> execute() async {
    List<Map<String, dynamic>> results = [];

    if (_table == 'orders') {
      final orders = await _compat._bitrix24.getOrders();
      results = orders
          .map((o) => {
                'id': o['id'] ?? '',
                'title': o['title'] ?? 'Заказ',
                'status': _mapBitrixStatus(o['status'] ?? 'NEW'),
                'address': o['address'] ?? '',
                'workers_count': o['workers_count'] ?? 1,
                'hours': o['hours'] ?? 1,
                'description': o['description'] ?? '',
                'created_at': o['created_at'],
              })
          .toList();

      if (_filterColumn != null && _filterValue != null) {
        results =
            results.where((o) => o[_filterColumn] == _filterValue).toList();
      }

      if (_orFilter != null) {
        final statuses = _parseOrFilter(_orFilter!);
        results = results.where((o) => statuses.contains(o['status'])).toList();
      }
    } else if (_table == 'profiles') {
      final contacts = await _compat._bitrix24.getContacts();
      results = contacts;
    }

    if (_orderColumn != null) {
      results.sort((a, b) {
        final left = a[_orderColumn]?.toString() ?? '';
        final right = b[_orderColumn]?.toString() ?? '';
        return _ascending ? left.compareTo(right) : right.compareTo(left);
      });
    }

    if (_limitCount != null && results.length > _limitCount!) {
      results = results.sublist(0, _limitCount!);
    }

    return results;
  }

  List<String> _parseOrFilter(String filter) {
    final statuses = <String>[];
    final parts = filter.split(',');
    for (final part in parts) {
      final match = RegExp(r'status\.eq\.(.+)').firstMatch(part.trim());
      if (match != null) {
        statuses.add(match.group(1)!);
      }
    }
    return statuses;
  }

  String _mapBitrixStatus(String bitrixStatus) {
    switch (bitrixStatus) {
      case 'NEW':
        return 'На модерации';
      case 'PROCESSED':
        return 'Одобрен';
      case 'IN_PROCESS':
        return 'В работе';
      case 'CONVERTED':
        return 'Завершен';
      case 'DONE_PENDING':
        return 'На подтверждении';
      case 'JUNK':
        return 'Отклонён';
      default:
        return 'На модерации';
    }
  }

  Future<Map<String, dynamic>?> single() async {
    final results = await execute();
    return results.isNotEmpty ? results.first : null;
  }
}

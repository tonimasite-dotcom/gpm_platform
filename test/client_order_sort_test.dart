import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/utils/client_order_sort.dart';

void main() {
  final orders = <Map<String, dynamic>>[
    {'id': 'a', 'status': 'PROCESSED', 'workers_count': 2, 'created_at': '2026-11-20T10:00:00Z'},
    {'id': 'b', 'status': 'NEW', 'workers_count': 3, 'created_at': '2026-11-20T11:00:00Z'},
    {'id': 'c', 'status': 'NEW', 'workers_count': 1, 'created_at': '2026-11-20T09:00:00Z'},
  ];
  test('priorities compose and preserve the input', () {
    final sorted = sortClientOrders(orders, [ClientOrderSort.status, ClientOrderSort.workers]);
    expect(sorted.map((o) => o['id']), ['b', 'c', 'a']);
    final reversed = sortClientOrders(orders, [ClientOrderSort.workers, ClientOrderSort.status]);
    expect(reversed.map((o) => o['id']), ['b', 'a', 'c']);
    expect(orders.map((o) => o['id']), ['a', 'b', 'c']);
  });
  test('dates compare instants, missing values come last in both directions', () {
    final values = <Map<String, dynamic>>[
      {'id': 'later', 'created_at': '2026-11-20T10:00:00Z'},
      {'id': 'earlier', 'created_at': '2026-11-20T11:00:00+03:00'},
      {'id': 'missing'},
      {'id': 'broken', 'created_at': 'invalid'},
    ];
    expect(sortClientOrders(values, [ClientOrderSort.dateAsc]).take(2).map((o) => o['id']), ['earlier', 'later']);
    expect(sortClientOrders(values, [ClientOrderSort.dateDesc]).take(2).map((o) => o['id']), ['later', 'earlier']);
  });
  test('equal values use stable order IDs and unknown statuses come last', () {
    final values = <Map<String, dynamic>>[
      {'id': 'b', 'status': 'NEW'},
      {'id': 'unknown', 'status': 'other'},
      {'id': 'a', 'status': 'NEW'},
    ];
    expect(sortClientOrders(values, [ClientOrderSort.status]).map((o) => o['id']), ['a', 'b', 'unknown']);
  });
}

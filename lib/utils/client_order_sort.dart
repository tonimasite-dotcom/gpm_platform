enum ClientOrderSort {
  dateDesc('По дате: сначала новые'),
  dateAsc('По дате: сначала старые'),
  status('По статусу'),
  workers('По количеству рабочих');

  const ClientOrderSort(this.label);
  final String label;
  bool get isDate => this == dateDesc || this == dateAsc;
}

List<Map<String, dynamic>> sortClientOrders(
  List<Map<String, dynamic>> orders,
  List<ClientOrderSort> priorities,
) {
  final fields = priorities.isEmpty ? [ClientOrderSort.dateDesc] : priorities;
  final result = [...orders];
  result.sort((a, b) {
    for (final field in fields) {
      final int compared;
      switch (field) {
        case ClientOrderSort.dateDesc:
        case ClientOrderSort.dateAsc:
          final left = DateTime.tryParse(a['created_at']?.toString() ?? '');
          final right = DateTime.tryParse(b['created_at']?.toString() ?? '');
          if (left == null || right == null) {
            compared = left == right ? 0 : (left == null ? 1 : -1);
          } else {
            compared = field == ClientOrderSort.dateDesc
                ? right.compareTo(left)
                : left.compareTo(right);
          }
        case ClientOrderSort.status:
          const statuses = ['NEW', 'PROCESSED', 'IN_PROCESS', 'DONE_PENDING', 'CONVERTED', 'JUNK'];
          int rank(dynamic value) {
            final index = statuses.indexOf(value?.toString() ?? '');
            return index < 0 ? statuses.length : index;
          }
          compared = rank(a['status']).compareTo(rank(b['status']));
        case ClientOrderSort.workers:
          int count(dynamic value) => int.tryParse(value?.toString() ?? '') ?? 0;
          compared = count(b['workers_count']).compareTo(count(a['workers_count']));
      }
      if (compared != 0) return compared;
    }
    return (a['id']?.toString() ?? '').compareTo(b['id']?.toString() ?? '');
  });
  return result;
}

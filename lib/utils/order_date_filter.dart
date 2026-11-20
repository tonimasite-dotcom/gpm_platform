/// Calendar dates use the same local timezone as the dates on order cards.
bool matchesOrderDateRange(
  dynamic value, {
  DateTime? from,
  DateTime? to,
}) {
  if (from == null && to == null) return true;
  final timestamp = DateTime.tryParse(value?.toString().trim() ?? '')?.toLocal();
  if (timestamp == null) return false;
  final start = from == null ? null : DateTime(from.year, from.month, from.day);
  // Construct the next calendar day: DST days need not be exactly 24 hours.
  final end = to == null ? null : DateTime(to.year, to.month, to.day + 1);
  return (start == null || !timestamp.isBefore(start)) &&
      (end == null || timestamp.isBefore(end));
}

enum WorkerOrderDay {
  today('Сегодня'),
  tomorrow('Завтра'),
  all('Все');

  const WorkerOrderDay(this.label);
  final String label;
}

bool matchesWorkerOrderDay(
  dynamic scheduledAt,
  WorkerOrderDay selection, {
  DateTime? now,
}) {
  if (selection == WorkerOrderDay.all) return true;
  final current = (now ?? DateTime.now()).toLocal();
  final date = DateTime(
    current.year,
    current.month,
    current.day + (selection == WorkerOrderDay.tomorrow ? 1 : 0),
  );
  return matchesOrderDateRange(scheduledAt, from: date, to: date);
}

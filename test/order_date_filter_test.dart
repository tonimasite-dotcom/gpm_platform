import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/utils/order_date_filter.dart';

void main() {
  test('inclusive calendar range includes the entire last day and UTC timestamps', () {
    final start = DateTime(2026, 11, 20);
    final end = DateTime(2026, 11, 21);
    bool matches(DateTime value) => matchesOrderDateRange(
      value.toUtc().toIso8601String(), from: start, to: end,
    );
    expect(matches(start), isTrue);
    expect(matches(DateTime(2026, 11, 21, 23, 59, 59, 999)), isTrue);
    expect(matches(DateTime(2026, 11, 19, 23, 59, 59, 999)), isFalse);
    expect(matches(DateTime(2026, 11, 22)), isFalse);
  });
  test('missing or invalid dates are retained only without an active filter', () {
    for (final value in [null, '', 'not-a-date']) {
      expect(matchesOrderDateRange(value), isTrue);
      expect(matchesWorkerOrderDay(value, WorkerOrderDay.all), isTrue);
      expect(matchesOrderDateRange(value, from: DateTime(2026, 11, 20)), isFalse);
      expect(matchesWorkerOrderDay(value, WorkerOrderDay.today), isFalse);
    }
  });
  test('today and tomorrow cross year boundary using scheduled date', () {
    final now = DateTime(2026, 12, 31, 23, 59);
    final today = DateTime(2026, 12, 31).toUtc().toIso8601String();
    final tomorrow = DateTime(2027, 1, 1, 23, 59).toUtc().toIso8601String();
    expect(matchesWorkerOrderDay(today, WorkerOrderDay.today, now: now), isTrue);
    expect(matchesWorkerOrderDay(tomorrow, WorkerOrderDay.today, now: now), isFalse);
    expect(matchesWorkerOrderDay(tomorrow, WorkerOrderDay.tomorrow, now: now), isTrue);
    expect(matchesWorkerOrderDay(today, WorkerOrderDay.tomorrow, now: now), isFalse);
  });
}

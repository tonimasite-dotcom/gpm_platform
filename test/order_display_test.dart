import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/utils/order_display.dart';

void main() {
  group('orderStatusText', () {
    test('maps every backend status code to a Russian label', () {
      expect(orderStatusText('NEW'), 'На модерации');
      expect(orderStatusText('PROCESSED'), 'Одобрен');
      expect(orderStatusText('IN_PROCESS'), 'В работе');
      expect(orderStatusText('DONE_PENDING'), 'На подтверждении');
      expect(orderStatusText('CONVERTED'), 'Завершен');
      expect(orderStatusText('JUNK'), 'Отклонен');
    });

    test('never leaks a raw code for unknown or null input', () {
      expect(orderStatusText(null), 'Неизвестно');
      expect(orderStatusText('SOMETHING_ELSE'), 'Неизвестно');
    });
  });

  test('orderStatusColor returns a stable colour per status', () {
    expect(orderStatusColor('IN_PROCESS'), Colors.green);
    expect(orderStatusColor('JUNK'), Colors.red);
    expect(orderStatusColor(null), Colors.grey);
  });

  group('formatOrderSchedule', () {
    test('renders local date and time with the year', () {
      final iso = DateTime(2026, 9, 8, 14, 30).toIso8601String();
      expect(formatOrderSchedule(iso), '08.09.2026 14:30');
    });

    test('handles missing and unparseable values', () {
      expect(formatOrderSchedule(null), 'Дата не указана');
      expect(formatOrderSchedule(''), 'Дата не указана');
      expect(formatOrderSchedule('not-a-date'), 'not-a-date');
    });
  });

  group('hoursText', () {
    test('picks the correct Russian plural form', () {
      expect(hoursText(1), '1 час');
      expect(hoursText(2), '2 часа');
      expect(hoursText(4), '4 часа');
      expect(hoursText(5), '5 часов');
      expect(hoursText(11), '11 часов');
      expect(hoursText(21), '21 час');
      expect(hoursText(0), '0 часов');
    });

    test('accepts string input and rejects non-numbers', () {
      expect(hoursText('3'), '3 часа');
      expect(hoursText(null), '');
      expect(hoursText('abc'), '');
    });
  });
}

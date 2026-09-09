import 'package:flutter/material.dart';

/// Shared order presentation helpers.
///
/// Order status is stored as a raw backend code (`NEW`, `PROCESSED`,
/// `IN_PROCESS`, `DONE_PENDING`, `CONVERTED`, `JUNK`). Every cabinet must render
/// it through [orderStatusText] / [orderStatusColor] so the label and colour
/// stay identical across the client, logist and worker screens.

/// Localised status label for a raw backend status code.
String orderStatusText(dynamic status) {
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

/// Accent colour for a raw backend status code.
Color orderStatusColor(dynamic status) {
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

/// `2026-09-08T14:30:00Z` -> `08.09.2026 14:30` in local time.
///
/// The year is always shown: orders can be scheduled up to a year ahead, so a
/// bare `08.09` is ambiguous.
String formatOrderSchedule(dynamic value) {
  final raw = value?.toString();
  if (raw == null || raw.isEmpty) return 'Дата не указана';

  final dateTime = DateTime.tryParse(raw)?.toLocal();
  if (dateTime == null) return raw;

  final day = dateTime.day.toString().padLeft(2, '0');
  final month = dateTime.month.toString().padLeft(2, '0');
  final hour = dateTime.hour.toString().padLeft(2, '0');
  final minute = dateTime.minute.toString().padLeft(2, '0');
  return '$day.$month.${dateTime.year} $hour:$minute';
}

/// Russian pluralisation for a whole number of hours: `1 час`, `2 часа`,
/// `5 часов`, `21 час`.
String hoursText(dynamic value) {
  final hours = int.tryParse(value?.toString() ?? '');
  if (hours == null) return '';
  return '$hours ${pluralRu(hours, 'час', 'часа', 'часов')}';
}

/// Picks the Russian plural form for [count]: [one] for 1, [few] for 2-4,
/// [many] for 0 and 5+, with the usual 11-14 exception.
String pluralRu(int count, String one, String few, String many) {
  final absCount = count.abs();
  final mod100 = absCount % 100;
  if (mod100 >= 11 && mod100 <= 14) return many;
  switch (absCount % 10) {
    case 1:
      return one;
    case 2:
    case 3:
    case 4:
      return few;
    default:
      return many;
  }
}

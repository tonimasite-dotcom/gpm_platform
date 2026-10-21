import 'package:flutter/material.dart';

import '../theme/gpm_theme.dart';

const orderCardShape = RoundedRectangleBorder(
  borderRadius: BorderRadius.all(Radius.circular(10)),
  side: BorderSide(color: GpmColors.line),
);

int _paymentNumber(dynamic value) => int.tryParse(value?.toString() ?? '') ?? 0;

int _performerRate(Map<String, dynamic> order) => [
  _paymentNumber(order['price_per_hour']),
  _paymentNumber(order['price_state']),
  _paymentNumber(order['price_regular']),
].firstWhere((value) => value > 0, orElse: () => 0);

/// Show only the stored performer rate, using the order's payment unit.
String workerRateText(Map<String, dynamic> order) {
  final isShift = order['work_mode'] == 'shift';
  final unit = isShift ? 'смена' : 'ч';
  final rate = _performerRate(order);
  return rate > 0 ? 'Ставка: $rate ₽/$unit' : 'Ставка не указана';
}

/// Payment per performer. Legacy orders with only a total budget are split
/// across the requested worker slots, just as the backend accrual does.
List<String> workerPaymentLines(Map<String, dynamic> order) {
  int number(dynamic value) => int.tryParse(value?.toString() ?? '') ?? 0;
  final rate = _performerRate(order);
  final minimum = number(order['min_time']);
  final planned = number(order['hours']);
  final hours = planned > minimum ? planned : minimum;
  if (rate > 0) {
    if (order['work_mode'] == 'shift') {
      return [workerRateText(order), 'Предполагаемый заработок: $rate ₽'];
    }
    return [
      workerRateText(order),
      if (hours > 0) 'Предполагаемый заработок: ${rate * hours} ₽',
      if (minimum > 0) 'Минимальное оплачиваемое время: ${hoursText(minimum)}',
    ];
  }
  final individual = number(order['individual_price']);
  final budget = individual > 0 ? individual : number(order['legal_price']);
  final slots = number(order['workers_count']);
  return [
    workerRateText(order),
    if (budget > 0)
      'Предполагаемый заработок: ${budget ~/ (slots > 0 ? slots : 1)} ₽'
    else
      'Оплата уточняется у логиста',
  ];
}

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

/// Formats the server-owned moment when an order was first published.
///
/// Returns `null` for legacy/incomplete records instead of showing a made-up
/// timestamp. New app and CRM orders always receive `created_at` from the
/// backend when they are first persisted.
String? formatOrderPublishedAt(dynamic value) {
  final raw = value?.toString().trim();
  if (raw == null || raw.isEmpty) return null;

  final dateTime = DateTime.tryParse(raw)?.toLocal();
  if (dateTime == null) return null;

  final day = dateTime.day.toString().padLeft(2, '0');
  final month = dateTime.month.toString().padLeft(2, '0');
  final hour = dateTime.hour.toString().padLeft(2, '0');
  final minute = dateTime.minute.toString().padLeft(2, '0');
  return '$day.$month.${dateTime.year} $hour:$minute';
}

/// Compact, shared publication marker for order cards in every cabinet.
class OrderPublishedAtMarker extends StatelessWidget {
  final dynamic createdAt;

  const OrderPublishedAtMarker({super.key, required this.createdAt});

  @override
  Widget build(BuildContext context) {
    final publishedAt = formatOrderPublishedAt(createdAt);
    if (publishedAt == null) return const SizedBox.shrink();

    const foreground = GpmColors.black;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: GpmColors.yellow,
        borderRadius: BorderRadius.circular(3),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.schedule_rounded, size: 13, color: foreground),
          const SizedBox(width: 4),
          Text(
            'Опубликовано $publishedAt',
            style: TextStyle(fontSize: 11, color: foreground),
          ),
        ],
      ),
    );
  }
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

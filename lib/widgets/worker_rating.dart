import 'package:flutter/material.dart';

const workerResultLabels = {
  'success': 'Справился',
  'fail': 'Не справился',
  'excellent': 'Справился хорошо',
  'good': 'С нареканиями',
};

const workerResultDeltas = {
  'success': 1,
  'fail': -2,
  'excellent': 2,
  'good': -1,
};

String workerRatingSummary(Map<String, dynamic> worker) =>
    'Рейтинг: ${worker['rating'] ?? 0} · '
    'Успешно: ${worker['success_requests'] ?? 0} · '
    'Не справился: ${worker['fail_requests'] ?? 0}';

String workerResultEffect(String result) {
  final delta = workerResultDeltas[result]!;
  final points = '${delta > 0 ? '+' : ''}$delta';
  final counter = switch (result) {
    'success' || 'excellent' => 'Успешно: +1.',
    'fail' => 'Не справился: +1.',
    _ => 'Счетчики успешных заказов и срывов не меняются.',
  };
  return 'Рейтинг: $points. $counter';
}

class WorkerRatingRules extends StatelessWidget {
  const WorkerRatingRules({super.key});

  @override
  Widget build(BuildContext context) => const ExpansionTile(
    tilePadding: EdgeInsets.zero,
    title: Text('Как считается рейтинг'),
    shape: Border(),
    collapsedShape: Border(),
    children: [
      Padding(
        padding: EdgeInsets.only(bottom: 12),
        child: Text(
          'Рейтинг начинается с 0 и складывается из оценок логиста за заявки. '
          'Он может быть отрицательным.\n'
          'Справился хорошо: +2. Справился: +1. '
          'С нареканиями: −1. Не справился: −2.\n'
          'Положительная оценка добавляет один успешный заказ; '
          '«Не справился» учитывается отдельно и не означает автоматически неявку.\n'
          'Оценка не завершает заявку и не меняет начисления. '
          'Ее можно выставить после приемки работы. '
          'Отмена, опоздание и неявка не списывают баллы автоматически.\n'
          'Отрицательная оценка требует причины. Исправление и аннулирование '
          'сохраняют предыдущие записи. Рабочий может направить обращение.\n'
          'Клиент видит общий рейтинг, но не внутренние причины и обращения.',
        ),
      ),
    ],
  );
}


String workerRatingResultLabel(Object? result) => result == 'void'
    ? 'Оценка аннулирована'
    : workerResultLabels[result] ?? 'Оценка сохранена';

class WorkerPublicRating extends StatelessWidget {
  const WorkerPublicRating({super.key, required this.worker});
  final Map<String, dynamic> worker;

  @override
  Widget build(BuildContext context) {
    final summary = worker['rating_summary'] is Map
        ? Map<String, dynamic>.from(worker['rating_summary'] as Map)
        : <String, dynamic>{};
    if (!worker.containsKey('rating') && !summary.containsKey('rating')) {
      return const Text('Рейтинг пока недоступен');
    }
    final score = summary['rating'] ?? worker['rating'] ?? 0;
    final known = summary.containsKey('review_count');
    final count = summary['review_count'] ?? 0;
    return Text(
      'Рейтинг: $score'
      '${known ? ' · Оценок: $count' : ''}'
      '${summary['positive_percent'] != null ? ' · Положительных: ${summary['positive_percent']}%' : ''}'
      '${summary['has_legacy_balance'] == true ? ' · Есть более ранний баланс; статистика по сохраненным оценкам' : (known && count == 0 ? ' · Оценок пока нет' : '')}',
    );
  }
}

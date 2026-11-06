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
    'Срывы: ${worker['fail_requests'] ?? 0}';

String workerResultEffect(String result) {
  final delta = workerResultDeltas[result]!;
  final points = '${delta > 0 ? '+' : ''}$delta';
  final counter = switch (result) {
    'success' || 'excellent' => 'Успешно: +1.',
    'fail' => 'Срывы: +1.',
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
    children: [
      Padding(
        padding: EdgeInsets.only(bottom: 12),
        child: Text(
          'Рейтинг начинается с 0 и складывается из оценок логиста за заявки. '
          'Он может быть отрицательным.\n'
          'Справился хорошо: +2. Справился: +1. '
          'С нареканиями: −1. Не справился: −2.\n'
          'Каждая положительная оценка добавляет один успешный заказ. '
          '«Не справился» добавляет один срыв. '
          '«С нареканиями» меняет только рейтинг.\n'
          'Каждый исполнитель оценивается отдельно, один раз за заявку. '
          'После сохранения изменить оценку нельзя.',
        ),
      ),
    ],
  );
}

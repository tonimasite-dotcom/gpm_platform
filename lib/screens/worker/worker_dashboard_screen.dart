import 'package:flutter/material.dart';

import '../../theme/gpm_theme.dart';

class WorkerDashboardScreen extends StatelessWidget {
  const WorkerDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: GpmColors.surface,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: GpmColors.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'КАБИНЕТ ИСПОЛНИТЕЛЯ',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              const Text(
                'Берите доступные заявки, отслеживайте назначенные смены и контролируйте выплаты.',
              ),
              const SizedBox(height: 18),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: const [
                  _DashboardStat(label: 'Активные заявки', value: '2'),
                  _DashboardStat(label: 'Рейтинг', value: '14'),
                  _DashboardStat(label: 'Выплаты', value: '24 600 ₽'),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _DashboardStat extends StatelessWidget {
  final String label;
  final String value;

  const _DashboardStat({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 160,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF6D8),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE9CE73)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            style: const TextStyle(
              color: GpmColors.black,
              fontSize: 22,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              color: GpmColors.graphite,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

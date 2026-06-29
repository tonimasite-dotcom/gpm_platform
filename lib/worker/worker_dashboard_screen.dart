import 'package:flutter/material.dart';

class WorkerDashboardScreen extends StatelessWidget {
  const WorkerDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text(
        'Главная грузчика:\nкраткая сводка по сменам и доходу.',
        textAlign: TextAlign.center,
      ),
    );
  }
}

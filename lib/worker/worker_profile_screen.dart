import 'package:flutter/material.dart';

class WorkerProfileScreen extends StatelessWidget {
  const WorkerProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text(
        'Профиль грузчика:\nданные, рейтинг, рефералы.',
        textAlign: TextAlign.center,
      ),
    );
  }
}

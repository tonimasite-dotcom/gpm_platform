import 'package:flutter/material.dart';

class ClientProfileScreen extends StatelessWidget {
  const ClientProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text(
        'Профиль клиента:\nназвание компании, контакты, способ оплаты.\n(Пока заглушка.)',
        textAlign: TextAlign.center,
      ),
    );
  }
}

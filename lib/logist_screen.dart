import 'package:flutter/material.dart';

class LogistHomeScreen extends StatefulWidget {
  const LogistHomeScreen({super.key});

  @override
  State<LogistHomeScreen> createState() => _LogistHomeScreenState();
}

class _LogistHomeScreenState extends State<LogistHomeScreen> {
  int currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final screens = [
      const LogistOrdersScreen(),
      const LogistAnalyticsScreen(),
      const LogistProfileScreen(),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Кабинет логиста')),
      body: screens[currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: currentIndex,
        onTap: (index) => setState(() => currentIndex = index),
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.assignment), label: 'Заказы'),
          BottomNavigationBarItem(
              icon: Icon(Icons.analytics), label: 'Аналитика'),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Профиль'),
        ],
      ),
    );
  }
}

class LogistOrdersScreen extends StatelessWidget {
  const LogistOrdersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text(
        'Модерация заказов\nФильтры: Новые | В работе | Завершенные',
        textAlign: TextAlign.center,
        style: TextStyle(fontSize: 16),
      ),
    );
  }
}

class LogistAnalyticsScreen extends StatelessWidget {
  const LogistAnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text('Аналитика\n(Графики, метрики)', textAlign: TextAlign.center),
    );
  }
}

class LogistProfileScreen extends StatelessWidget {
  const LogistProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child:
          Text('Профиль логиста\n(Регион, права)', textAlign: TextAlign.center),
    );
  }
}

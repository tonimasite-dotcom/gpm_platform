import 'package:flutter/material.dart';
import '../../models/chat_models.dart';
import '../chats/chat_threads_screen.dart';
import 'worker_dashboard_screen.dart';
import 'worker_orders_screen.dart';
import 'worker_finance_screen.dart';
import 'worker_profile_screen.dart';

class WorkerHomeScreen extends StatefulWidget {
  const WorkerHomeScreen({super.key});

  @override
  State<WorkerHomeScreen> createState() => _WorkerHomeScreenState();
}

class _WorkerHomeScreenState extends State<WorkerHomeScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final screens = const [
      WorkerDashboardScreen(),
      WorkerOrdersScreen(),
      ChatThreadsScreen(role: ChatRole.worker),
      WorkerFinanceScreen(),
      WorkerProfileScreen(),
    ];

    return Scaffold(
      body: screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        type: BottomNavigationBarType.fixed,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Главная'),
          BottomNavigationBarItem(icon: Icon(Icons.list_alt), label: 'Заказы'),
          BottomNavigationBarItem(
              icon: Icon(Icons.forum_outlined), label: 'Чаты'),
          BottomNavigationBarItem(
              icon: Icon(Icons.account_balance_wallet), label: 'Финансы'),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Профиль'),
        ],
      ),
    );
  }
}

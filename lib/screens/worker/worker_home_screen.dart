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
  final Set<int> _visited = {0};

  @override
  Widget build(BuildContext context) {
    final screens = [
      WorkerDashboardScreen(
        onOpenOrders: () => setState(() => _currentIndex = 1),
      ),
      const WorkerOrdersScreen(),
      const ChatThreadsScreen(role: ChatRole.worker),
      const WorkerFinanceScreen(),
      const WorkerProfileScreen(),
    ];

    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: List.generate(
          screens.length,
          (index) => TickerMode(
            enabled: index == _currentIndex,
            child:
                (index == _currentIndex ||
                    (index == 2 && _visited.contains(index)))
                ? screens[index]
                : const SizedBox.shrink(),
          ),
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        type: BottomNavigationBarType.fixed,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
            _visited.add(index);
          });
        },
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Главная'),
          BottomNavigationBarItem(icon: Icon(Icons.list_alt), label: 'Заказы'),
          BottomNavigationBarItem(
            icon: Icon(Icons.forum_outlined),
            label: 'Чаты',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.account_balance_wallet),
            label: 'Финансы',
          ),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Профиль'),
        ],
      ),
    );
  }
}

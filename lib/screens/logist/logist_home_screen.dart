import 'package:flutter/material.dart';
import '../../widgets/gpm_bottom_navigation_bar.dart';
import '../../models/chat_models.dart';
import '../chats/chat_threads_screen.dart';
import 'logist_orders_screen.dart';
import 'logist_analytics_screen.dart';
import 'logist_profile_screen.dart';
import 'logist_workers_screen.dart';

class LogistHomeScreen extends StatefulWidget {
  const LogistHomeScreen({super.key});

  @override
  State<LogistHomeScreen> createState() => _LogistHomeScreenState();
}

class _LogistHomeScreenState extends State<LogistHomeScreen> {
  int _currentIndex = 0;
  final Set<int> _visited = {0};

  @override
  Widget build(BuildContext context) {
    final screens = const [
      LogistOrdersScreen(),
      LogistWorkersScreen(),
      ChatThreadsScreen(role: ChatRole.logist),
      LogistAnalyticsScreen(),
      LogistProfileScreen(),
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
      bottomNavigationBar: GpmBottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        selectedFontSize: 11,
        unselectedFontSize: 11,
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
            _visited.add(index);
          });
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.assignment),
            label: 'Заказы',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.people_outline),
            label: 'Исполнители',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.forum_outlined),
            label: 'Чаты',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.analytics),
            label: 'Аналитика',
          ),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Профиль'),
        ],
      ),
    );
  }
}

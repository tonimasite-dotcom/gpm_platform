import 'package:flutter/material.dart';
import '../../models/chat_models.dart';
import '../chats/chat_threads_screen.dart';
import 'logist_orders_screen.dart';
import 'logist_analytics_screen.dart';
import 'logist_profile_screen.dart';

class LogistHomeScreen extends StatefulWidget {
  const LogistHomeScreen({super.key});

  @override
  State<LogistHomeScreen> createState() => _LogistHomeScreenState();
}

class _LogistHomeScreenState extends State<LogistHomeScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final screens = const [
      LogistOrdersScreen(),
      ChatThreadsScreen(role: ChatRole.logist),
      LogistAnalyticsScreen(),
      LogistProfileScreen(),
    ];

    return Scaffold(
      body: screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.assignment), label: 'Заказы'),
          BottomNavigationBarItem(
              icon: Icon(Icons.forum_outlined), label: 'Чаты'),
          BottomNavigationBarItem(
              icon: Icon(Icons.analytics), label: 'Аналитика'),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Профиль'),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';
import '../../models/chat_models.dart';
import '../chats/chat_threads_screen.dart';
import 'client_orders_screen.dart';
import 'client_create_order_screen.dart';
import 'client_profile_screen.dart';

class ClientHomeScreen extends StatefulWidget {
  const ClientHomeScreen({super.key});

  @override
  State<ClientHomeScreen> createState() => _ClientHomeScreenState();
}

class _ClientHomeScreenState extends State<ClientHomeScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final screens = [
      const ClientOrdersScreen(),
      ClientCreateOrderScreen(
        publishImmediately: true,
        onBack: () => setState(() => _currentIndex = 0),
      ),
      const ChatThreadsScreen(role: ChatRole.client),
      const ClientProfileScreen(),
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
          BottomNavigationBarItem(
            icon: Icon(Icons.list_alt),
            label: 'Мои заказы',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.add_circle_outline),
            label: 'Создать заказ',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.forum_outlined),
            label: 'Чаты',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person),
            label: 'Профиль',
          ),
        ],
      ),
    );
  }
}

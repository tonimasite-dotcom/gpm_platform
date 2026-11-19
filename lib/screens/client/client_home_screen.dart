import 'package:flutter/material.dart';
import '../../widgets/gpm_bottom_navigation_bar.dart';
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
  final Set<int> _visited = {0};

  @override
  Widget build(BuildContext context) {
    final screens = [
      const ClientOrdersScreen(),
      ClientCreateOrderScreen(
        publishImmediately: false,
        submitText: 'Создать черновик',
        onBack: () => setState(() => _currentIndex = 0),
      ),
      const ChatThreadsScreen(role: ChatRole.client),
      const ClientProfileScreen(),
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
        currentIndex: _currentIndex,
        type: BottomNavigationBarType.fixed,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
            _visited.add(index);
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
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Профиль'),
        ],
      ),
    );
  }
}

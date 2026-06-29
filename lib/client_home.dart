import 'package:flutter/material.dart';

class ClientHomeScreen extends StatefulWidget {
  const ClientHomeScreen({super.key});

  @override
  State<ClientHomeScreen> createState() => _ClientHomeScreenState();
}

class _ClientHomeScreenState extends State<ClientHomeScreen> {
  int selectedIndex = 0;

  final List<Widget> screens = const [
    ClientOrdersTab(),
    ClientCreateOrderTab(),
    ClientProfileTab(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Кабинет клиента')),
      body: screens[selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: selectedIndex,
        onTap: (index) => setState(() => selectedIndex = index),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.list), label: 'Заказы'),
          BottomNavigationBarItem(
              icon: Icon(Icons.add_circle), label: 'Создать'),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Профиль'),
        ],
      ),
    );
  }
}

class ClientOrdersTab extends StatelessWidget {
  const ClientOrdersTab({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(child: Text('Список заказов'));
  }
}

class ClientCreateOrderTab extends StatelessWidget {
  const ClientCreateOrderTab({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(child: Text('Форма создания заказа'));
  }
}

class ClientProfileTab extends StatelessWidget {
  const ClientProfileTab({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(child: Text('Профиль клиента'));
  }
}

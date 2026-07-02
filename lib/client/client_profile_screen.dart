import 'package:flutter/material.dart';
import '../main.dart' show supabase;

class ClientProfileScreen extends StatelessWidget {
  const ClientProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          const SizedBox(height: 20),

          // Аватар
          const CircleAvatar(
            radius: 50,
            backgroundColor: Color(0xFF5B4FFF),
            child: Icon(Icons.person, size: 50, color: Colors.white),
          ),
          const SizedBox(height: 16),

          // Имя (mock-данные)
          const Text(
            'Администратор (dev)',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            'admin@gpm-platform.ru',
            style: TextStyle(fontSize: 14, color: Colors.grey[600]),
          ),
          const SizedBox(height: 32),

          // Карточки со статистикой
          FutureBuilder<int>(
            future: _getOrdersCount(),
            builder: (context, snapshot) {
              final count = snapshot.data ?? 0;
              return _StatCard(
                icon: Icons.assignment,
                title: 'Всего заказов',
                value: count.toString(),
                color: Colors.blue,
              );
            },
          ),
          const SizedBox(height: 12),
          const _StatCard(
            icon: Icons.calendar_today,
            title: 'Аккаунт создан',
            value: '13.01.2026',
            color: Colors.green,
          ),
          const SizedBox(height: 32),

          // Кнопки действий
          ListTile(
            leading: const Icon(Icons.settings),
            title: const Text('Настройки'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Раздел в разработке')),
              );
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.help_outline),
            title: const Text('Помощь'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Раздел в разработке')),
              );
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout, color: Colors.red),
            title: const Text('Выйти', style: TextStyle(color: Colors.red)),
            onTap: () {
              Navigator.of(context)
                  .pushNamedAndRemoveUntil('/', (route) => false);
            },
          ),
        ],
      ),
    );
  }

  // ✅ Простой подсчет через length списка
  Future<int> _getOrdersCount() async {
    try {
      final data = await supabase.from('orders').select('id').execute();
      return (data as List).length;
    } catch (e) {
      debugPrint('Ошибка подсчета заказов: $e');
      return 0;
    }
  }
}

// Виджет карточки статистики
class _StatCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;
  final Color color;

  const _StatCard({
    required this.icon,
    required this.title,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, size: 40, color: color),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(fontSize: 14, color: Colors.grey[600]),
              ),
              const SizedBox(height: 4),
              Text(
                value,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

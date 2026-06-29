import 'package:flutter/material.dart';
import '../../models/worker_transaction.dart';

class WorkerFinanceScreen extends StatelessWidget {
  const WorkerFinanceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    const balance = '45 000 ₽';
    const monthChange = '+18%';

    final transactions = <WorkerTransaction>[
      const WorkerTransaction(
        id: '17144/25',
        title: 'Выгрузка сувенирной продукции',
        date: 'Сегодня, 10:30',
        amount: '+1 550 ₽',
        isIncome: true,
      ),
      const WorkerTransaction(
        id: '17212/25',
        title: 'Разгрузить 2 авто с техникой',
        date: 'Вчера, 19:10',
        amount: '+2 100 ₽',
        isIncome: true,
      ),
      const WorkerTransaction(
        id: 'W001',
        title: 'Выплата на карту',
        date: '12 мая, 19:10',
        amount: '-12 500 ₽',
        isIncome: false,
      ),
    ];

    return Column(
      children: [
        Container(
          width: double.infinity,
          margin: const EdgeInsets.all(16),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: const LinearGradient(
              colors: [Color(0xFF5B4FFF), Color(0xFF8A7FFF)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.1),
                blurRadius: 8,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Доход за декабрь',
                    style: TextStyle(fontSize: 14, color: Colors.white70),
                  ),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.trending_up,
                            size: 14, color: Colors.greenAccent),
                        SizedBox(width: 4),
                        Text(
                          monthChange,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.greenAccent,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                balance,
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'Доступно к выводу',
                style: TextStyle(fontSize: 13, color: Colors.white70),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton.tonal(
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: const Color(0xFF5B4FFF),
                  ),
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                          content: Text('Запрос выплаты пока демо.')),
                    );
                  },
                  child: const Text('Вывести деньги'),
                ),
              ),
            ],
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'История операций',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: transactions.length,
            itemBuilder: (context, index) {
              final t = transactions[index];
              final color = t.isIncome ? Colors.green : Colors.red;

              return Card(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: t.isIncome
                        ? Colors.green.withValues(alpha: 0.1)
                        : Colors.red.withValues(alpha: 0.1),
                    child: Icon(
                      t.isIncome ? Icons.arrow_downward : Icons.arrow_upward,
                      color: t.isIncome ? Colors.green : Colors.red,
                      size: 18,
                    ),
                  ),
                  title: Text(
                    t.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(t.date),
                  trailing: Text(
                    t.amount,
                    style: TextStyle(
                      color: color,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  onTap: () {},
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

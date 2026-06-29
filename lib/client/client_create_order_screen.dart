import 'package:flutter/material.dart';
import '../main.dart' show supabase;

class ClientCreateOrderScreen extends StatefulWidget {
  const ClientCreateOrderScreen({super.key});

  @override
  State<ClientCreateOrderScreen> createState() =>
      _ClientCreateOrderScreenState();
}

class _ClientCreateOrderScreenState extends State<ClientCreateOrderScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _addressController = TextEditingController();
  final _descriptionController = TextEditingController();

  DateTime? selectedDate;
  TimeOfDay? selectedTime;
  int workersCount = 2;
  int hours = 4;
  bool isSubmitting = false;

  @override
  void dispose() {
    _titleController.dispose();
    _addressController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 90)),
    );

    if (date != null) {
      setState(() => selectedDate = date);
    }
  }

  Future<void> _pickTime() async {
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );

    if (time != null) {
      setState(() => selectedTime = time);
    }
  }

  Future<void> _submitOrder() async {
    if (!_formKey.currentState!.validate()) return;

    if (selectedDate == null || selectedTime == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Выберите дату и время')),
      );
      return;
    }

    setState(() => isSubmitting = true);

    try {
      // Формируем DateTime для отправки
      final orderDateTime = DateTime(
        selectedDate!.year,
        selectedDate!.month,
        selectedDate!.day,
        selectedTime!.hour,
        selectedTime!.minute,
      );

      // Вставка в Supabase
      await supabase.from('orders').insert({
        'title': _titleController.text.trim(),
        'description': _descriptionController.text.trim(),
        'address': _addressController.text.trim(),
        'workers_count': workersCount,
        'hours': hours,
        'datetime': orderDateTime.toIso8601String(),
        'status': 'На модерации',
      });

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('✅ Заказ успешно создан!'),
          backgroundColor: Colors.green,
        ),
      );

      // Очистка формы
      _titleController.clear();
      _addressController.clear();
      _descriptionController.clear();
      setState(() {
        selectedDate = null;
        selectedTime = null;
        workersCount = 2;
        hours = 4;
      });
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Ошибка создания заказа: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => isSubmitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Создание заказа',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),

            // Название заказа
            TextFormField(
              controller: _titleController,
              decoration: const InputDecoration(
                labelText: 'Название заказа',
                hintText: 'Например: Разгрузка контейнера',
                border: OutlineInputBorder(),
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Введите название';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),

            // Адрес
            TextFormField(
              controller: _addressController,
              decoration: const InputDecoration(
                labelText: 'Адрес',
                prefixIcon: Icon(Icons.location_on),
                border: OutlineInputBorder(),
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Введите адрес';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),

            // Дата и время
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickDate,
                    icon: const Icon(Icons.calendar_today),
                    label: Text(
                      selectedDate == null
                          ? 'Выбрать дату'
                          : '${selectedDate!.day}.${selectedDate!.month}.${selectedDate!.year}',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickTime,
                    icon: const Icon(Icons.access_time),
                    label: Text(
                      selectedTime == null
                          ? 'Время'
                          : '${selectedTime!.hour}:${selectedTime!.minute.toString().padLeft(2, '0')}',
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Количество грузчиков
            Row(
              children: [
                const Text('👷 Грузчиков:'),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: () {
                    if (workersCount > 1) {
                      setState(() => workersCount--);
                    }
                  },
                  icon: const Icon(Icons.remove_circle_outline),
                ),
                Text('$workersCount', style: const TextStyle(fontSize: 18)),
                IconButton(
                  onPressed: () => setState(() => workersCount++),
                  icon: const Icon(Icons.add_circle_outline),
                ),
                const Spacer(),
                const Text('⏱️ Часов:'),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: () {
                    if (hours > 1) {
                      setState(() => hours--);
                    }
                  },
                  icon: const Icon(Icons.remove_circle_outline),
                ),
                Text('$hours', style: const TextStyle(fontSize: 18)),
                IconButton(
                  onPressed: () => setState(() => hours++),
                  icon: const Icon(Icons.add_circle_outline),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Описание
            TextFormField(
              controller: _descriptionController,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Описание работ',
                hintText: 'Опишите детали: что грузить, с какого этажа и т.д.',
                border: OutlineInputBorder(),
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Добавьте описание';
                }
                return null;
              },
            ),
            const SizedBox(height: 24),

            // Кнопка отправки
            SizedBox(
              height: 50,
              child: ElevatedButton(
                onPressed: isSubmitting ? null : _submitOrder,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF5B4FFF),
                  foregroundColor: Colors.white,
                ),
                child: isSubmitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text(
                        'Создать заказ',
                        style: TextStyle(fontSize: 16),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

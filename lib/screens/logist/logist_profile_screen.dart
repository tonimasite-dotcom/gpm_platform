import 'dart:convert';

import 'package:flutter/material.dart';

import '../../services/demo_storage.dart';
import '../../theme/gpm_theme.dart';

class LogistProfileScreen extends StatefulWidget {
  const LogistProfileScreen({super.key});

  @override
  State<LogistProfileScreen> createState() => _LogistProfileScreenState();
}

class _LogistProfileScreenState extends State<LogistProfileScreen> {
  static const _storageKey = 'gpm.logist.profile.v1';

  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController(text: 'Демо Логист');
  final _phoneController = TextEditingController();
  final _emailController = TextEditingController(text: 'logist@gpm.ru');
  final _telegramController = TextEditingController();
  final _cityController = TextEditingController(text: 'Москва');
  final _maxOrdersController = TextEditingController(text: '25');
  final _commentController = TextEditingController();

  String _department = 'operations';
  String _accessLevel = 'standard';
  bool _canPublishOrders = true;
  bool _canApproveWorkers = true;
  bool _notifyNewOrders = true;
  bool _profileLoaded = false;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _telegramController.dispose();
    _cityController.dispose();
    _maxOrdersController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  void _loadProfile() {
    final raw = readDemoValue(_storageKey);
    if (raw != null) {
      final data = jsonDecode(raw) as Map<String, dynamic>;
      _department = data['department']?.toString() ?? _department;
      _accessLevel = data['access_level']?.toString() ?? _accessLevel;
      _canPublishOrders = data['can_publish_orders'] != false;
      _canApproveWorkers = data['can_approve_workers'] != false;
      _notifyNewOrders = data['notify_new_orders'] != false;
      _nameController.text = data['name']?.toString() ?? _nameController.text;
      _phoneController.text = data['phone']?.toString() ?? '';
      _emailController.text = data['email']?.toString() ?? _emailController.text;
      _telegramController.text = data['telegram']?.toString() ?? '';
      _cityController.text = data['cities']?.toString() ?? _cityController.text;
      _maxOrdersController.text =
          data['max_orders']?.toString() ?? _maxOrdersController.text;
      _commentController.text = data['comment']?.toString() ?? '';
    }
    setState(() => _profileLoaded = true);
  }

  void _saveProfile() {
    if (!_formKey.currentState!.validate()) return;

    writeDemoValue(
      _storageKey,
      jsonEncode({
        'department': _department,
        'access_level': _accessLevel,
        'can_publish_orders': _canPublishOrders,
        'can_approve_workers': _canApproveWorkers,
        'notify_new_orders': _notifyNewOrders,
        'name': _nameController.text.trim(),
        'phone': _phoneController.text.trim(),
        'email': _emailController.text.trim(),
        'telegram': _telegramController.text.trim(),
        'cities': _cityController.text.trim(),
        'max_orders': int.tryParse(_maxOrdersController.text.trim()),
        'comment': _commentController.text.trim(),
        'updated_at': DateTime.now().toUtc().toIso8601String(),
      }),
    );

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Профиль логиста сохранен')),
    );
  }

  String? _required(String? value, String message) {
    return value == null || value.trim().isEmpty ? message : null;
  }

  String? _positiveInt(String? value) {
    final parsed = int.tryParse(value?.trim() ?? '');
    return parsed == null || parsed <= 0 ? 'Укажите число больше 0' : null;
  }

  @override
  Widget build(BuildContext context) {
    if (!_profileLoaded) {
      return const Center(child: CircularProgressIndicator());
    }

    return Material(
      color: Colors.transparent,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ProfileHeader(
                icon: Icons.support_agent,
                title: 'Кабинет логиста',
                subtitle: 'Контакты, зона ответственности и права доступа',
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'ФИО',
                  border: OutlineInputBorder(),
                ),
                validator: (value) => _required(value, 'Укажите ФИО'),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _phoneController,
                      keyboardType: TextInputType.phone,
                      decoration: const InputDecoration(
                        labelText: 'Телефон',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextFormField(
                      controller: _telegramController,
                      decoration: const InputDecoration(
                        labelText: 'Telegram',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _emailController,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                  labelText: 'Email',
                  border: OutlineInputBorder(),
                ),
                validator: (value) => _required(value, 'Укажите email'),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _department,
                decoration: const InputDecoration(
                  labelText: 'Отдел',
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(
                    value: 'operations',
                    child: Text('Операционный отдел'),
                  ),
                  DropdownMenuItem(
                    value: 'key_accounts',
                    child: Text('Ключевые клиенты'),
                  ),
                  DropdownMenuItem(
                    value: 'quality',
                    child: Text('Контроль качества'),
                  ),
                ],
                onChanged: (value) {
                  if (value == null) return;
                  setState(() => _department = value);
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _cityController,
                decoration: const InputDecoration(
                  labelText: 'Города и районы',
                  hintText: 'Например: Москва, Химки, Красногорск',
                  border: OutlineInputBorder(),
                ),
                validator: (value) => _required(value, 'Укажите зону работы'),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _maxOrdersController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Лимит активных заявок',
                  border: OutlineInputBorder(),
                ),
                validator: _positiveInt,
              ),
              const SizedBox(height: 16),
              const Text(
                'Уровень доступа',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'standard', label: Text('Стандарт')),
                  ButtonSegment(value: 'senior', label: Text('Старший')),
                  ButtonSegment(value: 'admin', label: Text('Админ')),
                ],
                selected: {_accessLevel},
                onSelectionChanged: (selection) {
                  setState(() => _accessLevel = selection.first);
                },
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Может публиковать заявки'),
                value: _canPublishOrders,
                onChanged: (value) {
                  setState(() => _canPublishOrders = value);
                },
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Может согласовывать исполнителей'),
                value: _canApproveWorkers,
                onChanged: (value) {
                  setState(() => _canApproveWorkers = value);
                },
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Уведомлять о новых заявках'),
                value: _notifyNewOrders,
                onChanged: (value) {
                  setState(() => _notifyNewOrders = value);
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _commentController,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Внутренняя заметка',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: _saveProfile,
                icon: const Icon(Icons.save_outlined),
                label: const Text('Сохранить профиль'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  const _ProfileHeader({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            CircleAvatar(
              backgroundColor: GpmColors.red,
              foregroundColor: Colors.white,
              child: Icon(icon),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 4),
                  Text(subtitle),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

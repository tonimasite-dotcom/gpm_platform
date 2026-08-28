import 'dart:convert';

import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
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
  final _cityController = TextEditingController(text: 'Москва');
  final _maxOrdersController = TextEditingController(text: '25');
  final _commentController = TextEditingController();

  String _department = 'operations';
  String _accessLevel = 'standard';
  bool _canPublishOrders = true;
  bool _canApproveWorkers = true;
  bool _notifyNewOrders = true;
  bool _profileLoaded = false;
  bool _verificationLoading = false;
  List<Map<String, dynamic>> _verificationQueue = [];
  final Set<String> _reviewingSubmissions = {};

  @override
  void initState() {
    super.initState();
    _loadProfile();
    _loadVerifications();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _cityController.dispose();
    _maxOrdersController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    try {
      Map<String, dynamic> data = {};
      if (gpmApi.isApiMode) {
        data = await gpmApi.getMyProfile();
      } else {
        final raw = readDemoValue(_storageKey);
        if (raw != null) {
          data = jsonDecode(raw) as Map<String, dynamic>;
        }
      }
      _department = data['department']?.toString() ?? _department;
      _accessLevel = data['access_level']?.toString() ?? _accessLevel;
      _canPublishOrders = data['can_publish_orders'] != false;
      _canApproveWorkers = data['can_approve_workers'] != false;
      _notifyNewOrders = data['notify_new_orders'] != false;
      _nameController.text =
          data['display_name']?.toString() ??
          data['name']?.toString() ??
          _nameController.text;
      _phoneController.text = data['phone']?.toString() ?? '';
      _emailController.text =
          data['email']?.toString() ?? _emailController.text;
      final cities = data['cities'];
      _cityController.text = cities is List
          ? cities.join(', ')
          : cities?.toString() ?? _cityController.text;
      _maxOrdersController.text =
          data['max_orders']?.toString() ?? _maxOrdersController.text;
      _commentController.text = data['comment']?.toString() ?? '';
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Не удалось загрузить профиль логиста'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
    if (mounted) setState(() => _profileLoaded = true);
  }

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;

    final data = <String, dynamic>{
      'department': _department,
      'notify_new_orders': _notifyNewOrders,
      'display_name': _nameController.text.trim(),
      'phone': _phoneController.text.trim(),
      'email': _emailController.text.trim(),
      'cities': _cityController.text
          .split(',')
          .map((item) => item.trim())
          .where((item) => item.isNotEmpty)
          .toList(),
      'max_orders': int.tryParse(_maxOrdersController.text.trim()),
    };
    try {
      if (gpmApi.isApiMode) {
        await gpmApi.updateMyProfile(data);
      } else {
        writeDemoValue(
          _storageKey,
          jsonEncode({
            ...data,
            'name': data['display_name'],
            'cities': _cityController.text.trim(),
            'access_level': _accessLevel,
            'can_publish_orders': _canPublishOrders,
            'can_approve_workers': _canApproveWorkers,
            'comment': _commentController.text.trim(),
          }),
        );
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Профиль логиста сохранён'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Не удалось сохранить профиль логиста'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _loadVerifications() async {
    if (!gpmApi.isApiMode) return;
    setState(() => _verificationLoading = true);
    try {
      final queue = await gpmApi.getWorkerVerificationQueue();
      if (mounted) setState(() => _verificationQueue = queue);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Не удалось загрузить очередь модерации'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _verificationLoading = false);
    }
  }

  Future<void> _reviewVerification(
    Map<String, dynamic> submission, {
    required bool approved,
  }) async {
    var reason = '';
    if (!approved) {
      final controller = TextEditingController();
      final result = await showDialog<String>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Отклонить заявку'),
          content: TextField(
            controller: controller,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Причина для исполнителя',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Отмена'),
            ),
            FilledButton(
              onPressed: () {
                if (controller.text.trim().isNotEmpty) {
                  Navigator.of(dialogContext).pop(controller.text.trim());
                }
              },
              child: const Text('Отклонить'),
            ),
          ],
        ),
      );
      controller.dispose();
      if (result == null) return;
      reason = result;
    }
    final submissionId = submission['submission_id']?.toString() ?? '';
    setState(() => _reviewingSubmissions.add(submissionId));
    try {
      await gpmApi.reviewWorkerVerification(
        submissionId: submissionId,
        approved: approved,
        rejectionReason: reason,
      );
      await _loadVerifications();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(approved ? 'Заявка подтверждена' : 'Заявка отклонена'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Не удалось обработать заявку'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _reviewingSubmissions.remove(submissionId));
    }
  }

  Future<void> _showAttachment(Map<String, dynamic> submission) async {
    final submissionId = submission['submission_id']?.toString() ?? '';
    try {
      final bytes = await gpmApi.downloadWorkerVerificationAttachment(
        submissionId,
      );
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Вложение к заявке'),
          content: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760, maxHeight: 620),
            child: InteractiveViewer(child: Image.memory(bytes)),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Закрыть'),
            ),
          ],
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Не удалось загрузить вложение'),
          backgroundColor: Colors.red,
        ),
      );
    }
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
              if (gpmApi.isApiMode) ...[
                _ModerationSection(
                  submissions: _verificationQueue,
                  loading: _verificationLoading,
                  reviewing: _reviewingSubmissions,
                  onRefresh: _loadVerifications,
                  onAttachment: _showAttachment,
                  onApprove: (submission) =>
                      _reviewVerification(submission, approved: true),
                  onReject: (submission) =>
                      _reviewVerification(submission, approved: false),
                ),
                const SizedBox(height: 16),
              ],
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'ФИО',
                  border: OutlineInputBorder(),
                ),
                validator: (value) => _required(value, 'Укажите ФИО'),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: 'Телефон',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _emailController,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                  labelText: 'Email',
                  border: OutlineInputBorder(),
                ),
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
                onSelectionChanged: gpmApi.isApiMode
                    ? null
                    : (selection) {
                        setState(() => _accessLevel = selection.first);
                      },
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Может публиковать заявки'),
                value: _canPublishOrders,
                onChanged: gpmApi.isApiMode
                    ? null
                    : (value) {
                        setState(() => _canPublishOrders = value);
                      },
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Может согласовывать исполнителей'),
                value: _canApproveWorkers,
                onChanged: gpmApi.isApiMode
                    ? null
                    : (value) {
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
              if (!gpmApi.isApiMode) ...[
                const SizedBox(height: 12),
                TextFormField(
                  controller: _commentController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Внутренняя заметка',
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
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

class _ModerationSection extends StatelessWidget {
  final List<Map<String, dynamic>> submissions;
  final bool loading;
  final Set<String> reviewing;
  final Future<void> Function() onRefresh;
  final Future<void> Function(Map<String, dynamic>) onAttachment;
  final Future<void> Function(Map<String, dynamic>) onApprove;
  final Future<void> Function(Map<String, dynamic>) onReject;

  const _ModerationSection({
    required this.submissions,
    required this.loading,
    required this.reviewing,
    required this.onRefresh,
    required this.onAttachment,
    required this.onApprove,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const CircleAvatar(
                backgroundColor: GpmColors.red,
                foregroundColor: Colors.white,
                child: Icon(Icons.verified_user_outlined),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Модерация исполнителей',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 3),
                    Text('Заявок на проверке: ${submissions.length}'),
                  ],
                ),
              ),
              IconButton(
                onPressed: loading ? null : onRefresh,
                tooltip: 'Обновить',
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (loading)
            const Center(child: CircularProgressIndicator())
          else if (submissions.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Новых заявок на модерацию нет.'),
            )
          else
            for (var index = 0; index < submissions.length; index++) ...[
              _ModerationCard(
                submission: submissions[index],
                busy: reviewing.contains(
                  submissions[index]['submission_id']?.toString() ?? '',
                ),
                onAttachment: () => onAttachment(submissions[index]),
                onApprove: () => onApprove(submissions[index]),
                onReject: () => onReject(submissions[index]),
              ),
              if (index != submissions.length - 1) const SizedBox(height: 12),
            ],
        ],
      ),
    );
  }
}

class _ModerationCard extends StatelessWidget {
  final Map<String, dynamic> submission;
  final bool busy;
  final VoidCallback onAttachment;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  const _ModerationCard({
    required this.submission,
    required this.busy,
    required this.onAttachment,
    required this.onApprove,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    final type = submission['verification_type']?.toString() ?? '';
    final rawData = submission['data'];
    final data = rawData is Map
        ? rawData.map((key, value) => MapEntry(key.toString(), value))
        : <String, dynamic>{};
    final fields = type == 'identity'
        ? <(String, String)>[
            ('ФИО', data['full_name']?.toString() ?? ''),
            (
              'Серия и номер',
              '${data['passport_series'] ?? ''} ${data['passport_number'] ?? ''}',
            ),
            ('Дата выдачи', data['issued_at']?.toString() ?? ''),
            ('Код подразделения', data['department_code']?.toString() ?? ''),
            ('Кем выдан', data['issued_by']?.toString() ?? ''),
          ]
        : <(String, String)>[('ИНН', data['inn']?.toString() ?? '')];
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            type == 'identity' ? 'Паспортные данные' : 'Самозанятость / НПД',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(submission['worker_name']?.toString() ?? 'Исполнитель'),
          const SizedBox(height: 10),
          for (final field in fields)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 150,
                    child: Text(
                      field.$1,
                      style: const TextStyle(color: GpmColors.graphite),
                    ),
                  ),
                  Expanded(child: SelectableText(field.$2)),
                ],
              ),
            ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (submission['has_attachment'] == true)
                OutlinedButton.icon(
                  onPressed: busy ? null : onAttachment,
                  icon: const Icon(Icons.image_outlined),
                  label: const Text('Открыть фото'),
                ),
              OutlinedButton.icon(
                onPressed: busy ? null : onReject,
                icon: const Icon(Icons.close),
                label: const Text('Отклонить'),
              ),
              FilledButton.icon(
                onPressed: busy ? null : onApprove,
                icon: const Icon(Icons.check),
                label: const Text('Подтвердить'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

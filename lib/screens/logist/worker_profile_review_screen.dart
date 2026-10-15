import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;

class WorkerProfileReviewScreen extends StatefulWidget {
  final String workerId;

  const WorkerProfileReviewScreen({super.key, required this.workerId});

  @override
  State<WorkerProfileReviewScreen> createState() =>
      _WorkerProfileReviewScreenState();
}

class _WorkerProfileReviewScreenState extends State<WorkerProfileReviewScreen> {
  Map<String, dynamic>? _profile;
  String? _error;
  bool _saving = false;
  String _employment = 'contract';
  bool? _nationality;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final profile = await gpmApi.getWorkerProfile(widget.workerId);
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _nationality = profile?['nationality'] as bool?;
        _employment = profile?['employment_type'] == 'state'
            ? 'state'
            : 'contract';
      });
    } catch (_) {
      if (mounted) setState(() => _error = 'Не удалось загрузить профиль');
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await gpmApi.updateWorkerStaffProfile(widget.workerId, {
        'employment_type': _employment,
        if (_nationality != null) 'nationality': _nationality,
      });
      if (mounted) Navigator.pop(context, true);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Не удалось сохранить профиль')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = _profile;
    return Scaffold(
      appBar: AppBar(title: const Text('Профиль исполнителя')),
      body: _error != null
          ? Center(child: Text(_error!))
          : profile == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  profile['display_name']?.toString() ??
                      profile['full_name']?.toString() ??
                      'Исполнитель',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                Text(profile['phone_number']?.toString() ?? ''),
                const SizedBox(height: 12),
                DropdownButtonFormField<bool>(
                  initialValue: _nationality,
                  decoration: const InputDecoration(labelText: 'Гражданство'),
                  hint: const Text('Не указано'),
                  items: const [
                    DropdownMenuItem(value: true, child: Text('РФ')),
                    DropdownMenuItem(value: false, child: Text('Не РФ')),
                  ],
                  onChanged: _saving
                      ? null
                      : (value) => setState(() => _nationality = value),
                ),
                const SizedBox(height: 12),
                Text(
                  profile['identity_status'] == 'verified'
                      ? 'Паспорт подтвержден'
                      : 'Паспорт не подтвержден',
                ),
                if (_nationality != null &&
                    _nationality != profile['nationality']) ...[
                  const SizedBox(height: 6),
                  const Text(
                    'После изменения гражданства потребуется повторное подтверждение паспорта.',
                  ),
                ],
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: _employment,
                  decoration: const InputDecoration(labelText: 'Тип занятости'),
                  items: const [
                    DropdownMenuItem(
                      value: 'contract',
                      child: Text('Подрядчик'),
                    ),
                    DropdownMenuItem(
                      value: 'state',
                      child: Text('Штатный исполнитель'),
                    ),
                  ],
                  onChanged: _saving
                      ? null
                      : (value) => setState(() => _employment = value!),
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: _saving ? null : _save,
                  child: Text(_saving ? 'Сохранение…' : 'Сохранить'),
                ),
              ],
            ),
    );
  }
}

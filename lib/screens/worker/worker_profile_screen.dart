import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../main.dart' show bitrix24;
import '../../services/bitrix24_service.dart';

class WorkerProfileScreen extends StatefulWidget {
  const WorkerProfileScreen({super.key});

  @override
  State<WorkerProfileScreen> createState() => _WorkerProfileScreenState();
}

class _WorkerProfileScreenState extends State<WorkerProfileScreen> {
  late Future<Map<String, dynamic>?> _profileFuture;

  @override
  void initState() {
    super.initState();
    _profileFuture = _loadProfile();
  }

  Future<Map<String, dynamic>?> _loadProfile() {
    return bitrix24.getWorkerProfile(Bitrix24Service.demoWorkerId);
  }

  Future<void> _updateProfile(
    Map<String, dynamic> currentProfile,
    Map<String, dynamic> data,
  ) async {
    try {
      final updatedProfile = Map<String, dynamic>.from(currentProfile)
        ..addAll(data);
      final priorityGroup = _calculatePriorityGroup(updatedProfile);
      updatedProfile['priority_group'] = priorityGroup;
      updatedProfile['priority_label'] = _priorityGroupLabel(priorityGroup);

      if (!mounted) return;
      setState(() {
        _profileFuture = Future.value(updatedProfile);
      });
      await bitrix24.updateWorkerProfile(Bitrix24Service.demoWorkerId, data);
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Не удалось обновить профиль: $error'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  int _calculatePriorityGroup(Map<String, dynamic> worker) {
    if (worker['employment_type'] == 'state') return 1;

    final isRussian = worker['nationality'] == true;
    final hasPassport = worker['passport']?.toString().isNotEmpty ?? false;
    final hasInn = worker['inn']?.toString().isNotEmpty ?? false;

    if (isRussian && hasPassport && hasInn) return 2;
    if (isRussian && hasInn) return 3;
    if (hasInn && hasPassport) return 4;
    if (hasInn) return 5;
    if (isRussian && hasPassport) return 6;
    if (hasPassport) return 7;
    if (isRussian) return 8;
    return 0;
  }

  String _priorityGroupLabel(int group) {
    switch (group) {
      case 1:
        return 'Штатный';
      case 2:
        return 'РФ, паспорт, самозанятый';
      case 3:
        return 'РФ, самозанятый';
      case 4:
        return 'Паспорт, самозанятый';
      case 5:
        return 'Самозанятый';
      case 6:
        return 'РФ, паспорт';
      case 7:
        return 'Паспорт';
      case 8:
        return 'РФ';
      default:
        return 'Остальные';
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>?>(
      future: _profileFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        final profile = snapshot.data;
        if (profile == null) {
          return const Center(child: Text('Профиль не найден'));
        }

        final tools = profile['tools'] is Map
            ? Map<String, dynamic>.from(profile['tools'])
            : <String, dynamic>{};
        final hasPassport = profile['passport']?.toString().isNotEmpty == true;
        final hasInn = profile['inn']?.toString().isNotEmpty == true;
        final isState = profile['employment_type'] == 'state';
        final priorityGroup = profile['priority_group'] is int
            ? profile['priority_group'] as int
            : 0;

        return RefreshIndicator(
          onRefresh: () async {
            setState(() {
              _profileFuture = _loadProfile();
            });
          },
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Row(
                children: [
                  const CircleAvatar(
                    radius: 32,
                    backgroundColor: Color(0xFF5B4FFF),
                    child:
                        Icon(Icons.engineering, color: Colors.white, size: 32),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          profile['full_name'] ?? 'Исполнитель',
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(profile['telegram'] ?? ''),
                        const SizedBox(height: 8),
                        _StatusPill(
                          text:
                              'Группа $priorityGroup: ${profile['priority_label'] ?? 'Остальные'}',
                          color: _priorityColor(priorityGroup),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _Section(
                title: 'Основные данные',
                children: [
                  _InfoRow('Телефон', profile['phone_number']),
                  _InfoRow('Дата рождения', profile['date_birth']),
                  _InfoRow(
                    'Гражданство РФ',
                    profile['nationality'] == true ? 'Да' : 'Нет',
                  ),
                  _InfoRow(
                    'Города',
                    (profile['cities'] as List?)?.join(', ') ?? '',
                  ),
                  _InfoRow(
                    'Тип занятости',
                    isState ? 'Штатный' : 'Подрядчик',
                  ),
                  const SizedBox(height: 8),
                  _WorkerAddressFields(
                    profile: profile,
                    onSave: (data) => _updateProfile(profile, data),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _Section(
                title: 'Выплаты',
                children: [
                  _WorkerPayoutFields(
                    key: ValueKey(hasInn),
                    profile: profile,
                    isSelfEmployed: hasInn,
                    onSave: (data) => _updateProfile(profile, data),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _Section(
                title: 'Проверки',
                children: [
                  _CheckRow(
                    title: 'Паспортные данные',
                    value: hasPassport ? profile['passport'] : 'Не подтвержден',
                    isOk: hasPassport,
                  ),
                  _CheckRow(
                    title: 'Самозанятость / ИНН',
                    value: hasInn ? profile['inn'] : 'Не подтверждена',
                    isOk: hasInn,
                  ),
                  _CheckRow(
                    title: 'Такелажные ремни',
                    value: tools['straps'] == true ? 'Есть' : 'Нет',
                    isOk: tools['straps'] == true,
                  ),
                  _CheckRow(
                    title: 'Инструменты',
                    value: tools['tools'] == true ? 'Есть' : 'Нет',
                    isOk: tools['tools'] == true,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _MetricCard(
                      label: 'Рейтинг',
                      value: profile['rating'].toString(),
                      color: Colors.blue,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MetricCard(
                      label: 'Успешно',
                      value: profile['success_requests'].toString(),
                      color: Colors.green,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MetricCard(
                      label: 'Срывы',
                      value: profile['fail_requests'].toString(),
                      color: Colors.red,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _Section(
                title: 'Dev действия',
                children: [
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Паспорт подтвержден'),
                    value: hasPassport,
                    onChanged: (value) => _updateProfile(profile, {
                      'passport': value ? '4512 345678' : '',
                    }),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Самозанятость подтверждена'),
                    value: hasInn,
                    onChanged: (value) => _updateProfile(profile, {
                      'inn': value ? '772812345678' : '',
                    }),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Штатный исполнитель'),
                    value: isState,
                    onChanged: (value) => _updateProfile(profile, {
                      'employment_type': value ? 'state' : 'contract',
                    }),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      isState
                          ? 'Штатный исполнитель всегда остается в группе 1. Чтобы увидеть влияние паспорта и ИНН, выключи штатность.'
                          : 'Без штатности группа считается по гражданству, паспорту и ИНН.',
                      style: TextStyle(color: Colors.grey[700], fontSize: 12),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;

  const _Section({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            ...children,
          ],
        ),
      ),
    );
  }
}

class _WorkerAddressFields extends StatefulWidget {
  final Map<String, dynamic> profile;
  final ValueChanged<Map<String, dynamic>> onSave;

  const _WorkerAddressFields({
    required this.profile,
    required this.onSave,
  });

  @override
  State<_WorkerAddressFields> createState() => _WorkerAddressFieldsState();
}

class _WorkerAddressFieldsState extends State<_WorkerAddressFields> {
  late final TextEditingController _cityController;
  late final TextEditingController _streetController;
  late final TextEditingController _houseController;
  late final TextEditingController _apartmentController;

  @override
  void initState() {
    super.initState();
    _cityController = TextEditingController(
      text: widget.profile['address_city']?.toString() ?? '',
    );
    _streetController = TextEditingController(
      text: widget.profile['address_street']?.toString() ?? '',
    );
    _houseController = TextEditingController(
      text: widget.profile['address_house']?.toString() ?? '',
    );
    _apartmentController = TextEditingController(
      text: widget.profile['address_apartment']?.toString() ?? '',
    );
  }

  @override
  void dispose() {
    _cityController.dispose();
    _streetController.dispose();
    _houseController.dispose();
    _apartmentController.dispose();
    super.dispose();
  }

  void _save() {
    widget.onSave({
      'address_city': _cityController.text.trim(),
      'address_street': _streetController.text.trim(),
      'address_house': _houseController.text.trim(),
      'address_apartment': _apartmentController.text.trim(),
      'address': [
        _cityController.text.trim(),
        _streetController.text.trim(),
        if (_houseController.text.trim().isNotEmpty)
          'д. ${_houseController.text.trim()}',
        if (_apartmentController.text.trim().isNotEmpty)
          'кв./офис ${_apartmentController.text.trim()}',
      ].where((part) => part.isNotEmpty).join(', '),
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          'Адрес',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _cityController,
          decoration: const InputDecoration(
            labelText: 'Город',
            hintText: 'Москва',
            border: OutlineInputBorder(),
          ),
          textInputAction: TextInputAction.next,
          onEditingComplete: _save,
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _streetController,
          decoration: const InputDecoration(
            labelText: 'Улица',
            hintText: 'Ленинградский проспект',
            border: OutlineInputBorder(),
          ),
          textInputAction: TextInputAction.next,
          onEditingComplete: _save,
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: TextFormField(
                controller: _houseController,
                decoration: const InputDecoration(
                  labelText: 'Дом',
                  hintText: '10',
                  border: OutlineInputBorder(),
                ),
                textInputAction: TextInputAction.next,
                onEditingComplete: _save,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextFormField(
                controller: _apartmentController,
                decoration: const InputDecoration(
                  labelText: 'Кв./офис',
                  hintText: '25',
                  border: OutlineInputBorder(),
                ),
                textInputAction: TextInputAction.done,
                onEditingComplete: _save,
                onFieldSubmitted: (_) => _save(),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _WorkerPayoutFields extends StatefulWidget {
  final Map<String, dynamic> profile;
  final bool isSelfEmployed;
  final ValueChanged<Map<String, dynamic>> onSave;

  const _WorkerPayoutFields({
    super.key,
    required this.profile,
    required this.isSelfEmployed,
    required this.onSave,
  });

  @override
  State<_WorkerPayoutFields> createState() => _WorkerPayoutFieldsState();
}

class _WorkerPayoutFieldsState extends State<_WorkerPayoutFields> {
  late String _method;

  @override
  void initState() {
    super.initState();
    final savedMethod = widget.profile['payout_method']?.toString();
    if (!widget.isSelfEmployed) {
      _method = 'card';
    } else {
      _method = savedMethod == 'card' || savedMethod == 'account'
          ? savedMethod!
          : 'account';
    }
  }

  @override
  void didUpdateWidget(covariant _WorkerPayoutFields oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.isSelfEmployed && _method != 'card') {
      _method = 'card';
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) widget.onSave({'payout_method': 'card'});
      });
    }
  }

  void _selectMethod(String method) {
    if (method == 'account' && !widget.isSelfEmployed) return;
    setState(() => _method = method);
    widget.onSave({'payout_method': method});
  }

  @override
  Widget build(BuildContext context) {
    final isAccount = widget.isSelfEmployed && _method == 'account';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          widget.isSelfEmployed
              ? 'Самозанятым по умолчанию выбрана выплата по счету.'
              : 'Счет для выплат доступен после подтверждения самозанятости.',
          style: TextStyle(color: Colors.grey[700], fontSize: 12),
        ),
        const SizedBox(height: 8),
        if (widget.isSelfEmployed) ...[
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(
                value: 'account',
                icon: Icon(Icons.account_balance),
                label: Text('Счет'),
              ),
              ButtonSegment(
                value: 'card',
                icon: Icon(Icons.credit_card),
                label: Text('Карта'),
              ),
            ],
            selected: {_method},
            onSelectionChanged: (selection) => _selectMethod(selection.first),
          ),
          const SizedBox(height: 12),
        ],
        if (isAccount) ...[
          TextFormField(
            initialValue: widget.profile['payout_account']?.toString() ?? '',
            decoration: const InputDecoration(
              labelText: 'Счет для выплат',
              hintText: '20 цифр',
              border: OutlineInputBorder(),
              counterText: '',
            ),
            keyboardType: TextInputType.number,
            maxLength: 20,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            onChanged: (value) {
              final digits = value.replaceAll(RegExp(r'[^0-9]'), '');
              if (digits.length == 20) {
                widget.onSave({'payout_account': digits});
              }
            },
          ),
          const SizedBox(height: 8),
          TextFormField(
            initialValue: widget.profile['payout_bik']?.toString() ?? '',
            decoration: const InputDecoration(
              labelText: 'БИК банка',
              hintText: '9 цифр',
              border: OutlineInputBorder(),
              counterText: '',
            ),
            keyboardType: TextInputType.number,
            maxLength: 9,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            onChanged: (value) {
              final digits = value.replaceAll(RegExp(r'[^0-9]'), '');
              if (digits.length == 9) {
                widget.onSave({'payout_bik': digits});
              }
            },
          ),
        ] else ...[
          TextFormField(
            initialValue: widget.profile['card_last4']?.toString() ?? '',
            decoration: const InputDecoration(
              labelText: 'Карта для выплат',
              prefixText: '**** **** **** ',
              prefixStyle: TextStyle(letterSpacing: 2),
              border: OutlineInputBorder(),
              counterText: '',
            ),
            keyboardType: TextInputType.number,
            maxLength: 4,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            onChanged: (value) {
              final digits = value.replaceAll(RegExp(r'[^0-9]'), '');
              if (digits.length == 4) {
                widget.onSave({'card_last4': digits});
              }
            },
          ),
        ],
      ],
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final Object? value;

  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Expanded(
              child: Text(label, style: TextStyle(color: Colors.grey[700]))),
          const SizedBox(width: 12),
          Flexible(
            child: Text(
              value?.toString() ?? '',
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

class _CheckRow extends StatelessWidget {
  final String title;
  final Object? value;
  final bool isOk;

  const _CheckRow({
    required this.title,
    required this.value,
    required this.isOk,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        isOk ? Icons.verified : Icons.error_outline,
        color: isOk ? Colors.green : Colors.orange,
      ),
      title: Text(title),
      subtitle: Text(value?.toString() ?? ''),
      dense: true,
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _MetricCard({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(
        children: [
          Text(label, style: TextStyle(color: Colors.grey[700], fontSize: 12)),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  final String text;
  final Color color;

  const _StatusPill({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(text, style: TextStyle(fontSize: 11, color: color)),
    );
  }
}

Color _priorityColor(int group) {
  if (group == 1) return Colors.purple;
  if (group >= 2 && group <= 4) return Colors.green;
  if (group >= 5 && group <= 7) return Colors.blue;
  if (group == 8) return Colors.orange;
  return Colors.grey;
}

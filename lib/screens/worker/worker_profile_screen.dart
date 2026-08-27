import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../main.dart' show gpmApi;
import '../../services/gpm_api_service.dart';
import '../../theme/gpm_theme.dart';

class WorkerProfileScreen extends StatefulWidget {
  const WorkerProfileScreen({super.key});

  @override
  State<WorkerProfileScreen> createState() => _WorkerProfileScreenState();
}

class _WorkerProfileScreenState extends State<WorkerProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _email = TextEditingController();
  final _telegram = TextEditingController();
  final _birthDate = TextEditingController();
  final _cities = TextEditingController();
  final _addressCity = TextEditingController();
  final _addressStreet = TextEditingController();
  final _addressHouse = TextEditingController();
  final _addressApartment = TextEditingController();
  final _cardLast4 = TextEditingController();
  final _payoutAccount = TextEditingController();
  final _payoutBik = TextEditingController();

  Map<String, dynamic> _profile = {};
  bool _loading = true;
  bool _saving = false;
  bool _nationality = false;
  bool _hasStraps = false;
  bool _hasTools = false;
  String _employmentType = 'contract';
  String _payoutMethod = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final controller in [
      _name,
      _phone,
      _email,
      _telegram,
      _birthDate,
      _cities,
      _addressCity,
      _addressStreet,
      _addressHouse,
      _addressApartment,
      _cardLast4,
      _payoutAccount,
      _payoutBik,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final raw = gpmApi.isApiMode
          ? await gpmApi.getMyProfile()
          : await gpmApi.getWorkerProfile(GpmApiService.demoWorkerId) ?? {};
      if (!mounted) return;
      _profile = Map<String, dynamic>.from(raw);
      _name.text = _text(raw['display_name'] ?? raw['full_name']);
      _phone.text = _text(raw['phone'] ?? raw['phone_number']);
      _email.text = _text(raw['email']);
      _telegram.text = _text(raw['telegram']);
      _birthDate.text = _text(raw['date_birth']);
      _cities.text = (raw['cities'] as List? ?? const []).join(', ');
      _addressCity.text = _text(raw['address_city']);
      _addressStreet.text = _text(raw['address_street']);
      _addressHouse.text = _text(raw['address_house']);
      _addressApartment.text = _text(raw['address_apartment']);
      _cardLast4.text = _text(raw['card_last4']);
      _payoutAccount.text = _text(raw['payout_account']);
      _payoutBik.text = _text(raw['payout_bik']);
      final tools = _map(raw['tools']);
      _hasStraps = tools['straps'] == true;
      _hasTools = tools['tools'] == true;
      _nationality = raw['nationality'] == true;
      _employmentType = _text(raw['employment_type']).isEmpty
          ? 'contract'
          : _text(raw['employment_type']);
      _payoutMethod = _text(raw['payout_method']);
    } catch (error) {
      if (mounted) _showError('Не удалось загрузить профиль');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate() || _saving) return;
    setState(() => _saving = true);
    final patch = <String, dynamic>{
      'display_name': _name.text.trim(),
      'phone': _phone.text.trim(),
      'email': _email.text.trim(),
      'telegram': _telegram.text.trim(),
      'date_birth': _birthDate.text.trim(),
      'nationality': _nationality,
      'cities': _cities.text
          .split(',')
          .map((item) => item.trim())
          .where((item) => item.isNotEmpty)
          .toList(),
      'employment_type': _employmentType,
      'tools': {'straps': _hasStraps, 'tools': _hasTools},
      'address_city': _addressCity.text.trim(),
      'address_street': _addressStreet.text.trim(),
      'address_house': _addressHouse.text.trim(),
      'address_apartment': _addressApartment.text.trim(),
      'payout_method': _payoutMethod,
      'card_last4': _payoutMethod == 'card' ? _cardLast4.text.trim() : '',
      'payout_account': _payoutMethod == 'account'
          ? _payoutAccount.text.trim()
          : '',
      'payout_bik': _payoutMethod == 'account' ? _payoutBik.text.trim() : '',
    };
    try {
      if (gpmApi.isApiMode) {
        _profile = await gpmApi.updateMyProfile(patch);
      } else {
        await gpmApi.updateWorkerProfile(GpmApiService.demoWorkerId, {
          ...patch,
          'full_name': patch['display_name'],
          'phone_number': patch['phone'],
        });
        _profile = {..._profile, ...patch, 'profile_completion': 100};
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Профиль сохранён'),
          backgroundColor: Colors.green,
        ),
      );
      setState(() {});
    } catch (error) {
      if (mounted) _showError('Не удалось сохранить профиль');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _showError(String text) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(text), backgroundColor: Colors.red));
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    final cities = _cities.text.trim();
    final identityStatus = _text(_profile['identity_status']);
    final npdStatus = _text(_profile['npd_status']);

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 16, 14, 36),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1280),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _ProfileHeader(
                      name: _name.text.trim().isEmpty
                          ? gpmApi.currentUsername
                          : _name.text.trim(),
                      username: _telegram.text.trim().isEmpty
                          ? gpmApi.currentUsername
                          : _telegram.text.trim().replaceFirst('@', ''),
                      completion: _asInt(_profile['profile_completion']),
                      profile: _profile,
                    ),
                    const SizedBox(height: 14),
                    _Section(
                      title: 'Основные данные',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _InfoRow(label: 'Телефон', value: _phone.text),
                          _InfoRow(
                            label: 'Дата рождения',
                            value: _birthDate.text,
                          ),
                          _InfoRow(
                            label: 'Гражданство РФ',
                            value: _nationality ? 'Да' : 'Нет',
                          ),
                          _InfoRow(label: 'Города', value: cities),
                          _InfoRow(
                            label: 'Тип занятости',
                            value: _employmentType == 'state'
                                ? 'Штатный'
                                : 'Подрядчик',
                          ),
                          const SizedBox(height: 10),
                          const Text(
                            'Адрес',
                            style: TextStyle(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 8),
                          TextFormField(
                            controller: _addressCity,
                            decoration: const InputDecoration(
                              labelText: 'Город',
                              hintText: 'Москва',
                            ),
                          ),
                          const SizedBox(height: 8),
                          TextFormField(
                            controller: _addressStreet,
                            decoration: const InputDecoration(
                              labelText: 'Улица',
                            ),
                          ),
                          const SizedBox(height: 8),
                          _AdaptiveRow(
                            children: [
                              TextFormField(
                                controller: _addressHouse,
                                decoration: const InputDecoration(
                                  labelText: 'Дом',
                                ),
                              ),
                              TextFormField(
                                controller: _addressApartment,
                                decoration: const InputDecoration(
                                  labelText: 'Кв./офис',
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 14),
                    _Section(
                      title: 'Выплаты',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const Text(
                            'Самозанятым по умолчанию выбрана выплата по счету.',
                            style: TextStyle(
                              color: GpmColors.graphite,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 8),
                          SegmentedButton<String>(
                            segments: const [
                              ButtonSegment(
                                value: 'account',
                                icon: Icon(Icons.account_balance_outlined),
                                label: Text('Счёт'),
                              ),
                              ButtonSegment(
                                value: 'card',
                                icon: Icon(Icons.credit_card_outlined),
                                label: Text('Карта'),
                              ),
                            ],
                            selected: _payoutMethod.isEmpty
                                ? const <String>{}
                                : {_payoutMethod},
                            emptySelectionAllowed: true,
                            onSelectionChanged: (selection) => setState(
                              () => _payoutMethod = selection.isEmpty
                                  ? ''
                                  : selection.first,
                            ),
                          ),
                          if (_payoutMethod == 'card') ...[
                            const SizedBox(height: 10),
                            TextFormField(
                              controller: _cardLast4,
                              keyboardType: TextInputType.number,
                              inputFormatters: [
                                FilteringTextInputFormatter.digitsOnly,
                                LengthLimitingTextInputFormatter(4),
                              ],
                              decoration: const InputDecoration(
                                labelText: 'Карта для выплат',
                                prefixText: '**** **** **** ',
                              ),
                              validator: (value) =>
                                  value?.length == 4 ? null : 'Укажите 4 цифры',
                            ),
                          ],
                          if (_payoutMethod == 'account') ...[
                            const SizedBox(height: 10),
                            TextFormField(
                              controller: _payoutAccount,
                              decoration: const InputDecoration(
                                labelText: 'Счёт для выплат',
                              ),
                              keyboardType: TextInputType.number,
                              inputFormatters: [
                                FilteringTextInputFormatter.digitsOnly,
                                LengthLimitingTextInputFormatter(20),
                              ],
                            ),
                            const SizedBox(height: 8),
                            TextFormField(
                              controller: _payoutBik,
                              decoration: const InputDecoration(
                                labelText: 'БИК банка',
                              ),
                              keyboardType: TextInputType.number,
                              inputFormatters: [
                                FilteringTextInputFormatter.digitsOnly,
                                LengthLimitingTextInputFormatter(9),
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: 14),
                    _Section(
                      title: 'Проверки',
                      child: Column(
                        children: [
                          _CheckRow(
                            title: 'Паспортные данные',
                            value: _verificationLabel(identityStatus),
                            isOk: identityStatus == 'verified',
                          ),
                          _CheckRow(
                            title: 'Самозанятость / НПД',
                            value: _verificationLabel(npdStatus),
                            isOk: npdStatus == 'verified',
                          ),
                          _CheckRow(
                            title: 'Такелажные ремни',
                            value: _hasStraps ? 'Есть' : 'Нет',
                            isOk: _hasStraps,
                          ),
                          _CheckRow(
                            title: 'Инструменты',
                            value: _hasTools ? 'Есть' : 'Нет',
                            isOk: _hasTools,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Expanded(
                          child: _MetricCard(
                            label: 'Рейтинг',
                            value: '${_asInt(_profile['rating'])}',
                            color: Colors.blue,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: _MetricCard(
                            label: 'Успешно',
                            value: '${_asInt(_profile['success_requests'])}',
                            color: Colors.green,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: _MetricCard(
                            label: 'Срывы',
                            value: '${_asInt(_profile['fail_requests'])}',
                            color: Colors.red,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    ElevatedButton.icon(
                      onPressed: _saving ? null : _save,
                      icon: _saving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.save_outlined),
                      label: Text(
                        _saving ? 'Сохраняем...' : 'Сохранить профиль',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  final String name;
  final String username;
  final int completion;
  final Map<String, dynamic> profile;

  const _ProfileHeader({
    required this.name,
    required this.username,
    required this.completion,
    required this.profile,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const CircleAvatar(
          radius: 28,
          backgroundColor: Color(0xFF5B4FFF),
          foregroundColor: Colors.white,
          child: Icon(Icons.engineering, size: 29),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 3),
              Text('@$username'),
              const SizedBox(height: 7),
              _StatusPill(
                text: _workerGroupLabel(profile, completion),
                color: Colors.green,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final Widget child;

  const _Section({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          child,
        ],
      ),
    );
  }
}

class _AdaptiveRow extends StatelessWidget {
  final List<Widget> children;

  const _AdaptiveRow({required this.children});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 680) {
          return Column(
            children: [
              for (var index = 0; index < children.length; index++) ...[
                children[index],
                if (index != children.length - 1) const SizedBox(height: 12),
              ],
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (var index = 0; index < children.length; index++) ...[
              Expanded(child: children[index]),
              if (index != children.length - 1) const SizedBox(width: 12),
            ],
          ],
        );
      },
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(color: Color(0xFF6F6F6F)),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              value.isEmpty ? 'Не указано' : value,
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
  final String value;
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
      subtitle: Text(value),
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
          Text(label, style: const TextStyle(fontSize: 12)),
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

String _workerGroupLabel(Map<String, dynamic> profile, int completion) {
  if (profile['employment_type'] == 'state') return 'Группа 1: штатный';
  final russian = profile['nationality'] == true;
  final identity = profile['identity_status'] == 'verified';
  final npd = profile['npd_status'] == 'verified';
  if (russian && identity && npd) {
    return 'Группа 2: РФ, паспорт, самозанятый';
  }
  if (russian && npd) return 'Группа 3: РФ, самозанятый';
  if (identity && npd) return 'Группа 4: паспорт, самозанятый';
  if (npd) return 'Группа 5: самозанятый';
  if (russian && identity) return 'Группа 6: РФ, паспорт';
  if (identity) return 'Группа 7: паспорт';
  if (russian) return 'Группа 8: РФ';
  return 'Профиль заполнен на $completion%';
}

String _verificationLabel(String status) {
  return switch (status) {
    'verified' => 'Подтверждено',
    'pending' => 'На проверке',
    'rejected' => 'Нужно исправить',
    _ => 'Не подтверждено',
  };
}

String _text(dynamic value) => value?.toString().trim() ?? '';
int _asInt(dynamic value) => int.tryParse(value?.toString() ?? '') ?? 0;

Map<String, dynamic> _map(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return <String, dynamic>{};
}

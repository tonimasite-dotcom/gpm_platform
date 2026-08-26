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

  String? _required(String? value) {
    return value == null || value.trim().isEmpty ? 'Заполните поле' : null;
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 18, 16, 36),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 980),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _ProfileHeader(
                      name: _name.text.trim().isEmpty
                          ? gpmApi.currentUsername
                          : _name.text.trim(),
                      username: gpmApi.currentUsername,
                      completion: _asInt(_profile['profile_completion']),
                    ),
                    const SizedBox(height: 16),
                    _Section(
                      title: 'Основные данные',
                      icon: Icons.badge_outlined,
                      child: Column(
                        children: [
                          _AdaptiveRow(
                            children: [
                              TextFormField(
                                controller: _name,
                                decoration: const InputDecoration(
                                  labelText: 'ФИО',
                                ),
                                validator: _required,
                              ),
                              TextFormField(
                                controller: _birthDate,
                                decoration: const InputDecoration(
                                  labelText: 'Дата рождения',
                                  hintText: 'ДД.ММ.ГГГГ',
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          _AdaptiveRow(
                            children: [
                              TextFormField(
                                controller: _phone,
                                keyboardType: TextInputType.phone,
                                decoration: const InputDecoration(
                                  labelText: 'Телефон',
                                ),
                                validator: _required,
                              ),
                              TextFormField(
                                controller: _email,
                                keyboardType: TextInputType.emailAddress,
                                decoration: const InputDecoration(
                                  labelText: 'Email',
                                ),
                              ),
                              TextFormField(
                                controller: _telegram,
                                decoration: const InputDecoration(
                                  labelText: 'Telegram',
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          SwitchListTile(
                            contentPadding: EdgeInsets.zero,
                            title: const Text('Гражданство РФ'),
                            subtitle: const Text(
                              'Используется при подборе заявок с требованиями к гражданству',
                            ),
                            value: _nationality,
                            onChanged: (value) =>
                                setState(() => _nationality = value),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    _Section(
                      title: 'Работа и география',
                      icon: Icons.work_outline,
                      child: Column(
                        children: [
                          DropdownButtonFormField<String>(
                            initialValue: _employmentType,
                            decoration: const InputDecoration(
                              labelText: 'Формат работы',
                            ),
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
                            onChanged: (value) {
                              if (value != null) {
                                setState(() => _employmentType = value);
                              }
                            },
                          ),
                          const SizedBox(height: 12),
                          TextFormField(
                            controller: _cities,
                            decoration: const InputDecoration(
                              labelText: 'Города работы',
                              hintText: 'Москва, Химки',
                            ),
                            validator: _required,
                          ),
                          const SizedBox(height: 12),
                          _AdaptiveRow(
                            children: [
                              TextFormField(
                                controller: _addressCity,
                                decoration: const InputDecoration(
                                  labelText: 'Город',
                                ),
                              ),
                              TextFormField(
                                controller: _addressStreet,
                                decoration: const InputDecoration(
                                  labelText: 'Улица',
                                ),
                              ),
                              TextFormField(
                                controller: _addressHouse,
                                decoration: const InputDecoration(
                                  labelText: 'Дом',
                                ),
                              ),
                              TextFormField(
                                controller: _addressApartment,
                                decoration: const InputDecoration(
                                  labelText: 'Квартира',
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 12,
                            runSpacing: 8,
                            children: [
                              FilterChip(
                                label: const Text('Такелажные ремни'),
                                selected: _hasStraps,
                                onSelected: (value) =>
                                    setState(() => _hasStraps = value),
                              ),
                              FilterChip(
                                label: const Text('Свой инструмент'),
                                selected: _hasTools,
                                onSelected: (value) =>
                                    setState(() => _hasTools = value),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    _Section(
                      title: 'Реквизиты для выплат',
                      icon: Icons.account_balance_wallet_outlined,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          SegmentedButton<String>(
                            segments: const [
                              ButtonSegment(
                                value: '',
                                label: Text('Не выбрано'),
                              ),
                              ButtonSegment(
                                value: 'card',
                                label: Text('Карта'),
                              ),
                              ButtonSegment(
                                value: 'account',
                                label: Text('Счёт'),
                              ),
                            ],
                            selected: {_payoutMethod},
                            onSelectionChanged: (selection) =>
                                setState(() => _payoutMethod = selection.first),
                          ),
                          if (_payoutMethod == 'card') ...[
                            const SizedBox(height: 12),
                            TextFormField(
                              controller: _cardLast4,
                              keyboardType: TextInputType.number,
                              inputFormatters: [
                                FilteringTextInputFormatter.digitsOnly,
                                LengthLimitingTextInputFormatter(4),
                              ],
                              decoration: const InputDecoration(
                                labelText: 'Последние 4 цифры карты',
                              ),
                              validator: (value) =>
                                  value?.length == 4 ? null : 'Укажите 4 цифры',
                            ),
                          ],
                          if (_payoutMethod == 'account') ...[
                            const SizedBox(height: 12),
                            _AdaptiveRow(
                              children: [
                                TextFormField(
                                  controller: _payoutAccount,
                                  decoration: const InputDecoration(
                                    labelText: 'Расчётный счёт',
                                  ),
                                  validator: _required,
                                ),
                                TextFormField(
                                  controller: _payoutBik,
                                  decoration: const InputDecoration(
                                    labelText: 'БИК',
                                  ),
                                  validator: _required,
                                ),
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    _Section(
                      title: 'Проверки',
                      icon: Icons.verified_user_outlined,
                      child: Column(
                        children: [
                          _VerificationRow(
                            title: 'Личность',
                            status: _text(_profile['identity_status']),
                          ),
                          _VerificationRow(
                            title: 'Право на работу',
                            status: _text(_profile['work_status']),
                          ),
                          _VerificationRow(
                            title: 'Самозанятость / НПД',
                            status: _text(_profile['npd_status']),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),
                    FilledButton.icon(
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

  const _ProfileHeader({
    required this.name,
    required this.username,
    required this.completion,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: GpmColors.line),
      ),
      child: Row(
        children: [
          const CircleAvatar(
            radius: 30,
            backgroundColor: GpmColors.red,
            foregroundColor: Colors.white,
            child: Icon(Icons.engineering_outlined, size: 31),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 3),
                Text(
                  '@$username · Исполнитель',
                  style: const TextStyle(color: GpmColors.graphite),
                ),
              ],
            ),
          ),
          SizedBox(
            width: 72,
            height: 72,
            child: Stack(
              fit: StackFit.expand,
              children: [
                CircularProgressIndicator(
                  value: completion / 100,
                  strokeWidth: 7,
                  backgroundColor: GpmColors.line,
                  color: completion == 100 ? Colors.green : GpmColors.red,
                ),
                Center(
                  child: Text(
                    '$completion%',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;

  const _Section({
    required this.title,
    required this.icon,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(icon, color: GpmColors.red),
              const SizedBox(width: 9),
              Text(title, style: Theme.of(context).textTheme.titleLarge),
            ],
          ),
          const SizedBox(height: 16),
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

class _VerificationRow extends StatelessWidget {
  final String title;
  final String status;

  const _VerificationRow({required this.title, required this.status});

  @override
  Widget build(BuildContext context) {
    final verified = status == 'verified';
    final pending = status == 'pending';
    final color = verified
        ? Colors.green
        : pending
        ? Colors.orange
        : Colors.grey;
    final label = verified
        ? 'Подтверждено'
        : pending
        ? 'На проверке'
        : status == 'rejected'
        ? 'Нужно исправить'
        : 'Не отправлено';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        verified ? Icons.check_circle : Icons.shield_outlined,
        color: color,
      ),
      title: Text(title),
      trailing: Text(
        label,
        style: TextStyle(color: color, fontWeight: FontWeight.w700),
      ),
    );
  }
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

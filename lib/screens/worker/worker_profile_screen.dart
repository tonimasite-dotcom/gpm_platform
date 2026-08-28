import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

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
  bool _submittingVerification = false;
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
    } catch (_) {
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
    } catch (_) {
      if (mounted) _showError('Не удалось сохранить профиль');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _submitPassport() async {
    final draft = await showDialog<_PassportDraft>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _PassportDialog(initialFullName: _name.text.trim()),
    );
    if (draft == null || !mounted) return;
    setState(() => _submittingVerification = true);
    try {
      if (gpmApi.isApiMode) {
        final bytes = await draft.photo.readAsBytes();
        await gpmApi.submitMyVerification(
          verificationType: 'identity',
          data: draft.data,
          attachmentBytes: bytes,
          attachmentName: draft.photo.name,
          attachmentMediaType: _imageMediaType(draft.photo),
        );
        await _load();
      } else {
        setState(() {
          _profile = {
            ..._profile,
            'identity_status': 'pending',
            'identity_rejection_reason': '',
          };
        });
      }
      if (!mounted) return;
      _showSuccess('Паспорт отправлен на модерацию');
    } catch (_) {
      if (mounted) _showError('Не удалось отправить паспорт на модерацию');
    } finally {
      if (mounted) setState(() => _submittingVerification = false);
    }
  }

  Future<void> _submitNpd() async {
    final inn = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) => const _NpdDialog(),
    );
    if (inn == null || !mounted) return;
    setState(() => _submittingVerification = true);
    try {
      if (gpmApi.isApiMode) {
        await gpmApi.submitMyVerification(
          verificationType: 'npd',
          data: {'inn': inn},
        );
        await _load();
      } else {
        setState(() {
          _profile = {
            ..._profile,
            'npd_status': 'pending',
            'npd_rejection_reason': '',
          };
        });
      }
      if (!mounted) return;
      _showSuccess('Заявка на подтверждение НПД отправлена');
    } catch (_) {
      if (mounted) _showError('Не удалось отправить заявку на модерацию');
    } finally {
      if (mounted) setState(() => _submittingVerification = false);
    }
  }

  void _showError(String text) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(text), backgroundColor: Colors.red));
  }

  void _showSuccess(String text) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(text), backgroundColor: Colors.green),
    );
  }

  String? _required(String? value) {
    return value == null || value.trim().isEmpty ? 'Заполните поле' : null;
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    final identityStatus = _text(_profile['identity_status']);
    final npdStatus = _text(_profile['npd_status']);

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1280),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const _ProfileHeader(
                      icon: Icons.engineering_outlined,
                      title: 'Кабинет исполнителя',
                      subtitle: 'Личные данные, оснащение и подтверждения',
                    ),
                    const SizedBox(height: 16),
                    _Section(
                      title: 'Основные данные',
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
                                validator: _required,
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
                            ],
                          ),
                          const SizedBox(height: 12),
                          _AdaptiveRow(
                            children: [
                              TextFormField(
                                controller: _cities,
                                decoration: const InputDecoration(
                                  labelText: 'Города работы',
                                  hintText: 'Москва, Химки',
                                ),
                                validator: _required,
                              ),
                              DropdownButtonFormField<String>(
                                initialValue: _employmentType,
                                decoration: const InputDecoration(
                                  labelText: 'Тип занятости',
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
                            ],
                          ),
                          const SizedBox(height: 14),
                          _YesNoField(
                            label: 'Гражданство РФ',
                            value: _nationality,
                            onChanged: (value) =>
                                setState(() => _nationality = value),
                          ),
                          const SizedBox(height: 14),
                          const Align(
                            alignment: Alignment.centerLeft,
                            child: Text(
                              'Адрес',
                              style: TextStyle(fontWeight: FontWeight.w700),
                            ),
                          ),
                          const SizedBox(height: 8),
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
                            ],
                          ),
                          const SizedBox(height: 12),
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
                    const SizedBox(height: 16),
                    _Section(
                      title: 'Оснащение',
                      child: _AdaptiveRow(
                        children: [
                          _YesNoField(
                            label: 'Такелажные ремни',
                            value: _hasStraps,
                            onChanged: (value) =>
                                setState(() => _hasStraps = value),
                          ),
                          _YesNoField(
                            label: 'Свои инструменты',
                            value: _hasTools,
                            onChanged: (value) =>
                                setState(() => _hasTools = value),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    _Section(
                      title: 'Выплаты',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const Text(
                            'Самозанятым по умолчанию выбрана выплата по счёту.',
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
                            const SizedBox(height: 12),
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
                            const SizedBox(height: 12),
                            _AdaptiveRow(
                              children: [
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
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    _Section(
                      title: 'Проверки',
                      child: Column(
                        children: [
                          _VerificationCard(
                            title: 'Паспортные данные',
                            description:
                                'Заполните данные паспорта и приложите фотографию основного разворота.',
                            status: identityStatus,
                            rejectionReason: _text(
                              _profile['identity_rejection_reason'],
                            ),
                            actionLabel: identityStatus == 'rejected'
                                ? 'Исправить и отправить повторно'
                                : 'Отправить паспорт на проверку',
                            onPressed: _submittingVerification
                                ? null
                                : _submitPassport,
                          ),
                          const SizedBox(height: 12),
                          _VerificationCard(
                            title: 'Самозанятость / НПД',
                            description:
                                'Укажите ИНН, чтобы логист проверил статус самозанятого.',
                            status: npdStatus,
                            rejectionReason: _text(
                              _profile['npd_rejection_reason'],
                            ),
                            actionLabel: npdStatus == 'rejected'
                                ? 'Исправить и отправить повторно'
                                : 'Отправить заявку на подтверждение',
                            onPressed: _submittingVerification
                                ? null
                                : _submitNpd,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
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
                    const SizedBox(height: 16),
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
          const SizedBox(height: 12),
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

class _YesNoField extends StatelessWidget {
  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _YesNoField({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        SegmentedButton<bool>(
          segments: const [
            ButtonSegment(value: true, label: Text('Да')),
            ButtonSegment(value: false, label: Text('Нет')),
          ],
          selected: {value},
          onSelectionChanged: (selection) => onChanged(selection.first),
        ),
      ],
    );
  }
}

class _VerificationCard extends StatelessWidget {
  final String title;
  final String description;
  final String status;
  final String rejectionReason;
  final String actionLabel;
  final VoidCallback? onPressed;

  const _VerificationCard({
    required this.title,
    required this.description,
    required this.status,
    required this.rejectionReason,
    required this.actionLabel,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final verified = status == 'verified';
    final pending = status == 'pending';
    final rejected = status == 'rejected';
    final color = verified
        ? Colors.green
        : pending
        ? GpmColors.yellow
        : rejected
        ? GpmColors.red
        : GpmColors.graphite;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(
                verified
                    ? Icons.verified
                    : pending
                    ? Icons.schedule
                    : Icons.verified_user_outlined,
                color: color,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                _verificationLabel(status),
                style: TextStyle(color: color, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(description),
          if (rejected && rejectionReason.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Причина: $rejectionReason',
              style: const TextStyle(
                color: GpmColors.red,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          if (!verified && !pending) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: onPressed,
              icon: const Icon(Icons.send_outlined),
              label: Text(actionLabel),
            ),
          ],
        ],
      ),
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

class _PassportDraft {
  final Map<String, dynamic> data;
  final XFile photo;

  const _PassportDraft({required this.data, required this.photo});
}

class _PassportDialog extends StatefulWidget {
  final String initialFullName;

  const _PassportDialog({required this.initialFullName});

  @override
  State<_PassportDialog> createState() => _PassportDialogState();
}

class _PassportDialogState extends State<_PassportDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _fullName;
  final _series = TextEditingController();
  final _number = TextEditingController();
  final _issuedAt = TextEditingController();
  final _departmentCode = TextEditingController();
  final _issuedBy = TextEditingController();
  XFile? _photo;
  bool _picking = false;

  @override
  void initState() {
    super.initState();
    _fullName = TextEditingController(text: widget.initialFullName);
  }

  @override
  void dispose() {
    _fullName.dispose();
    _series.dispose();
    _number.dispose();
    _issuedAt.dispose();
    _departmentCode.dispose();
    _issuedBy.dispose();
    super.dispose();
  }

  Future<void> _pick(ImageSource source) async {
    setState(() => _picking = true);
    try {
      final photo = await ImagePicker().pickImage(
        source: source,
        maxWidth: 2400,
        imageQuality: 90,
      );
      if (mounted && photo != null) setState(() => _photo = photo);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Не удалось выбрать фотографию')),
      );
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  String? _required(String? value) =>
      value == null || value.trim().isEmpty ? 'Заполните поле' : null;

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    if (_photo == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Приложите фотографию паспорта')),
      );
      return;
    }
    Navigator.of(context).pop(
      _PassportDraft(
        data: {
          'full_name': _fullName.text.trim(),
          'passport_series': _series.text.trim(),
          'passport_number': _number.text.trim(),
          'issued_at': _issuedAt.text.trim(),
          'department_code': _departmentCode.text.trim(),
          'issued_by': _issuedBy.text.trim(),
        },
        photo: _photo!,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Паспортные данные'),
      content: SizedBox(
        width: 620,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Используйте только закрытый тестовый контур. Фотография будет храниться в защищённом серверном каталоге.',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _fullName,
                  decoration: const InputDecoration(labelText: 'ФИО'),
                  validator: _required,
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _series,
                        keyboardType: TextInputType.number,
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                          LengthLimitingTextInputFormatter(4),
                        ],
                        decoration: const InputDecoration(labelText: 'Серия'),
                        validator: (value) =>
                            value?.length == 4 ? null : 'Укажите 4 цифры',
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        controller: _number,
                        keyboardType: TextInputType.number,
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                          LengthLimitingTextInputFormatter(6),
                        ],
                        decoration: const InputDecoration(labelText: 'Номер'),
                        validator: (value) =>
                            value?.length == 6 ? null : 'Укажите 6 цифр',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _issuedAt,
                        decoration: const InputDecoration(
                          labelText: 'Дата выдачи',
                          hintText: 'ДД.ММ.ГГГГ',
                        ),
                        validator: _required,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        controller: _departmentCode,
                        keyboardType: TextInputType.number,
                        inputFormatters: const [_DepartmentCodeFormatter()],
                        decoration: const InputDecoration(
                          labelText: 'Код подразделения',
                          hintText: '000-000',
                        ),
                        validator: _required,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _issuedBy,
                  maxLines: 2,
                  decoration: const InputDecoration(labelText: 'Кем выдан'),
                  validator: _required,
                ),
                const SizedBox(height: 12),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    border: Border.all(color: GpmColors.line),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    children: [
                      Icon(
                        _photo == null
                            ? Icons.photo_camera_outlined
                            : Icons.check_circle,
                        color: _photo == null
                            ? GpmColors.graphite
                            : Colors.green,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        _photo?.name ?? 'Фото основного разворота не выбрано',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        alignment: WrapAlignment.center,
                        children: [
                          OutlinedButton.icon(
                            onPressed: _picking
                                ? null
                                : () => _pick(ImageSource.gallery),
                            icon: const Icon(Icons.image_outlined),
                            label: const Text('Выбрать фото'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _picking
                                ? null
                                : () => _pick(ImageSource.camera),
                            icon: const Icon(Icons.photo_camera_outlined),
                            label: const Text('Сделать фото'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Отмена'),
        ),
        FilledButton.icon(
          onPressed: _submit,
          icon: const Icon(Icons.send_outlined),
          label: const Text('Отправить на проверку'),
        ),
      ],
    );
  }
}

class _DepartmentCodeFormatter extends TextInputFormatter {
  const _DepartmentCodeFormatter();

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(RegExp(r'\D'), '');
    final limited = digits.length > 6 ? digits.substring(0, 6) : digits;
    final formatted = limited.length > 3
        ? '${limited.substring(0, 3)}-${limited.substring(3)}'
        : limited;
    return TextEditingValue(
      text: formatted,
      selection: TextSelection.collapsed(offset: formatted.length),
    );
  }
}

class _NpdDialog extends StatefulWidget {
  const _NpdDialog();

  @override
  State<_NpdDialog> createState() => _NpdDialogState();
}

class _NpdDialogState extends State<_NpdDialog> {
  final _formKey = GlobalKey<FormState>();
  final _inn = TextEditingController();

  @override
  void dispose() {
    _inn.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Подтверждение самозанятости'),
      content: SizedBox(
        width: 480,
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'После отправки заявка появится у логиста на модерации.',
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _inn,
                keyboardType: TextInputType.number,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(12),
                ],
                decoration: const InputDecoration(labelText: 'ИНН'),
                validator: (value) =>
                    value?.length == 12 ? null : 'Укажите 12 цифр ИНН',
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Отмена'),
        ),
        FilledButton.icon(
          onPressed: () {
            if (_formKey.currentState!.validate()) {
              Navigator.of(context).pop(_inn.text.trim());
            }
          },
          icon: const Icon(Icons.send_outlined),
          label: const Text('Отправить на проверку'),
        ),
      ],
    );
  }
}

String _imageMediaType(XFile photo) {
  final mimeType = photo.mimeType?.toLowerCase();
  if (mimeType == 'image/png') return 'image/png';
  return 'image/jpeg';
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

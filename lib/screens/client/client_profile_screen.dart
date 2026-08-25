import 'dart:convert';

import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../services/demo_storage.dart';
import '../../theme/gpm_theme.dart';
import '../../widgets/feature_unavailable.dart';

class ClientProfileScreen extends StatefulWidget {
  const ClientProfileScreen({super.key});

  @override
  State<ClientProfileScreen> createState() => _ClientProfileScreenState();
}

class _ClientProfileScreenState extends State<ClientProfileScreen> {
  static const _storageKey = 'gpm.client.profile.v1';

  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _companyController = TextEditingController();
  final _innController = TextEditingController();
  final _kppController = TextEditingController();
  final _ogrnController = TextEditingController();
  final _contactController = TextEditingController();
  final _phoneController = TextEditingController();
  final _emailController = TextEditingController();
  final _addressController = TextEditingController();
  final _legalAddressController = TextEditingController();
  final _checkingAccountController = TextEditingController();
  final _bankController = TextEditingController();
  final _bikController = TextEditingController();
  final _correspondentAccountController = TextEditingController();
  final _documentsEmailController = TextEditingController();

  String _clientType = 'individual';
  String _paymentType = 'card';
  bool _profileLoaded = false;

  @override
  void initState() {
    super.initState();
    if (gpmApi.isApiMode) {
      _profileLoaded = true;
    } else {
      _loadProfile();
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _companyController.dispose();
    _innController.dispose();
    _kppController.dispose();
    _ogrnController.dispose();
    _contactController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _addressController.dispose();
    _legalAddressController.dispose();
    _checkingAccountController.dispose();
    _bankController.dispose();
    _bikController.dispose();
    _correspondentAccountController.dispose();
    _documentsEmailController.dispose();
    super.dispose();
  }

  void _loadProfile() {
    final raw = readDemoValue(_storageKey);
    if (raw != null) {
      final data = jsonDecode(raw) as Map<String, dynamic>;
      _clientType = data['client_type']?.toString() ?? _clientType;
      _paymentType = data['payment_type']?.toString() ?? _paymentType;
      if (_clientType == 'legal') {
        _paymentType = 'invoice';
      } else if (_paymentType == 'invoice') {
        _paymentType = 'card';
      }
      _nameController.text = data['name']?.toString() ?? '';
      _companyController.text = data['company']?.toString() ?? '';
      _innController.text = data['inn']?.toString() ?? '';
      _kppController.text = data['kpp']?.toString() ?? '';
      _ogrnController.text = data['ogrn']?.toString() ?? '';
      _contactController.text = data['contact']?.toString() ?? '';
      _phoneController.text = data['phone']?.toString() ?? '';
      _emailController.text = data['email']?.toString() ?? '';
      _addressController.text = data['address']?.toString() ?? '';
      _legalAddressController.text = data['legal_address']?.toString() ?? '';
      _checkingAccountController.text =
          data['checking_account']?.toString() ?? '';
      _bankController.text = data['bank']?.toString() ?? '';
      _bikController.text = data['bik']?.toString() ?? '';
      _correspondentAccountController.text =
          data['correspondent_account']?.toString() ?? '';
      _documentsEmailController.text =
          data['documents_email']?.toString() ?? '';
    }
    setState(() => _profileLoaded = true);
  }

  void _saveProfile() {
    if (!_formKey.currentState!.validate()) return;

    writeDemoValue(
      _storageKey,
      jsonEncode({
        'client_type': _clientType,
        'payment_type': _paymentType,
        'name': _nameController.text.trim(),
        'company': _companyController.text.trim(),
        'inn': _innController.text.trim(),
        'kpp': _kppController.text.trim(),
        'ogrn': _ogrnController.text.trim(),
        'contact': _contactController.text.trim(),
        'phone': _phoneController.text.trim(),
        'email': _emailController.text.trim(),
        'address': _addressController.text.trim(),
        'legal_address': _legalAddressController.text.trim(),
        'checking_account': _checkingAccountController.text.trim(),
        'bank': _bankController.text.trim(),
        'bik': _bikController.text.trim(),
        'correspondent_account': _correspondentAccountController.text.trim(),
        'documents_email': _documentsEmailController.text.trim(),
        'updated_at': DateTime.now().toUtc().toIso8601String(),
      }),
    );

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Профиль клиента сохранен')),
    );
  }

  String? _required(String? value, String message) {
    return value == null || value.trim().isEmpty ? message : null;
  }

  void _showSupportMessage() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Поддержка 24/7 скоро будет доступна')),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (gpmApi.isApiMode) {
      return const FeatureUnavailable(
        title: 'Профиль клиента готовится',
        message:
            'Профиль и реквизиты должны храниться на сервере с привязкой к '
            'учётной записи. Локальное сохранение чувствительных данных отключено '
            'для production-режима.',
        icon: Icons.account_circle_outlined,
      );
    }
    if (!_profileLoaded) {
      return const Center(child: CircularProgressIndicator());
    }

    final isLegal = _clientType == 'legal';

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
                icon: Icons.business_center_outlined,
                title: 'Кабинет клиента',
                subtitle: isLegal
                    ? 'Юрлицо: реквизиты, контакт и способ оплаты'
                    : 'Физлицо: контактные данные и предпочтения',
              ),
              const SizedBox(height: 16),
              const Text(
                'Тип клиента',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(
                    value: 'individual',
                    icon: Icon(Icons.person_outline),
                    label: Text('Физлицо'),
                  ),
                  ButtonSegment(
                    value: 'legal',
                    icon: Icon(Icons.apartment),
                    label: Text('Юрлицо'),
                  ),
                ],
                selected: {_clientType},
                onSelectionChanged: (selection) {
                  setState(() {
                    _clientType = selection.first;
                    _paymentType = _clientType == 'legal' ? 'invoice' : 'card';
                  });
                },
              ),
              const SizedBox(height: 16),
              if (isLegal) ...[
                TextFormField(
                  controller: _companyController,
                  decoration: const InputDecoration(
                    labelText: 'Название компании',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) =>
                      _required(value, 'Укажите название компании'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _innController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'ИНН',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) => _required(value, 'Укажите ИНН'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _kppController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'КПП',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) => _required(value, 'Укажите КПП'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _ogrnController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'ОГРН',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
              ] else ...[
                TextFormField(
                  controller: _nameController,
                  decoration: const InputDecoration(
                    labelText: 'ФИО',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) => _required(value, 'Укажите ФИО'),
                ),
                const SizedBox(height: 12),
              ],
              TextFormField(
                controller: _contactController,
                decoration: InputDecoration(
                  labelText:
                      isLegal ? 'Контактное лицо' : 'Как к вам обращаться',
                  border: const OutlineInputBorder(),
                ),
                validator: (value) => _required(value, 'Укажите контакт'),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: 'Телефон',
                  border: OutlineInputBorder(),
                ),
                validator: (value) => _required(value, 'Укажите телефон'),
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
              TextFormField(
                controller: _addressController,
                decoration: const InputDecoration(
                  labelText: 'Основной адрес',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Способ оплаты',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: isLegal
                    ? const [
                        ButtonSegment(
                          value: 'invoice',
                          icon: Icon(Icons.receipt_long_outlined),
                          label: Text('Счет'),
                        ),
                      ]
                    : const [
                        ButtonSegment(
                          value: 'card',
                          icon: Icon(Icons.credit_card),
                          label: Text('Карта'),
                        ),
                        ButtonSegment(
                          value: 'cash',
                          icon: Icon(Icons.payments_outlined),
                          label: Text('Наличные'),
                        ),
                      ],
                selected: {_paymentType},
                onSelectionChanged: (selection) {
                  setState(() => _paymentType = selection.first);
                },
              ),
              if (isLegal) ...[
                const SizedBox(height: 16),
                const Text(
                  'Реквизиты для счета',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _legalAddressController,
                  decoration: const InputDecoration(
                    labelText: 'Юридический адрес',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) =>
                      _required(value, 'Укажите юридический адрес'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _checkingAccountController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Расчетный счет',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) =>
                      _required(value, 'Укажите расчетный счет'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _bankController,
                  decoration: const InputDecoration(
                    labelText: 'Банк',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) => _required(value, 'Укажите банк'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _bikController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'БИК',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) => _required(value, 'Укажите БИК'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _correspondentAccountController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Корреспондентский счет',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _documentsEmailController,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(
                    labelText: 'Email для документов',
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
              const SizedBox(height: 20),
              OutlinedButton.icon(
                onPressed: _showSupportMessage,
                icon: const Icon(Icons.support_agent),
                label: const Text('Обратиться в поддержку 24/7'),
              ),
              const SizedBox(height: 12),
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

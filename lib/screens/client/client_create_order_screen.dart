import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../services/demo_storage.dart';
import '../../services/gpm_api_service.dart';
import '../../theme/gpm_theme.dart';

class ClientCreateOrderScreen extends StatefulWidget {
  final bool publishImmediately;
  final bool closeOnSuccess;
  final String title;
  final String submitText;
  final VoidCallback? onBack;

  const ClientCreateOrderScreen({
    super.key,
    this.publishImmediately = false,
    this.closeOnSuccess = false,
    this.title = 'Создание заказа',
    this.submitText = 'Создать заказ',
    this.onBack,
  });

  @override
  State<ClientCreateOrderScreen> createState() =>
      _ClientCreateOrderScreenState();
}

class _ClientCreateOrderScreenState extends State<ClientCreateOrderScreen> {
  final _formKey = GlobalKey<FormState>();
  final _cityController = TextEditingController(text: 'Москва');
  final _dateController = TextEditingController();
  final _timeController = TextEditingController();
  final _addressController = TextEditingController();
  final _addressFocusNode = FocusNode();
  final _metroController = TextEditingController();
  final _cargoTypeController = TextEditingController();
  final _cargoWeightController = TextEditingController();
  final _floorController = TextEditingController();
  final _priceController = TextEditingController();
  Timer? _addressLookupTimer;
  int _hours = 4;
  int _workersCount = 2;
  bool _hasElevator = true;
  String _workerCategory = 'loader';
  String _clientType = 'individual';
  String _clientEmail = '';
  String _clientPhone = '';
  bool _isLoading = false;
  bool _isAddressLookupLoading = false;
  List<_AddressCandidate> _addressCandidates = const [];
  _AddressCandidate? _selectedAddress;
  String? _addressLookupError;
  bool _isAddressServiceUnavailable = false;

  @override
  void initState() {
    super.initState();
    _loadClientType();
  }

  @override
  void dispose() {
    _addressLookupTimer?.cancel();
    _cityController.dispose();
    _dateController.dispose();
    _timeController.dispose();
    _addressController.dispose();
    _addressFocusNode.dispose();
    _metroController.dispose();
    _cargoTypeController.dispose();
    _cargoWeightController.dispose();
    _floorController.dispose();
    _priceController.dispose();
    super.dispose();
  }

  void _loadClientType() {
    if (gpmApi.isApiMode) return;
    final raw = readDemoValue('gpm.client.profile.v1');
    if (raw == null) return;

    try {
      final data = jsonDecode(raw) as Map<String, dynamic>;
      final type = data['client_type']?.toString();
      if (type == 'legal' || type == 'individual') {
        _clientType = type!;
      }
      _clientEmail = data['email']?.toString().trim() ?? '';
      _clientPhone = data['phone']?.toString().trim() ?? '';
    } catch (_) {
      _clientType = 'individual';
      _clientEmail = '';
      _clientPhone = '';
    }
  }

  String? _requiredText(String? value, String message) {
    return value == null || value.trim().isEmpty ? message : null;
  }

  int? _optionalPositiveInt(TextEditingController controller) {
    final text = controller.text.trim();
    if (text.isEmpty) return null;
    final parsed = int.tryParse(text);
    return parsed == null || parsed < 0 ? null : parsed;
  }

  String? _optionalPrice(String? value) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return null;
    final parsed = int.tryParse(text);
    if (parsed == null || parsed < 0) return 'Укажите сумму числом';
    return null;
  }

  String? _optionalIntegerInRange(
    String? value, {
    required int min,
    required int max,
  }) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return null;

    final parsed = int.tryParse(text);
    if (parsed == null || parsed < min || parsed > max) {
      return 'Введите целое число от $min до $max';
    }
    return null;
  }

  void _scheduleAddressLookup(String value) {
    _addressLookupTimer?.cancel();
    _selectedAddress = null;
    _addressLookupError = null;

    final query = value.trim();
    if (query.length < 4) {
      setState(() {
        _addressCandidates = const [];
        _isAddressLookupLoading = false;
      });
      return;
    }

    setState(() {
      _isAddressLookupLoading = true;
    });

    _addressLookupTimer = Timer(const Duration(milliseconds: 650), () {
      _lookupAddress(query);
    });
  }

  Future<void> _lookupAddress(String rawQuery) async {
    final city = _cityController.text.trim();

    try {
      final rawCandidates = await gpmApi.suggestAddresses(
        query: rawQuery,
        city: city,
      );
      final candidates = rawCandidates
          .map(_AddressCandidate.fromJson)
          .whereType<_AddressCandidate>()
          .toList();

      if (!mounted || _addressController.text.trim() != rawQuery) return;

      setState(() {
        _addressCandidates = candidates;
        _isAddressServiceUnavailable = false;
        _addressLookupError = candidates.isEmpty
            ? 'Адрес не найден. Уточните город, улицу и дом.'
            : null;
        _isAddressLookupLoading = false;
      });
    } catch (error) {
      if (!mounted || _addressController.text.trim() != rawQuery) return;

      setState(() {
        _addressCandidates = const [];
        _isAddressServiceUnavailable = true;
        _addressLookupError =
            'Подсказки временно недоступны. Введите адрес вручную.';
        _isAddressLookupLoading = false;
      });
    }
  }

  void _selectAddress(_AddressCandidate candidate) {
    _addressLookupTimer?.cancel();
    if (!candidate.isComplete) {
      setState(() {
        _selectedAddress = null;
        _addressController.text = candidate.title;
        _addressController.selection = TextSelection.collapsed(
          offset: _addressController.text.length,
        );
        _addressCandidates = const [];
        _addressLookupError = 'Допишите номер дома';
        _isAddressLookupLoading = false;
      });
      _addressFocusNode.requestFocus();
      return;
    }
    setState(() {
      _selectedAddress = candidate;
      _addressController.text = candidate.title;
      _addressCandidates = const [];
      _addressLookupError = null;
      _isAddressLookupLoading = false;
    });
  }

  String? _validateAddress(String? value) {
    final message = _requiredText(value, 'Укажите адрес');
    if (message != null) return message;
    if (_selectedAddress == null && !_isAddressServiceUnavailable) {
      return 'Выберите адрес из вариантов, чтобы подтвердить точку на карте';
    }
    return null;
  }

  void _goBack() {
    if (widget.onBack != null) {
      widget.onBack!();
      return;
    }
    if (Navigator.canPop(context)) {
      Navigator.pop(context);
    }
  }

  DateTime? _parseScheduledAt() {
    final dateParts = _dateController.text.trim().split('.');
    final timeParts = _timeController.text.trim().split(':');
    if (dateParts.length != 3 || timeParts.length != 2) return null;

    final day = int.tryParse(dateParts[0]);
    final month = int.tryParse(dateParts[1]);
    final year = int.tryParse(dateParts[2]);
    final hour = int.tryParse(timeParts[0]);
    final minute = int.tryParse(timeParts[1]);
    if (day == null ||
        month == null ||
        year == null ||
        hour == null ||
        minute == null ||
        day < 1 ||
        day > 31 ||
        month < 1 ||
        month > 12 ||
        year < 1 ||
        year > 9999 ||
        hour < 0 ||
        hour > 23 ||
        minute < 0 ||
        minute > 59) {
      return null;
    }

    final parsed = DateTime(year, month, day, hour, minute);
    if (parsed.day != day || parsed.month != month || parsed.year != year) {
      return null;
    }
    return parsed;
  }

  String? _validateDate(String? value) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return 'Укажите дату';

    final parts = text.split('.');
    if (parts.length != 3) return 'Формат даты: 18.08.2026';

    final day = int.tryParse(parts[0]);
    final month = int.tryParse(parts[1]);
    final year = int.tryParse(parts[2]);
    if (day == null ||
        month == null ||
        year == null ||
        day < 1 ||
        day > 31 ||
        month < 1 ||
        month > 12 ||
        year < 1 ||
        year > 9999) {
      return 'Формат даты: 18.08.2026';
    }

    final parsed = DateTime(year, month, day);
    if (parsed.day != day || parsed.month != month || parsed.year != year) {
      return 'Укажите существующую дату';
    }
    return null;
  }

  String? _validateTime(String? value) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return 'Укажите время';

    final parts = text.split(':');
    if (parts.length != 2) return 'Формат времени: 14:30';

    final hour = int.tryParse(parts[0]);
    final minute = int.tryParse(parts[1]);
    if (hour == null ||
        minute == null ||
        hour < 0 ||
        hour > 23 ||
        minute < 0 ||
        minute > 59) {
      return 'Формат времени: 14:30';
    }

    final scheduledAt = _parseScheduledAt();
    if (scheduledAt == null) return null;

    final now = DateTime.now();
    if (scheduledAt.isBefore(now.add(const Duration(minutes: 30)))) {
      return 'Выберите дату и время минимум через 30 минут';
    }
    if (scheduledAt.isAfter(now.add(const Duration(days: 365)))) {
      return 'Заказ можно запланировать максимум на 1 год вперёд';
    }
    return null;
  }

  String _buildDescription() {
    return [
      'Вид груза: ${_cargoTypeController.text.trim()}',
      if (_cargoWeightController.text.trim().isNotEmpty)
        'Вес: ${_cargoWeightController.text.trim()} кг',
      if (_floorController.text.trim().isNotEmpty)
        'Этаж: ${_floorController.text.trim()}',
      'Лифт: ${_hasElevator ? 'есть' : 'нет'}',
    ].join('\n');
  }

  int get _recommendedPrice {
    final baseRate = _clientType == 'legal' ? 650 : 550;
    return _workersCount * _hours * baseRate;
  }

  Widget _buildCounters() {
    final hoursCounter = _BoundedCounter(
      label: 'Часы',
      value: _hours,
      min: 1,
      max: 24,
      onDecrement: () => setState(() {
        if (_hours > 1) _hours--;
      }),
      onIncrement: () => setState(() {
        if (_hours < 24) _hours++;
      }),
    );
    final workersCounter = _BoundedCounter(
      label: 'Исполнители',
      value: _workersCount,
      min: 1,
      max: 50,
      onDecrement: () => setState(() {
        if (_workersCount > 1) _workersCount--;
      }),
      onIncrement: () => setState(() {
        if (_workersCount < 50) _workersCount++;
      }),
    );

    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 360) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              hoursCounter,
              const SizedBox(height: 12),
              workersCounter,
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: hoursCounter),
            const SizedBox(width: 12),
            Expanded(child: workersCounter),
          ],
        );
      },
    );
  }

  Future<void> _submit() async {
    final scheduledAt = _parseScheduledAt();
    final countersAreValid = _hours >= 1 &&
        _hours <= 24 &&
        _workersCount >= 1 &&
        _workersCount <= 50;
    if (!_formKey.currentState!.validate() ||
        scheduledAt == null ||
        !countersAreValid) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content:
              Text('Проверьте поля, дату, время и количество исполнителей'),
        ),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final cargoType = _cargoTypeController.text.trim();
      final price = _optionalPositiveInt(_priceController);
      final result = await gpmApi.createOrder(
        title: cargoType.isEmpty ? 'Заказ грузчиков' : cargoType,
        description: _buildDescription(),
        address: _addressController.text.trim(),
        hours: _hours,
        workersCount: _workersCount,
        clientEmail: _clientEmail,
        clientPhone: _clientPhone,
        scheduledAt: scheduledAt.toUtc().toIso8601String(),
        city: _cityController.text.trim(),
        source: GpmApiService.sourceManual,
        metro: _metroController.text.trim(),
        national: 'every',
        minTime: _hours,
        individualPrice: _clientType == 'individual' ? price : null,
        legalPrice: _clientType == 'legal' ? price : null,
        nationality: 'any',
        workerCategory: _workerCategory,
        workMode: 'rate',
        timezone: 'Europe/Moscow',
        addressStreet:
            _selectedAddress?.street ?? _addressController.text.trim(),
        addressNumber: _selectedAddress?.houseNumber,
        addressLat: _selectedAddress?.latitude,
        addressLon: _selectedAddress?.longitude,
      );

      if (result['success'] != true) {
        throw StateError(
          result['error']?.toString() ?? 'Не удалось создать заказ',
        );
      }

      if (widget.publishImmediately) {
        final statusUpdated = await gpmApi.updateOrderStatus(
          result['orderId'].toString(),
          'PROCESSED',
        );
        if (!statusUpdated) {
          throw StateError(
            'Заказ создан, но публикация не подтверждена. Обновите список и повторите.',
          );
        }
      }

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.publishImmediately
                ? 'Заказ опубликован и доступен исполнителям'
                : 'Заказ создан и отправлен на модерацию',
          ),
          backgroundColor: Colors.green,
        ),
      );

      if (widget.closeOnSuccess) {
        Navigator.pop(context, true);
        return;
      }

      _addressController.clear();
      _cityController.text = 'Москва';
      _dateController.clear();
      _timeController.clear();
      _metroController.clear();
      _cargoTypeController.clear();
      _cargoWeightController.clear();
      _floorController.clear();
      _priceController.clear();
      setState(() {
        _hours = 4;
        _workersCount = 2;
        _hasElevator = true;
        _workerCategory = 'loader';
        _selectedAddress = null;
        _addressCandidates = const [];
        _addressLookupError = null;
        _isAddressServiceUnavailable = false;
        _isAddressLookupLoading = false;
      });
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка: $error')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: GpmColors.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: GpmColors.line),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        IconButton(
                          tooltip: 'Назад',
                          onPressed: _goBack,
                          icon: const Icon(Icons.arrow_back),
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            widget.title.toUpperCase(),
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Оставьте заявку: укажите время, адрес, груз и бюджет.',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _cityController,
                decoration: const InputDecoration(
                  labelText: 'Город',
                  border: OutlineInputBorder(),
                ),
                validator: (value) => _requiredText(value, 'Укажите город'),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _dateController,
                      keyboardType: TextInputType.datetime,
                      decoration: const InputDecoration(
                        labelText: 'Дата',
                        hintText: '18.08.2026',
                        prefixIcon: Icon(Icons.calendar_today),
                        border: OutlineInputBorder(),
                      ),
                      validator: _validateDate,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextFormField(
                      controller: _timeController,
                      keyboardType: TextInputType.datetime,
                      decoration: const InputDecoration(
                        labelText: 'Время',
                        hintText: '14:30',
                        prefixIcon: Icon(Icons.schedule),
                        border: OutlineInputBorder(),
                      ),
                      validator: _validateTime,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Формат: дата ДД.ММ.ГГГГ, время 24 часа. '
                'Не раньше чем через 30 минут и не позже чем через год.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _cargoTypeController,
                decoration: const InputDecoration(
                  labelText: 'Вид груза',
                  hintText: 'Например: мебель, техника, коробки',
                  border: OutlineInputBorder(),
                ),
                validator: (value) => _requiredText(value, 'Укажите вид груза'),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _cargoWeightController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Вес, кг (необязательно)',
                        hintText: 'Например: 300',
                        border: OutlineInputBorder(),
                      ),
                      validator: (value) => _optionalIntegerInRange(
                        value,
                        min: 1,
                        max: 100000,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextFormField(
                      controller: _floorController,
                      keyboardType: const TextInputType.numberWithOptions(
                        signed: true,
                      ),
                      decoration: const InputDecoration(
                        labelText: 'Этаж (необязательно)',
                        hintText: 'Например: 4',
                        border: OutlineInputBorder(),
                      ),
                      validator: (value) => _optionalIntegerInRange(
                        value,
                        min: -5,
                        max: 200,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Есть лифт'),
                value: _hasElevator,
                onChanged: (value) => setState(() => _hasElevator = value),
              ),
              const SizedBox(height: 12),
              _buildCounters(),
              const SizedBox(height: 12),
              TextFormField(
                controller: _addressController,
                focusNode: _addressFocusNode,
                decoration: InputDecoration(
                  labelText: 'Адрес',
                  hintText: 'Начните вводить улицу и дом',
                  border: const OutlineInputBorder(),
                  prefixIcon: const Icon(Icons.location_on_outlined),
                  suffixIcon: _isAddressLookupLoading
                      ? const Padding(
                          padding: EdgeInsets.all(14),
                          child: SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        )
                      : null,
                ),
                onChanged: _scheduleAddressLookup,
                validator: _validateAddress,
              ),
              if (_addressLookupError != null) ...[
                const SizedBox(height: 8),
                Text(
                  _addressLookupError!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              if (_addressCandidates.isNotEmpty) ...[
                const SizedBox(height: 8),
                _AddressCandidatesList(
                  candidates: _addressCandidates,
                  onSelected: _selectAddress,
                ),
              ],
              if (_selectedAddress != null) ...[
                const SizedBox(height: 12),
                _SelectedAddressPreview(candidate: _selectedAddress!),
              ],
              const SizedBox(height: 12),
              TextFormField(
                controller: _metroController,
                decoration: const InputDecoration(
                  labelText: 'Метро (необязательно)',
                  hintText: 'Например: Динамо, если рядом есть метро',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              const ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(Icons.verified_user_outlined),
                title: Text('Право на законную работу'),
                subtitle: Text(
                  'Гражданство не используется как общий фильтр. Необходимые '
                  'документы должен проверять серверный процесс верификации.',
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _workerCategory,
                decoration: const InputDecoration(
                  labelText: 'Категория рабочих',
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: 'loader', child: Text('Грузчики')),
                  DropdownMenuItem(value: 'rigger', child: Text('Такелажники')),
                  DropdownMenuItem(
                    value: 'assembler',
                    child: Text('Сборщики / разборщики'),
                  ),
                  DropdownMenuItem(
                    value: 'mover',
                    child: Text('Разнорабочие'),
                  ),
                  DropdownMenuItem(
                    value: 'packer',
                    child: Text('Упаковщики / комплектовщики'),
                  ),
                ],
                onChanged: (value) {
                  if (value == null) return;
                  setState(() => _workerCategory = value);
                },
              ),
              const SizedBox(height: 12),
              _ClientPriceSection(
                clientType: _clientType,
                controller: _priceController,
                validatePrice: _optionalPrice,
                recommendedPrice: _recommendedPrice,
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: _isLoading ? null : _submit,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: _isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : Text(widget.submitText,
                        style: const TextStyle(fontSize: 16)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BoundedCounter extends StatelessWidget {
  final String label;
  final int value;
  final int min;
  final int max;
  final VoidCallback onDecrement;
  final VoidCallback onIncrement;

  const _BoundedCounter({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.onDecrement,
    required this.onIncrement,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: '$label: $value. Допустимо от $min до $max.',
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: GpmColors.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: GpmColors.line),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '$label ($min–$max)',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 2),
              Row(
                children: [
                  IconButton(
                    tooltip: 'Уменьшить: $label',
                    onPressed: value > min ? onDecrement : null,
                    icon: const Icon(Icons.remove),
                  ),
                  Expanded(
                    child: Text(
                      '$value',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Увеличить: $label',
                    onPressed: value < max ? onIncrement : null,
                    icon: const Icon(Icons.add),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ClientPriceSection extends StatelessWidget {
  final String clientType;
  final TextEditingController controller;
  final FormFieldValidator<String> validatePrice;
  final int recommendedPrice;

  const _ClientPriceSection({
    required this.clientType,
    required this.controller,
    required this.validatePrice,
    required this.recommendedPrice,
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
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.payments_outlined),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Предполагаемая стоимость',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'Рекомендация: от $recommendedPrice ₽',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: controller,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: clientType == 'legal'
                    ? 'Бюджет по счету, ₽'
                    : 'Бюджет к оплате, ₽',
                hintText: recommendedPrice.toString(),
                border: OutlineInputBorder(),
              ),
              validator: validatePrice,
            ),
          ],
        ),
      ),
    );
  }
}

class _AddressCandidate {
  final String title;
  final String details;
  final String street;
  final String? houseNumber;
  final double? latitude;
  final double? longitude;
  final bool isComplete;

  const _AddressCandidate({
    required this.title,
    required this.details,
    required this.street,
    required this.houseNumber,
    required this.latitude,
    required this.longitude,
    required this.isComplete,
  });

  static _AddressCandidate? fromJson(Map<String, dynamic> json) {
    final title = json['title']?.toString().trim() ?? '';
    if (title.isEmpty) return null;
    final latitude = double.tryParse(json['latitude']?.toString() ?? '');
    final longitude = double.tryParse(json['longitude']?.toString() ?? '');
    final houseNumber = json['house_number']?.toString().trim();

    return _AddressCandidate(
      title: title,
      details: json['details']?.toString().trim() ?? title,
      street: json['street']?.toString().trim() ?? title,
      houseNumber: houseNumber?.isNotEmpty == true ? houseNumber : null,
      latitude: latitude,
      longitude: longitude,
      isComplete: json['complete'] == true &&
          latitude != null &&
          longitude != null &&
          houseNumber?.isNotEmpty == true,
    );
  }
}

class _AddressCandidatesList extends StatelessWidget {
  final List<_AddressCandidate> candidates;
  final ValueChanged<_AddressCandidate> onSelected;

  const _AddressCandidatesList({
    required this.candidates,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        children: [
          for (var index = 0; index < candidates.length; index++) ...[
            if (index > 0) const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.place_outlined),
              title: Text(candidates[index].title),
              subtitle: Text(
                candidates[index].details,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              trailing: Icon(
                candidates[index].isComplete
                    ? Icons.check_circle_outline
                    : Icons.arrow_forward_ios,
                size: candidates[index].isComplete ? 24 : 16,
              ),
              onTap: () => onSelected(candidates[index]),
            ),
          ],
        ],
      ),
    );
  }
}

class _SelectedAddressPreview extends StatelessWidget {
  final _AddressCandidate candidate;

  const _SelectedAddressPreview({required this.candidate});

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: GpmColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            height: 108,
            decoration: const BoxDecoration(
              color: GpmColors.page,
              borderRadius: BorderRadius.vertical(top: Radius.circular(8)),
            ),
            alignment: Alignment.center,
            child: const Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.location_on_outlined, size: 36),
                SizedBox(height: 6),
                Text(
                  'Координаты адреса определены',
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.verified,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 8),
                    const Expanded(
                      child: Text(
                        'Локация подтверждена',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(candidate.details),
                const SizedBox(height: 6),
                Text(
                  '${candidate.latitude!.toStringAsFixed(6)}, '
                  '${candidate.longitude!.toStringAsFixed(6)}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

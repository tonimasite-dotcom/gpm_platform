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
  bool _isRussianCitizenshipRequired = true;
  bool _hasElevator = true;
  String _workerCategory = 'loader';
  String _clientType = 'individual';
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
    final raw = readDemoValue('gpm.client.profile.v1');
    if (raw == null) return;

    try {
      final data = jsonDecode(raw) as Map<String, dynamic>;
      final type = data['client_type']?.toString();
      if (type == 'legal' || type == 'individual') {
        _clientType = type!;
      }
    } catch (_) {
      _clientType = 'individual';
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
        hour > 23 ||
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
    return _parseScheduledAt() == null ? 'Формат даты: 18.08.2026' : null;
  }

  String? _validateTime(String? value) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return 'Укажите время';
    return _parseScheduledAt() == null ? 'Формат времени: 14:30' : null;
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

  Future<void> _submit() async {
    final scheduledAt = _parseScheduledAt();
    if (!_formKey.currentState!.validate() || scheduledAt == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Заполните поля, дату и время'),
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
        clientEmail: 'client@gpm.ru',
        clientPhone: '',
        scheduledAt: scheduledAt.toUtc().toIso8601String(),
        city: _cityController.text.trim(),
        source: widget.publishImmediately
            ? GpmApiService.sourceExternal
            : GpmApiService.sourceManual,
        metro: _metroController.text.trim(),
        national: _isRussianCitizenshipRequired ? 'yes' : 'every',
        minTime: _hours,
        individualPrice: _clientType == 'individual' ? price : null,
        legalPrice: _clientType == 'legal' ? price : null,
        nationality: _isRussianCitizenshipRequired ? 'ru' : 'any',
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
        await gpmApi.updateOrderStatus(
          result['orderId'].toString(),
          'PROCESSED',
        );
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
        _isRussianCitizenshipRequired = true;
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
                'Формат: дата ДД.ММ.ГГГГ, время 24 часа.',
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
                        labelText: 'Вес, кг',
                        hintText: 'Например: 300',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextFormField(
                      controller: _floorController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Этаж',
                        hintText: 'Например: 4',
                        border: OutlineInputBorder(),
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
              Row(
                children: [
                  const Text('Часов:'),
                  IconButton(
                    onPressed: () {
                      setState(() {
                        if (_hours > 1) _hours--;
                      });
                    },
                    icon: const Icon(Icons.remove),
                  ),
                  Text(
                    '$_hours',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  IconButton(
                    onPressed: () {
                      setState(() {
                        _hours++;
                      });
                    },
                    icon: const Icon(Icons.add),
                  ),
                  const Spacer(),
                  const Text('Грузчиков:'),
                  IconButton(
                    onPressed: () {
                      setState(() {
                        if (_workersCount > 1) _workersCount--;
                      });
                    },
                    icon: const Icon(Icons.remove),
                  ),
                  Text(
                    '$_workersCount',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  IconButton(
                    onPressed: () {
                      setState(() {
                        _workersCount++;
                      });
                    },
                    icon: const Icon(Icons.add),
                  ),
                ],
              ),
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
                  labelText: 'Метро',
                  hintText: 'Например: Динамо',
                  border: OutlineInputBorder(),
                ),
                validator: (value) => _requiredText(value, 'Укажите метро'),
              ),
              const SizedBox(height: 12),
              const Text(
                'Гражданство РФ:',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(value: true, label: Text('Да')),
                  ButtonSegment(value: false, label: Text('Необязательно')),
                ],
                selected: {_isRussianCitizenshipRequired},
                onSelectionChanged: (selection) =>
                    setState(
                  () => _isRussianCitizenshipRequired = selection.first,
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
                labelText:
                    clientType == 'legal' ? 'Бюджет по счету, ₽' : 'Бюджет к оплате, ₽',
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

  String get mapImageUrl {
    final lat = latitude!.toStringAsFixed(6);
    final lon = longitude!.toStringAsFixed(6);
    return 'https://staticmap.openstreetmap.de/staticmap.php'
        '?center=$lat,$lon&zoom=16&size=720x260&markers=$lat,$lon,red-pushpin';
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
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
            child: Image.network(
              candidate.mapImageUrl,
              height: 180,
              fit: BoxFit.cover,
              errorBuilder: (context, error, stackTrace) {
                return Container(
                  height: 180,
                  color: GpmColors.page,
                  alignment: Alignment.center,
                  child: const Icon(Icons.map_outlined, size: 44),
                );
              },
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

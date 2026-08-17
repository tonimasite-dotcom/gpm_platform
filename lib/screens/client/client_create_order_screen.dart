import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../main.dart' show bitrix24;
import '../../services/demo_storage.dart';
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

  @override
  void initState() {
    super.initState();
    _loadClientType();
  }

  @override
  void dispose() {
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
    final query = city.isEmpty ? rawQuery : '$city, $rawQuery';
    final uri = Uri.https(
      'nominatim.openstreetmap.org',
      '/search',
      {
        'format': 'jsonv2',
        'addressdetails': '1',
        'limit': '6',
        'accept-language': 'ru',
        'countrycodes': 'ru',
        'q': query,
      },
    );

    try {
      final response = await http.get(
        uri,
        headers: const {'Accept': 'application/json'},
      );
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError('address service returned ${response.statusCode}');
      }

      final decoded = jsonDecode(response.body);
      final candidates = decoded is List
          ? decoded
              .whereType<Map<String, dynamic>>()
              .map(_AddressCandidate.fromJson)
              .whereType<_AddressCandidate>()
              .toList()
          : <_AddressCandidate>[];

      if (!mounted || _addressController.text.trim() != rawQuery) return;

      setState(() {
        _addressCandidates = candidates;
        _addressLookupError = candidates.isEmpty
            ? 'Адрес не найден. Уточните город, улицу и дом.'
            : null;
        _isAddressLookupLoading = false;
      });
    } catch (error) {
      if (!mounted || _addressController.text.trim() != rawQuery) return;

      setState(() {
        _addressCandidates = const [];
        _addressLookupError = 'Не удалось проверить адрес по картам: $error';
        _isAddressLookupLoading = false;
      });
    }
  }

  void _selectAddress(_AddressCandidate candidate) {
    _addressLookupTimer?.cancel();
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
    if (_selectedAddress == null) {
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

  Iterable<String> _addressOptions(TextEditingValue value) {
    final query = value.text.trim().toLowerCase();
    if (query.length < 2) return const Iterable<String>.empty();

    final city = _cityController.text.trim();
    final cityPrefix = city.isEmpty ? '' : '$city, ';

    return _moscowAddressSuggestions
        .where((address) => address.toLowerCase().contains(query))
        .map((address) => '$cityPrefix$address')
        .take(8);
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
      final result = await bitrix24.createOrder(
        title: cargoType.isEmpty ? 'Заказ грузчиков' : cargoType,
        description: _buildDescription(),
        address: _addressController.text.trim(),
        hours: _hours,
        workersCount: _workersCount,
        clientEmail: 'client@gpm.ru',
        clientPhone: '',
        scheduledAt: scheduledAt.toUtc().toIso8601String(),
        city: _cityController.text.trim(),
        source: widget.publishImmediately ? 'crm' : 'manual',
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
        await bitrix24.updateOrderStatus(
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
              RawAutocomplete<String>(
                textEditingController: _addressController,
                focusNode: _addressFocusNode,
                optionsBuilder: _addressOptions,
                onSelected: (value) {
                  _addressController.text = value;
                  _scheduleAddressLookup(value);
                },
                fieldViewBuilder: (
                  context,
                  textEditingController,
                  focusNode,
                  onFieldSubmitted,
                ) {
                  return TextFormField(
                    controller: textEditingController,
                    focusNode: focusNode,
                    decoration: const InputDecoration(
                      labelText: 'Адрес',
                      hintText: 'Начните вводить улицу или проспект',
                      border: OutlineInputBorder(),
                    ),
                    onChanged: _scheduleAddressLookup,
                    validator: _validateAddress,
                  );
                },
                optionsViewBuilder: (context, onSelected, options) {
                  return Align(
                    alignment: Alignment.topLeft,
                    child: Material(
                      elevation: 6,
                      borderRadius: BorderRadius.circular(8),
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(
                          maxHeight: 280,
                          maxWidth: 720,
                        ),
                        child: ListView.separated(
                          padding: EdgeInsets.zero,
                          shrinkWrap: true,
                          itemCount: options.length,
                          separatorBuilder: (_, __) =>
                              const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final option = options.elementAt(index);
                            return ListTile(
                              dense: true,
                              leading: const Icon(Icons.place_outlined),
                              title: Text(option),
                              onTap: () => onSelected(option),
                            );
                          },
                        ),
                      ),
                    ),
                  );
                },
              ),
              if (_isAddressLookupLoading) ...[
                const SizedBox(height: 8),
                const LinearProgressIndicator(minHeight: 2),
              ],
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
  final double latitude;
  final double longitude;

  const _AddressCandidate({
    required this.title,
    required this.details,
    required this.street,
    required this.houseNumber,
    required this.latitude,
    required this.longitude,
  });

  static _AddressCandidate? fromJson(Map<String, dynamic> json) {
    final lat = double.tryParse(json['lat']?.toString() ?? '');
    final lon = double.tryParse(json['lon']?.toString() ?? '');
    final displayName = json['display_name']?.toString().trim();
    if (lat == null || lon == null || displayName == null || displayName.isEmpty) {
      return null;
    }

    final address = json['address'];
    final street = address is Map ? address['road']?.toString().trim() : null;
    final houseNumber =
        address is Map ? address['house_number']?.toString().trim() : null;
    final building =
        address is Map ? address['building']?.toString().trim() : null;
    final title = address is Map
        ? [street, houseNumber, building]
            .where((part) => part != null && part.toString().trim().isNotEmpty)
            .map((part) => part.toString().trim())
            .join(', ')
        : '';

    return _AddressCandidate(
      title: title.isEmpty ? displayName : title,
      details: displayName,
      street: street?.isNotEmpty == true ? street! : displayName,
      houseNumber: houseNumber?.isNotEmpty == true ? houseNumber : building,
      latitude: lat,
      longitude: lon,
    );
  }

  String get mapImageUrl {
    final lat = latitude.toStringAsFixed(6);
    final lon = longitude.toStringAsFixed(6);
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
              trailing: const Icon(Icons.check_circle_outline),
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
                  '${candidate.latitude.toStringAsFixed(6)}, '
                  '${candidate.longitude.toStringAsFixed(6)}',
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
const _moscowAddressSuggestions = [
  'Ленинградский проспект',
  'Ленинградское шоссе',
  'Варшавское шоссе',
  'Каширское шоссе',
  'Дмитровское шоссе',
  'Алтуфьевское шоссе',
  'Волгоградский проспект',
  'Кутузовский проспект',
  'Мичуринский проспект',
  'Нахимовский проспект',
  'Рязанский проспект',
  'Севастопольский проспект',
  'Ленинский проспект',
  'Проспект Мира',
  'Проспект Вернадского',
  'Проспект Андропова',
  'Проспект Маршала Жукова',
  'Улица Новый Арбат',
  'Улица Арбат',
  'Тверская улица',
  '1-я Тверская-Ямская улица',
  'Садовая-Кудринская улица',
  'Садовая-Самотечная улица',
  'Большая Садовая улица',
  'Пятницкая улица',
  'Большая Ордынка',
  'Мясницкая улица',
  'Покровка',
  'Сретенка',
  'Неглинная улица',
  'Новая Басманная улица',
  'Старая Басманная улица',
  'Бауманская улица',
  'Большая Семеновская улица',
  'Электрозаводская улица',
  'Профсоюзная улица',
  'Вавилова улица',
  'Улица Гарибальди',
  'Улица Обручева',
  'Улица Академика Королева',
  'Улица Академика Янгеля',
  'Улица 1905 года',
  'Улица Красная Пресня',
  'Пресненская набережная',
  'Шмитовский проезд',
  'Хорошевское шоссе',
  'Звенигородское шоссе',
  'Бутырская улица',
  'Новослободская улица',
  'Сущевский Вал',
  'Складочная улица',
  'Шереметьевская улица',
  'Люблинская улица',
  'Шоссейная улица',
  'Люблинская улица',
  'Коровинское шоссе',
  'Пятницкое шоссе',
  'Ярославское шоссе',
  'Щелковское шоссе',
  'Открытое шоссе',
  'Большая Черкизовская улица',
  'Измайловское шоссе',
  'Перовская улица',
  'Зеленый проспект',
  'Свободный проспект',
  'Шоссе Энтузиастов',
  'Авиамоторная улица',
  'Нижегородская улица',
  'Рогожский Вал',
  'Таганская улица',
  'Марксистская улица',
  'Павелецкая площадь',
  'Дербеневская набережная',
  'Дубининская улица',
  'Большая Тульская улица',
  'Автозаводская улица',
  'Велозаводская улица',
  'Кантемировская улица',
  'Промышленная улица',
  'Дорожная улица',
  'Подольских Курсантов улица',
  'Можайское шоссе',
  'Рублевское шоссе',
  'Аминьевское шоссе',
  'Очаковское шоссе',
  'Рябиновая улица',
  'Генерала Дорохова улица',
  'Минская улица',
  'Мосфильмовская улица',
  'Ломоносовский проспект',
  'Университетский проспект',
  'Комсомольский проспект',
  'Фрунзенская набережная',
  'Большая Пироговская улица',
  'Хамовнический Вал',
  'Остоженка',
  'Пречистенка',
];

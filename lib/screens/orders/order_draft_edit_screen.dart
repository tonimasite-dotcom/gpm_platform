import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../theme/gpm_theme.dart';

class OrderDraftEditScreen extends StatefulWidget {
  final Map<String, dynamic> order;

  const OrderDraftEditScreen({super.key, required this.order});

  @override
  State<OrderDraftEditScreen> createState() => _OrderDraftEditScreenState();
}

class _OrderDraftEditScreenState extends State<OrderDraftEditScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _title;
  late final TextEditingController _city;
  late final TextEditingController _date;
  late final TextEditingController _time;
  late final TextEditingController _address;
  late final TextEditingController _metro;
  late final TextEditingController _workersCount;
  late final TextEditingController _hours;
  late final TextEditingController _minTime;
  late final TextEditingController _description;
  late final TextEditingController _shiftDescription;
  late final TextEditingController _pricePerHour;
  late final TextEditingController _priceRegular;
  late final TextEditingController _priceState;
  late final TextEditingController _individualPrice;
  late final TextEditingController _legalPrice;
  late final TextEditingController _additionalInfo;
  late String _national;
  late String _workMode;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final order = widget.order;
    final scheduledAt = DateTime.tryParse(
      order['scheduled_at']?.toString() ?? '',
    )?.toLocal();
    _title = _textController(order['title']);
    _city = _textController(
      _value(order['city']).isNotEmpty
          ? order['city']
          : _cityFromAddress(order['address']),
    );
    _date = TextEditingController(
      text: scheduledAt == null
          ? ''
          : '${_two(scheduledAt.day)}.${_two(scheduledAt.month)}.${scheduledAt.year}',
    );
    _time = TextEditingController(
      text: scheduledAt == null
          ? ''
          : '${_two(scheduledAt.hour)}:${_two(scheduledAt.minute)}',
    );
    _address = _textController(order['address']);
    _metro = _textController(order['metro']);
    _workersCount = _textController(order['workers_count']);
    _hours = _textController(order['hours']);
    _minTime = _textController(order['min_time'] ?? order['hours']);
    _description = _textController(order['description']);
    _shiftDescription = _textController(order['shift_description']);
    _pricePerHour = _textController(order['price_per_hour']);
    _priceRegular = _textController(order['price_regular']);
    _priceState = _textController(order['price_state']);
    _individualPrice = _textController(order['individual_price']);
    _legalPrice = _textController(order['legal_price']);
    _additionalInfo = _textController(order['additional_info']);
    final national = _value(order['national']);
    _national = national == 'yes' || national == 'no' ? national : 'every';
    _workMode = _value(order['work_mode']) == 'shift' ? 'shift' : 'rate';
  }

  @override
  void dispose() {
    for (final controller in [
      _title,
      _city,
      _date,
      _time,
      _address,
      _metro,
      _workersCount,
      _hours,
      _minTime,
      _description,
      _shiftDescription,
      _pricePerHour,
      _priceRegular,
      _priceState,
      _individualPrice,
      _legalPrice,
      _additionalInfo,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  TextEditingController _textController(dynamic value) =>
      TextEditingController(text: _value(value));

  String _value(dynamic value) => value?.toString().trim() ?? '';

  String _two(int value) => value.toString().padLeft(2, '0');

  String _cityFromAddress(dynamic value) {
    final firstPart = _value(value).split(',').first.trim();
    final lower = firstPart.toLowerCase().replaceAll('ё', 'е');
    for (final prefix in const ['город ', 'г. ', 'г ']) {
      if (lower.startsWith(prefix)) {
        return firstPart.substring(prefix.length).trim();
      }
    }
    return '';
  }

  String? _required(String? value) =>
      value == null || value.trim().isEmpty ? 'Заполните поле' : null;

  String? _integer(
    String? value, {
    required int min,
    required int max,
  }) {
    final parsed = int.tryParse(value?.trim() ?? '');
    if (parsed == null || parsed < min || parsed > max) {
      return 'Введите число от $min до $max';
    }
    return null;
  }

  String? _optionalPrice(String? value) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return null;
    final parsed = int.tryParse(text);
    return parsed == null || parsed < 0 ? 'Введите сумму числом' : null;
  }

  DateTime? _scheduledAt() {
    final date = _date.text.trim().split('.');
    final time = _time.text.trim().split(':');
    if (date.length != 3 || time.length != 2) return null;
    final day = int.tryParse(date[0]);
    final month = int.tryParse(date[1]);
    final year = int.tryParse(date[2]);
    final hour = int.tryParse(time[0]);
    final minute = int.tryParse(time[1]);
    if ([day, month, year, hour, minute].any((value) => value == null)) {
      return null;
    }
    final result = DateTime(year!, month!, day!, hour!, minute!);
    if (result.year != year ||
        result.month != month ||
        result.day != day ||
        result.hour != hour ||
        result.minute != minute) {
      return null;
    }
    return result;
  }

  String? _dateTimeValidator(String? _) {
    final scheduledAt = _scheduledAt();
    if (scheduledAt == null) return 'Формат: ДД.ММ.ГГГГ и ЧЧ:ММ';
    final now = DateTime.now();
    if (scheduledAt.isBefore(now.add(const Duration(minutes: 30)))) {
      return 'Минимум через 30 минут';
    }
    if (scheduledAt.isAfter(now.add(const Duration(days: 366)))) {
      return 'Не более чем на год вперёд';
    }
    return null;
  }

  int? _optionalInt(TextEditingController controller) {
    final text = controller.text.trim();
    return text.isEmpty ? null : int.tryParse(text);
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final scheduledAt = _scheduledAt();
    if (scheduledAt == null) return;

    setState(() => _saving = true);
    final result = await gpmApi.updateOrderDraft(
      widget.order['id'].toString(),
      {
        'title': _title.text.trim(),
        'city': _city.text.trim(),
        'scheduled_at': scheduledAt.toUtc().toIso8601String(),
        'address': _address.text.trim(),
        'metro': _metro.text.trim(),
        'workers_count': int.parse(_workersCount.text.trim()),
        'hours': int.parse(_hours.text.trim()),
        'min_time': int.parse(_minTime.text.trim()),
        'description': _description.text.trim(),
        'national': _national,
        'work_mode': _workMode,
        'shift_description': _shiftDescription.text.trim(),
        'price_per_hour': _optionalInt(_pricePerHour),
        'price_regular': _optionalInt(_priceRegular),
        'price_state': _optionalInt(_priceState),
        'individual_price': _optionalInt(_individualPrice),
        'legal_price': _optionalInt(_legalPrice),
        'additional_info': _additionalInfo.text.trim(),
      },
    );

    if (!mounted) return;
    setState(() => _saving = false);
    final success = result['success'] == true;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          success
              ? 'Изменения сохранены'
              : result['error']?.toString() ?? 'Не удалось сохранить изменения',
        ),
        backgroundColor: success ? Colors.green : Colors.red,
      ),
    );
    if (success) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final source = _value(widget.order['source']).toLowerCase();
    final isExternal = source == 'external' || source == 'crm';
    return Scaffold(
      appBar: AppBar(title: const Text('Редактирование заявки')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: GpmColors.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: GpmColors.line),
              ),
              child: Text(
                'Заявка № ${widget.order['external_order_id'] ?? widget.order['id']}\n'
                '${isExternal ? 'Источник: CRM. Номер и назначенный логист не изменяются.' : 'Источник: приложение.'}',
              ),
            ),
            const SizedBox(height: 16),
            _field(_title, 'Название / характер работ', validator: _required),
            _field(_city, 'Город', validator: _required),
            Row(
              children: [
                Expanded(
                  child: _field(
                    _date,
                    'Дата, ДД.ММ.ГГГГ',
                    validator: _dateTimeValidator,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _field(
                    _time,
                    'Время, ЧЧ:ММ',
                    validator: _dateTimeValidator,
                  ),
                ),
              ],
            ),
            _field(_address, 'Адрес', validator: _required),
            _field(_metro, 'Метро'),
            Row(
              children: [
                Expanded(
                  child: _field(
                    _workersCount,
                    'Количество людей',
                    keyboardType: TextInputType.number,
                    validator: (value) => _integer(value, min: 1, max: 100),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _field(
                    _hours,
                    'Часы',
                    keyboardType: TextInputType.number,
                    validator: (value) => _integer(value, min: 1, max: 24),
                  ),
                ),
              ],
            ),
            _field(
              _minTime,
              'Минимальное время оплаты, ч',
              keyboardType: TextInputType.number,
              validator: (value) => _integer(value, min: 1, max: 24),
            ),
            DropdownButtonFormField<String>(
              key: const Key('order-nationality-field'),
              initialValue: _national,
              decoration: const InputDecoration(
                labelText: 'Гражданство исполнителя',
              ),
              items: const [
                DropdownMenuItem(value: 'yes', child: Text('РФ')),
                DropdownMenuItem(value: 'no', child: Text('Не РФ')),
                DropdownMenuItem(value: 'every', child: Text('Необязательно')),
              ],
              onChanged: (value) => setState(() => _national = value!),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _workMode,
              decoration: const InputDecoration(labelText: 'Режим работы'),
              items: const [
                DropdownMenuItem(value: 'rate', child: Text('Ставка')),
                DropdownMenuItem(value: 'shift', child: Text('Смена')),
              ],
              onChanged: (value) => setState(() => _workMode = value!),
            ),
            const SizedBox(height: 12),
            _field(_description, 'Описание', maxLines: 3),
            if (_workMode == 'shift')
              _field(_shiftDescription, 'Описание смены', maxLines: 3),
            const SizedBox(height: 4),
            const Text(
              'Стоимость и ставки',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            _priceField(_individualPrice, 'Стоимость для физлиц'),
            _priceField(_legalPrice, 'Стоимость для юрлиц'),
            _priceField(_priceRegular, 'Ставка: постоянный график'),
            _priceField(_priceState, 'Ставка: свободный график'),
            _priceField(_pricePerHour, 'Ставка: наёмник'),
            _field(_additionalInfo, 'Дополнительная информация', maxLines: 3),
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
              label: const Text('Сохранить изменения'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _priceField(TextEditingController controller, String label) => _field(
        controller,
        label,
        keyboardType: TextInputType.number,
        validator: _optionalPrice,
      );

  Widget _field(
    TextEditingController controller,
    String label, {
    String? Function(String?)? validator,
    TextInputType? keyboardType,
    int maxLines = 1,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        decoration: InputDecoration(labelText: label),
        validator: validator,
        keyboardType: keyboardType,
        maxLines: maxLines,
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../../main.dart' show bitrix24;
import '../../theme/gpm_theme.dart';

class ClientCreateOrderScreen extends StatefulWidget {
  final bool publishImmediately;
  final bool closeOnSuccess;
  final String title;
  final String submitText;

  const ClientCreateOrderScreen({
    super.key,
    this.publishImmediately = false,
    this.closeOnSuccess = false,
    this.title = 'Создание заказа',
    this.submitText = 'Создать заказ',
  });

  @override
  State<ClientCreateOrderScreen> createState() =>
      _ClientCreateOrderScreenState();
}

class _ClientCreateOrderScreenState extends State<ClientCreateOrderScreen> {
  final _formKey = GlobalKey<FormState>();
  final _cityController = TextEditingController(text: 'Москва');
  final _orderNumberController = TextEditingController();
  final _addressController = TextEditingController();
  final _addressFocusNode = FocusNode();
  final _metroController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _shiftDescriptionController = TextEditingController();
  final _regularRateController = TextEditingController(text: '450');
  final _freeScheduleRateController = TextEditingController(text: '450');
  final _workerRateController = TextEditingController(text: '400');
  final _minPayController = TextEditingController(text: '4');
  DateTime? _dateTime;
  int _hours = 4;
  int _workersCount = 2;
  bool _isRussianCitizenshipRequired = true;
  String _workMode = 'shift';
  String _workerCategory = 'loader';
  bool _isLoading = false;

  @override
  void dispose() {
    _cityController.dispose();
    _orderNumberController.dispose();
    _addressController.dispose();
    _addressFocusNode.dispose();
    _metroController.dispose();
    _descriptionController.dispose();
    _shiftDescriptionController.dispose();
    _regularRateController.dispose();
    _freeScheduleRateController.dispose();
    _workerRateController.dispose();
    _minPayController.dispose();
    super.dispose();
  }

  String? _requiredText(String? value, String message) {
    return value == null || value.trim().isEmpty ? message : null;
  }

  String? _requiredPositiveInt(String? value, String message) {
    final parsed = int.tryParse(value?.trim() ?? '');
    return parsed == null || parsed <= 0 ? message : null;
  }

  int _requiredInt(TextEditingController controller) {
    return int.parse(controller.text.trim());
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

  Future<void> _pickDateTime() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 30)),
    );
    if (date == null || !mounted) return;

    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(now.add(const Duration(hours: 2))),
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
          child: child!,
        );
      },
    );
    if (time == null) return;

    setState(() {
      _dateTime =
          DateTime(date.year, date.month, date.day, time.hour, time.minute);
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate() || _dateTime == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Заполните поля и выберите дату/время'),
        ),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final orderNumber = _orderNumberController.text.trim();
      final firstLine = _descriptionController.text.split('\n').first.trim();
      final result = await bitrix24.createOrder(
        title: orderNumber.isEmpty
            ? (firstLine.isEmpty ? 'Заказ грузчиков' : firstLine)
            : 'Заявка № $orderNumber',
        description: _descriptionController.text.trim(),
        address: _addressController.text.trim(),
        hours: _hours,
        workersCount: _workersCount,
        clientEmail: 'client@gpm.ru',
        clientPhone: '',
        scheduledAt: _dateTime!.toUtc().toIso8601String(),
        city: _cityController.text.trim(),
        source: widget.publishImmediately ? 'crm' : 'manual',
        externalOrderId: orderNumber.isEmpty ? null : orderNumber,
        metro: _metroController.text.trim(),
        national: _isRussianCitizenshipRequired ? 'yes' : 'any',
        minTime: _workMode == 'rate' ? _requiredInt(_minPayController) : null,
        pricePerHour:
            _workMode == 'rate' ? _requiredInt(_workerRateController) : null,
        priceRegular:
            _workMode == 'rate' ? _requiredInt(_regularRateController) : null,
        priceState: _workMode == 'rate'
            ? _requiredInt(_freeScheduleRateController)
            : null,
        nationality: _isRussianCitizenshipRequired ? 'ru' : 'any',
        workerCategory: _workerCategory,
        workMode: _workMode,
        shiftDescription: _workMode == 'shift'
            ? _shiftDescriptionController.text.trim()
            : null,
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
      _orderNumberController.clear();
      _metroController.clear();
      _descriptionController.clear();
      _shiftDescriptionController.clear();
      _regularRateController.text = '450';
      _freeScheduleRateController.text = '450';
      _workerRateController.text = '400';
      _minPayController.text = '4';
      setState(() {
        _dateTime = null;
        _hours = 4;
        _workersCount = 2;
        _isRussianCitizenshipRequired = true;
        _workMode = 'shift';
        _workerCategory = 'loader';
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
                    Text(
                      widget.title.toUpperCase(),
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Оставьте заявку: укажите время, адрес и задачу. Логист проверит заказ и передаст его исполнителям.',
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
              TextFormField(
                controller: _orderNumberController,
                decoration: const InputDecoration(
                  labelText: 'Номер заказа',
                  hintText: 'Например: 12724/26',
                  border: OutlineInputBorder(),
                ),
                validator: (value) =>
                    _requiredText(value, 'Укажите номер заказа'),
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: _pickDateTime,
                icon: const Icon(Icons.calendar_today),
                label: Text(
                  _dateTime == null
                      ? 'Выбрать дату и время'
                      : 'Дата: ${_dateTime!.day.toString().padLeft(2, '0')}.${_dateTime!.month.toString().padLeft(2, '0')} '
                          '${_dateTime!.hour.toString().padLeft(2, '0')}:${_dateTime!.minute.toString().padLeft(2, '0')}',
                ),
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
                    validator: (value) =>
                        _requiredText(value, 'Укажите адрес'),
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
              const Text(
                'Режим работы:',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'shift', label: Text('Смена')),
                  ButtonSegment(value: 'rate', label: Text('Ставка')),
                ],
                selected: {_workMode},
                onSelectionChanged: (selection) =>
                    setState(() => _workMode = selection.first),
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
              TextFormField(
                controller: _descriptionController,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Характер работы',
                  hintText:
                      'Например: разгрузка машины с оргтехникой. Общий вес - 300 кг...',
                  border: OutlineInputBorder(),
                ),
                validator: (value) =>
                    _requiredText(value, 'Опишите характер работы'),
              ),
              if (_workMode == 'shift') ...[
                const SizedBox(height: 12),
                TextFormField(
                  controller: _shiftDescriptionController,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Описание смены',
                    hintText:
                        'Например: Ночная смена 22:00-06:00, 5000 руб за смену',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) => _workMode == 'shift'
                      ? _requiredText(value, 'Опишите смену')
                      : null,
                ),
              ] else ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _regularRateController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Ставка штат. пост.',
                          border: OutlineInputBorder(),
                        ),
                        validator: (value) => _workMode == 'rate'
                            ? _requiredPositiveInt(
                                value,
                                'Укажите ставку',
                              )
                            : null,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextFormField(
                        controller: _freeScheduleRateController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Ставка штат. своб.',
                          border: OutlineInputBorder(),
                        ),
                        validator: (value) => _workMode == 'rate'
                            ? _requiredPositiveInt(
                                value,
                                'Укажите ставку',
                              )
                            : null,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _workerRateController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Ставка наемник',
                          border: OutlineInputBorder(),
                        ),
                        validator: (value) => _workMode == 'rate'
                            ? _requiredPositiveInt(
                                value,
                                'Укажите ставку',
                              )
                            : null,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextFormField(
                        controller: _minPayController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Мин. оплата, ч',
                          border: OutlineInputBorder(),
                        ),
                        validator: (value) => _workMode == 'rate'
                            ? _requiredPositiveInt(
                                value,
                                'Укажите часы',
                              )
                            : null,
                      ),
                    ),
                  ],
                ),
              ],
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

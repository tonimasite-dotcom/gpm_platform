import 'dart:math';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../theme/gpm_theme.dart';
import '../utils/date_time_input_formatters.dart';
import '../widgets/adaptive_buttons.dart';
import '../widgets/gpm_logo.dart';
import 'registration_preview_api.dart';

class RegistrationPreviewScreen extends StatefulWidget {
  final RegistrationPreviewGateway gateway;
  const RegistrationPreviewScreen({super.key, required this.gateway});
  @override
  State<RegistrationPreviewScreen> createState() => _RegistrationPreviewScreenState();
}

class _RegistrationPreviewScreenState extends State<RegistrationPreviewScreen> {
  final _scroll = ScrollController();
  final _phone = TextEditingController();
  final _code = TextEditingController();
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _middle = TextEditingController();
  final _birth = TextEditingController();
  final _search = TextEditingController();
  Map<String, dynamic> _session = {};
  List<Map<String, dynamic>> _locations = [];
  Set<int> _cities = {};
  Set<int> _districts = {};
  bool? _citizenship;
  bool? _straps;
  bool? _tools;
  String _country = 'RU';
  int _step = 0;
  bool _busy = true;
  bool _initializing = true;
  bool _editing = false;
  bool _phoneDirty = false;
  String? _error;
  String? _errorCode;
  Map<String, String> _fieldErrors = {};
  RegistrationPreviewGateway get _api => widget.gateway;
  Map<String, dynamic> get _answers => Map<String, dynamic>.from((_session['answers'] as Map?) ?? {});
  bool get _completed => _session['status'] == 'completed';
  bool get _expired => _session['status'] == 'expired';
  bool get _verified => _session['phone_verified'] == true && !_phoneDirty;
  static const _titles = ['Телефон', 'Территории работы', 'Личные данные', 'Гражданство и оснащение', 'Проверь данные'];

  @override
  void initState() { super.initState(); _load(); }
  @override
  void dispose() {
    for (final controller in [_phone, _code, _first, _last, _middle, _birth, _search]) { controller.dispose(); }
    _scroll.dispose();
    super.dispose();
  }

  int _stepFor(String? value) => switch (value) {
    'phone' => 0,
    'locations' => 1,
    'first_name' || 'last_name' || 'middle_name' || 'birth_date' => 2,
    'citizenship_ru' || 'has_straps' || 'has_tools' => 3,
    _ => 4,
  };

  String _birthLabel(String value) {
    final date = DateTime.tryParse(value);
    if (date == null) return '';
    return '${date.day.toString().padLeft(2, '0')}.${date.month.toString().padLeft(2, '0')}.${date.year}';
  }

  void _syncInputs() {
    final a = _answers;
    _phone.text = a['phone']?.toString() ?? '';
    _first.text = a['first_name']?.toString() ?? '';
    _last.text = a['last_name']?.toString() ?? '';
    _middle.text = a['middle_name']?.toString() ?? '';
    _birth.text = _birthLabel(a['birth_date']?.toString() ?? '');
    _country = a['phone_country']?.toString() ?? 'RU';
    _cities = (a['city_ids'] as List? ?? []).cast<int>().toSet();
    _districts = (a['district_ids'] as List? ?? []).cast<int>().toSet();
    _citizenship = a['citizenship_ru'] as bool?;
    _straps = a['has_straps'] as bool?;
    _tools = a['has_tools'] as bool?;
    _phoneDirty = false;
  }

  void _accept(Map<String, dynamic> value, {bool sync = false}) {
    if (!mounted) return;
    setState(() {
      _session = value;
      if (sync) _syncInputs();
    });
  }

  void _move(int step) {
    if (!mounted) return;
    setState(() => _step = step);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scroll.hasClients) _scroll.animateTo(0, duration: const Duration(milliseconds: 180), curve: Curves.easeOut);
    });
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    FocusScope.of(context).unfocus();
    setState(() { _busy = true; _error = null; _errorCode = null; _fieldErrors = {}; });
    try {
      await action();
    } on RegistrationPreviewError catch (error) {
      if (mounted) setState(() {
        _error = error.message; _errorCode = error.code;
        if (error.field != null) _fieldErrors[error.field!] = error.message;
      });
    } catch (_) {
      if (mounted) setState(() => _error = 'Не удалось выполнить действие. Попробуй еще раз');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _load() async {
    setState(() { _busy = true; _initializing = true; _error = null; _fieldErrors = {}; });
    try {
      final values = await Future.wait([_api.load(), _api.locations()]);
      if (!mounted) return;
      setState(() {
        _locations = (values[1] as List).cast<Map<String, dynamic>>();
        _session = values[0] as Map<String, dynamic>;
        _syncInputs();
        _step = _stepFor(_session['current_step']?.toString());
        _initializing = false;
      });
    } catch (error) {
      if (mounted) setState(() => _error = error is RegistrationPreviewError ? error.message : 'Не удалось открыть анкету. Попробуй еще раз');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool> _confirm(String title, String text) async => await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title), content: Text(text),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Продолжить')),
      ],
    ),
  ) ?? false;

  Future<void> _reset() async {
    if (!await _confirm('Начать заново?', 'Очистится только текущий тестовый черновик. Рабочие аккаунты и завершенные профили сохранятся.')) return;
    if (!mounted) return;
    await _run(() async {
      _accept(await _api.restart(), sync: true);
      _code.clear(); _editing = false; _move(0);
    });
  }

  Future<void> _newTest() => _run(() async {
    _accept(await _api.newSession(), sync: true);
    _code.clear(); _editing = false; _initializing = false; _move(0);
    if (_locations.isEmpty) _locations = await _api.locations();
  });

  Future<void> _example() async {
    if (_answers.isNotEmpty && !await _confirm('Заполнить пример?', 'Текущие тестовые ответы будут заменены примером.')) return;
    if (!mounted) return;
    await _run(() async {
      if (_answers.isNotEmpty) _accept(await _api.restart());
      final suffix = Random.secure().nextInt(10000000).toString().padLeft(7, '0');
      _accept(await _api.save({'phone': '+7000$suffix', 'phone_country': 'RU'}));
      _accept(await _api.challenge());
      _accept(await _api.verify(_session['test_code']?.toString() ?? '123456'));
      _accept(await _api.save({
        'city_ids': [101], 'district_ids': [502],
        'first_name': 'Иван', 'last_name': 'Иванов', 'middle_name': 'Иванович',
        'birth_date': '1994-01-01', 'citizenship_ru': true, 'has_straps': false, 'has_tools': true,
      }), sync: true);
      _editing = false; _move(4);
    });
  }

  Future<void> _sendCode() async {
    _accept(await _api.save({'phone': _phone.text, 'phone_country': _country}));
    if (!mounted) return;
    _phone.text = _answers['phone']?.toString() ?? _phone.text;
    _phoneDirty = false;
    if (_session['phone_verified'] == true) {
      _move(_editing ? 4 : 1); _editing = false;
      return;
    }
    _accept(await _api.challenge());
    _code.clear();
  }

  String _birthIso() {
    final parts = _birth.text.split('.');
    if (parts.length != 3) throw const RegistrationPreviewError('INVALID_BIRTH_DATE', 'Укажи дату в формате ДД.ММ.ГГГГ', 'birth_date');
    final day = int.tryParse(parts[0]), month = int.tryParse(parts[1]), year = int.tryParse(parts[2]);
    if (day == null || month == null || year == null || year < 1 || year > 9999) {
      throw const RegistrationPreviewError('INVALID_BIRTH_DATE', 'Укажи существующую дату рождения', 'birth_date');
    }
    final date = DateTime(year, month, day);
    if (date.day != day || date.month != month || date.year != year) {
      throw const RegistrationPreviewError('INVALID_BIRTH_DATE', 'Укажи существующую дату рождения', 'birth_date');
    }
    return '${year.toString().padLeft(4, '0')}-${month.toString().padLeft(2, '0')}-${day.toString().padLeft(2, '0')}';
  }

  Future<void> _continue() => _run(() async {
    if (_step == 0) {
      if (_phoneDirty || (!_verified && _session['challenge_active'] != true)) {
        await _sendCode(); return;
      }
      if (!_verified) _accept(await _api.verify(_code.text.trim()));
      _move(_editing ? 4 : 1); _editing = false; return;
    }
    if (_step == 1) {
      _accept(await _api.save({'city_ids': _cities.toList(), 'district_ids': _districts.toList()}));
    } else if (_step == 2) {
      _accept(await _api.save({'first_name': _first.text, 'last_name': _last.text,
        'middle_name': _middle.text, 'birth_date': _birthIso()}));
    } else if (_step == 3) {
      for (final entry in {'citizenship_ru': _citizenship, 'has_straps': _straps, 'has_tools': _tools}.entries) {
        if (entry.value == null) throw RegistrationPreviewError('REQUIRED_FIELD', 'Выбери «Да» или «Нет» для каждого вопроса', entry.key);
      }
      _accept(await _api.save({'citizenship_ru': _citizenship, 'has_straps': _straps, 'has_tools': _tools}));
    } else {
      _accept(await _api.complete()); return;
    }
    _move(_editing ? 4 : _step + 1); _editing = false;
  });

  void _edit(int step) {
    _syncInputs(); _editing = true; _error = null; _fieldErrors = {}; _move(step);
  }

  void _back() {
    if (_editing) { _syncInputs(); _editing = false; _move(4); }
    else { _move(_step - 1); }
    setState(() { _error = null; _fieldErrors = {}; });
  }

  String get _primaryLabel {
    if (_step == 4) return 'Подтвердить тестовую регистрацию';
    if (_step == 0 && !_verified) return _phoneDirty || _session['challenge_active'] != true ? 'Получить тестовый код' : 'Подтвердить код';
    return _editing ? 'Сохранить изменения' : 'Далее';
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: SingleChildScrollView(
        controller: _scroll,
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Wrap(
                  spacing: 16, runSpacing: 8, alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: const [GpmLogoImage(width: 132), Chip(avatar: Icon(Icons.engineering_outlined), label: Text('Исполнитель'))],
                ),
                const SizedBox(height: 20),
                _surface(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(color: GpmColors.yellow.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(10)),
                    child: const Text('Тестовая регистрация', style: TextStyle(fontWeight: FontWeight.w700)),
                  ),
                  const SizedBox(height: 14),
                  Text(_completed ? 'Анкета завершена' : 'Регистрация исполнителя', style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 10),
                  Text(_completed ? 'Тестовый профиль сохранен на сервере. Рабочий аккаунт в приложении не создается.' :
                    'Заполни анкету и проверь ответы. Черновик сохраняется на сервере после каждого шага.'),
                  const SizedBox(height: 8),
                  const Text('Используй вымышленные данные. Телефон и список территорий пока тестовые.', style: TextStyle(color: GpmColors.muted)),
                ])),
                const SizedBox(height: 16),
                if (_error != null) ...[
                  _surface(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    const Icon(Icons.info_outline, color: GpmColors.redInk),
                    const SizedBox(height: 8), Text(_error!, style: const TextStyle(color: GpmColors.redInk)),
                    if (_initializing || _errorCode == 'REVISION_CONFLICT')
                      TextButton(onPressed: _busy ? null : _load, child: const Text('Загрузить анкету заново')),
                  ])),
                  const SizedBox(height: 16),
                ],
                if (_initializing) ...[
                  if (_busy) const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
                  if (!_busy) OutlinedButton(onPressed: _newTest, child: const Text('Открыть новую тестовую анкету')),
                ] else if (_expired) ...[
                  _surface(const Text('Срок черновика истек. Можно открыть новую тестовую анкету.')),
                  const SizedBox(height: 16),
                  FilledButton(onPressed: _busy ? null : _newTest, child: const Text('Новая тестовая анкета')),
                ] else if (_completed) ...[
                  const Center(child: Icon(Icons.check_circle_outline, color: GpmColors.business, size: 52)),
                  const SizedBox(height: 16), _review(), const SizedBox(height: 16),
                  OutlinedButton(onPressed: _busy ? null : _newTest, child: const Text('Новая тестовая анкета')),
                  TextButton(onPressed: () => launchUrl(Uri.parse('https://app.gpmbot.ru/'), webOnlyWindowName: '_self'), child: const Text('Открыть приложение')),
                ] else ...[
                  if (_session['browser_remembers_session'] == false) ...[
                    const Text('Браузер не смог запомнить ключ черновика. Не закрывай страницу до завершения.', style: TextStyle(color: GpmColors.redInk)),
                    const SizedBox(height: 12),
                  ],
                  Text('Шаг ${_step + 1} из 5 · ${_titles[_step]}', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 10),
                  LinearProgressIndicator(value: (_step + 1) / 5, borderRadius: BorderRadius.circular(8), minHeight: 6),
                  const SizedBox(height: 18),
                  switch (_step) { 0 => _phoneStep(), 1 => _locationsStep(), 2 => _personalStep(), 3 => _equipmentStep(), _ => _review() },
                  const SizedBox(height: 18),
                  GpmActionButtons(children: [
                    if (_step > 0) OutlinedButton(onPressed: _busy ? null : _back,
                      child: GpmButtonContent(icon: const Icon(Icons.arrow_back), label: Text(_editing ? 'Отменить изменения' : 'Назад'))),
                    FilledButton(key: const Key('registration_primary'), onPressed: _busy ? null : _continue,
                      child: GpmButtonContent(icon: _busy ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) :
                        Icon(_step == 4 ? Icons.check : Icons.arrow_forward), label: Text(_busy ? 'Сохраняем…' : _primaryLabel))),
                  ]),
                  const SizedBox(height: 12),
                  Wrap(spacing: 8, runSpacing: 4, alignment: WrapAlignment.center, children: [
                    TextButton(onPressed: _busy ? null : _example, child: const Text('Заполнить пример')),
                    TextButton(onPressed: _busy ? null : _reset, child: const Text('Начать заново')),
                  ]),
                  const SizedBox(height: 8),
                  const Text('Паспорт, ИНН и самозанятость оформляются отдельно после основной анкеты.', textAlign: TextAlign.center, style: TextStyle(color: GpmColors.muted, fontSize: 12)),
                ],
              ],
            ),
          ),
        ),
      ),
    ),
  );

  Widget _surface(Widget child) => Card(margin: EdgeInsets.zero, child: Padding(padding: const EdgeInsets.all(18), child: child));

  Widget _input(TextEditingController controller, String field, String label, {String? hint, IconData? icon, TextInputType? type, Widget? suffix}) => TextFormField(
    key: Key('registration_$field'), controller: controller, enabled: !_busy,
    keyboardType: type, textCapitalization: type == null ? TextCapitalization.words : TextCapitalization.none,
    decoration: InputDecoration(labelText: label, hintText: hint, prefixIcon: icon == null ? null : Icon(icon), suffixIcon: suffix, errorText: _fieldErrors[field]),
  );

  Widget _phoneStep() => _surface(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    Text('Номер для связи по заказам', style: Theme.of(context).textTheme.titleMedium),
    const SizedBox(height: 16),
    DropdownButtonFormField<String>(
      key: ValueKey(_country), initialValue: _country, isExpanded: true,
      decoration: const InputDecoration(labelText: 'Страна номера'),
      items: const [DropdownMenuItem(value: 'RU', child: Text('Россия (+7)')), DropdownMenuItem(value: 'INT', child: Text('Другая страна'))],
      onChanged: _busy ? null : (value) => setState(() { _country = value!; _phoneDirty = true; }),
    ),
    const SizedBox(height: 16),
    TextFormField(key: const Key('registration_phone'), controller: _phone, enabled: !_busy,
      keyboardType: TextInputType.phone, autofillHints: const [AutofillHints.telephoneNumber],
      onChanged: (_) => setState(() => _phoneDirty = true),
      decoration: InputDecoration(labelText: 'Телефон', hintText: '+7 000 000-00-00', prefixIcon: const Icon(Icons.phone_outlined), errorText: _fieldErrors['phone'])),
    const SizedBox(height: 12),
    if (_verified) const Text('Номер подтвержден в тесте', style: TextStyle(color: GpmColors.business, fontWeight: FontWeight.w700)),
    if (_session['challenge_active'] == true && !_phoneDirty && !_verified) ...[
      const SizedBox(height: 8),
      _input(_code, 'code', 'Код подтверждения', hint: '123456', icon: Icons.sms_outlined, type: TextInputType.number),
      const SizedBox(height: 8),
      TextButton(onPressed: _busy ? null : () => _run(_sendCode), child: const Text('Получить новый код')),
    ],
    const SizedBox(height: 8),
    const Text('SMS не отправляется. Для проверки сценария используй код 123456.', style: TextStyle(color: GpmColors.muted)),
  ]));

  Widget _locationsStep() {
    final query = _search.text.trim().toLowerCase();
    String cityName(dynamic id) => _locations.where((item) => item['kind'] == 'city' && item['id'] == id).map((item) => item['name'].toString()).firstOrNull ?? '';
    final visible = _locations.where((item) => item['enabled'] == true && '${item['name']} ${cityName(item['city_id'])}'.toLowerCase().contains(query));
    return _surface(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('Где ты хочешь работать?', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      const Text('Можно выбрать несколько городов или отдельные районы. Выбор района не добавляет весь город.'),
      const SizedBox(height: 16),
      TextField(controller: _search, enabled: !_busy, onChanged: (_) => setState(() {}), decoration: const InputDecoration(labelText: 'Поиск города или района', prefixIcon: Icon(Icons.search))),
      const SizedBox(height: 12),
      Text('Выбрано: ${_cities.length + _districts.length}', style: const TextStyle(fontWeight: FontWeight.w700)),
      if (visible.isEmpty) const Padding(padding: EdgeInsets.all(16), child: Text('Ничего не найдено')),
      for (final item in visible)
        CheckboxListTile(
          key: Key('location_${item['id']}'), contentPadding: EdgeInsets.zero,
          title: Text(item['name'].toString()),
          subtitle: Text(item['kind'] == 'city' ? 'Весь город' : '${cityName(item['city_id'])} · только этот район'),
          value: (item['kind'] == 'city' ? _cities : _districts).contains(item['id']),
          onChanged: _busy ? null : (selected) => setState(() {
            final target = item['kind'] == 'city' ? _cities : _districts;
            if (selected == true) { target.add(item['id'] as int); } else { target.remove(item['id']); }
          }),
        ),
      const Text('Пока показан тестовый список территорий.', style: TextStyle(color: GpmColors.muted)),
    ]));
  }

  Future<void> _pickBirth() async {
    final now = DateTime.now();
    final parts = _birth.text.split('.');
    var initial = DateTime(now.year - 18, now.month, now.day);
    if (parts.length == 3) {
      final parsed = DateTime.tryParse('${parts[2]}-${parts[1]}-${parts[0]}');
      if (parsed != null && !parsed.isAfter(now) && !parsed.isBefore(DateTime(1900))) initial = parsed;
    }
    final result = await showDatePicker(context: context, initialDate: initial, firstDate: DateTime(1900), lastDate: now,
      helpText: 'Дата рождения', cancelText: 'Отмена', confirmText: 'Выбрать');
    if (!mounted || result == null) return;
    setState(() => _birth.text = _birthLabel('${result.year.toString().padLeft(4, '0')}-${result.month.toString().padLeft(2, '0')}-${result.day.toString().padLeft(2, '0')}'));
  }

  Widget _personalStep() => _surface(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    Text('Расскажи о себе', style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 16),
    _input(_first, 'first_name', 'Имя', icon: Icons.person_outline), const SizedBox(height: 16),
    _input(_last, 'last_name', 'Фамилия', icon: Icons.badge_outlined), const SizedBox(height: 16),
    _input(_middle, 'middle_name', _session['middle_name_required'] == true ? 'Отчество' : 'Отчество (необязательно в тесте)'), const SizedBox(height: 16),
    TextFormField(key: const Key('registration_birth_date'), controller: _birth, enabled: !_busy,
      keyboardType: TextInputType.number, inputFormatters: dateAutoSeparatorFormatters,
      decoration: InputDecoration(labelText: 'Дата рождения', hintText: 'ДД.ММ.ГГГГ', errorText: _fieldErrors['birth_date'],
        prefixIcon: const Icon(Icons.cake_outlined), suffixIcon: IconButton(tooltip: 'Выбрать дату рождения', onPressed: _busy ? null : _pickBirth, icon: const Icon(Icons.calendar_today_outlined)))),
    const SizedBox(height: 10), const Text('Для регистрации должно исполниться 18 лет.', style: TextStyle(color: GpmColors.muted)),
  ]));

  Widget _answer(String field, String title, bool? value, ValueChanged<bool> update) => Padding(
    padding: const EdgeInsets.only(bottom: 20),
    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(title, style: const TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 12),
      GpmSegmentedButton<bool>(key: Key('answer_$field'),
        segments: const [ButtonSegment(value: true, label: Text('Да')), ButtonSegment(value: false, label: Text('Нет'))],
        selected: value == null ? <bool>{} : {value}, emptySelectionAllowed: true,
        onSelectionChanged: _busy ? null : (values) { if (values.isNotEmpty) setState(() => update(values.first)); },
      ),
      if (_fieldErrors[field] != null) Text(_fieldErrors[field]!, style: const TextStyle(color: GpmColors.redInk)),
    ]),
  );

  Widget _equipmentStep() => _surface(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    _answer('citizenship_ru', 'Ты гражданин Российской Федерации?', _citizenship, (value) => _citizenship = value),
    _answer('has_straps', 'Есть ли у тебя такелажные ремни?', _straps, (value) => _straps = value),
    _answer('has_tools', 'Есть ли у тебя шуруповерт или другие инструменты?', _tools, (value) => _tools = value),
    const Text('Ответ «Нет» не мешает завершить основную анкету.', style: TextStyle(color: GpmColors.muted)),
  ]));

  Widget _review() {
    final a = _answers;
    final selected = {...(a['city_ids'] as List? ?? []), ...(a['district_ids'] as List? ?? [])};
    final labels = _locations.where((item) => selected.contains(item['id'])).map((item) => item['name'].toString()).join(', ');
    String yesNo(dynamic value) => value == true ? 'Да' : value == false ? 'Нет' : 'Не указано';
    final rows = [
      ('Телефон', a['phone']?.toString() ?? 'Не указан', 0),
      ('Города и районы', labels.isEmpty ? 'Не выбраны' : labels, 1),
      ('Имя', a['first_name']?.toString() ?? '', 2),
      ('Фамилия', a['last_name']?.toString() ?? '', 2),
      ('Отчество', a['middle_name']?.toString().isNotEmpty == true ? a['middle_name'].toString() : 'Не указано', 2),
      ('Дата рождения', _birthLabel(a['birth_date']?.toString() ?? ''), 2),
      ('Гражданство РФ', yesNo(a['citizenship_ru']), 3),
      ('Такелажные ремни', yesNo(a['has_straps']), 3),
      ('Шуруповерт или другие инструменты', yesNo(a['has_tools']), 3),
    ];
    return _surface(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (!_completed) ...[Text('Все верно?', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 8), const Text('Можно изменить любой ответ до подтверждения.'), const SizedBox(height: 12)],
      for (var index = 0; index < rows.length; index++) ...[
        if (index > 0) const Divider(height: 24),
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(rows[index].$1, style: const TextStyle(color: GpmColors.muted, fontSize: 12)),
            const SizedBox(height: 4), Text(rows[index].$2, style: const TextStyle(fontWeight: FontWeight.w600)),
          ])),
          if (!_completed) IconButton(tooltip: 'Изменить: ${rows[index].$1}', onPressed: _busy ? null : () => _edit(rows[index].$3), icon: const Icon(Icons.edit_outlined)),
        ]),
      ],
    ]));
  }
}

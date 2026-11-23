import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../registration/registration_phone_input.dart';
import '../../theme/gpm_theme.dart';
import '../../widgets/adaptive_buttons.dart';

String? normalizeSbpPhone(String value) {
  if (!RegExp(r'^[+0-9 ()-]+$').hasMatch(value) ||
      '+'.allMatches(value).length > 1 ||
      (value.contains('+') && !value.trim().startsWith('+'))) {
    return null;
  }
  var digits = value.replaceAll(RegExp(r'[^0-9]'), '');
  if (digits.length == 11 && (digits.startsWith('7') || digits.startsWith('8'))) {
    digits = digits.substring(1);
  }
  return digits.length == 10 ? '+7$digits' : null;
}

class SbpBank {
  final String id;
  final String name;
  const SbpBank(this.id, this.name);
}
Future<List<SbpBank>>? _banksFuture;
Future<List<SbpBank>> loadSbpBanks() => _banksFuture ??= _readBanks();
Future<List<SbpBank>> _readBanks() async {
  final raw = jsonDecode(await rootBundle.loadString('assets/data/sbp_banks.json')) as Map<String, dynamic>;
  final banks = (raw['banks'] as List).map((item) => SbpBank(item['id'] as String, item['name'] as String)).toList();
  banks.sort((a,b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
  return banks;
}

class SbpPayoutDetails {
  final String bankId;
  final String bankName;
  final String phone;
  const SbpPayoutDetails({required this.bankId, required this.bankName, required this.phone});
  bool get complete => bankId.isNotEmpty && normalizeSbpPhone(phone) != null;
}

class WorkerSbpPayoutField extends StatelessWidget {
  final SbpPayoutDetails details;
  final String profilePhone;
  final Future<void> Function(SbpPayoutDetails) onSave;
  const WorkerSbpPayoutField({super.key, required this.details, required this.profilePhone, required this.onSave});
  @override
  Widget build(BuildContext context) => Container(
    decoration: BoxDecoration(color: GpmColors.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: GpmColors.softLine)),
    child: ListTile(
      key: const Key('worker_sbp_details'),
      leading: const Icon(Icons.account_balance_outlined, color: GpmColors.redAction),
      title: Text(details.complete ? details.bankName : 'Реквизиты для получения оплаты', style: const TextStyle(fontWeight: FontWeight.w700)),
      subtitle: Text(details.complete ? details.phone : 'Выберите банк и телефон для перевода по СБП'),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => showWorkerSbpPayout(context, details: details, profilePhone: profilePhone, onSave: onSave),
    ),
  );
}

Future<void> showWorkerSbpPayout(BuildContext context, {
  required SbpPayoutDetails details, required String profilePhone,
  required Future<void> Function(SbpPayoutDetails) onSave,
}) async {
  Widget editor() => _SbpEditor(details: details, profilePhone: profilePhone, onSave: onSave);
  if (MediaQuery.sizeOf(context).width >= 600) {
    await showDialog<void>(context: context, builder: (_) => Dialog(
      backgroundColor: GpmColors.surface,
      child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 480), child: editor()),
    ));
  } else {
    await showModalBottomSheet<void>(
      context: context, isScrollControlled: true, useSafeArea: true,
      backgroundColor: GpmColors.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (context) => Padding(padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom), child: editor()),
    );
  }
}

class _SbpEditor extends StatefulWidget {
  final SbpPayoutDetails details;
  final String profilePhone;
  final Future<void> Function(SbpPayoutDetails) onSave;
  const _SbpEditor({required this.details, required this.profilePhone, required this.onSave});
  @override
  State<_SbpEditor> createState() => _SbpEditorState();
}
class _SbpEditorState extends State<_SbpEditor> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _phone;
  SbpBank? _bank;
  bool _saving = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    _phone = TextEditingController(text: widget.details.phone);
    if (widget.details.bankId.isNotEmpty) _bank = SbpBank(widget.details.bankId, widget.details.bankName);
  }
  @override
  void dispose() { _phone.dispose(); super.dispose(); }

  Future<void> _chooseBank() async {
    FocusScope.of(context).unfocus();
    final selected = await showModalBottomSheet<SbpBank>(
      context: context, isScrollControlled: true, useSafeArea: true,
      backgroundColor: GpmColors.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (context) => SizedBox(
        height: math.min(MediaQuery.sizeOf(context).height * .88, 720),
        child: Padding(padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom), child: _BankPicker(selectedId: _bank?.id)),
      ),
    );
    if (mounted && selected != null) setState(() { _bank = selected; _error = null; });
  }
  Future<void> _submit() async {
    if (_saving || !_form.currentState!.validate()) return;
    if (_bank == null) { setState(() => _error = 'Выберите банк'); return; }
    final details = SbpPayoutDetails(bankId: _bank!.id, bankName: _bank!.name, phone: normalizeSbpPhone(_phone.text)!);
    setState(() { _saving = true; _error = null; });
    try {
      await widget.onSave(details);
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) setState(() => _error = 'Не удалось сохранить реквизиты. Повторите попытку');
    } finally { if (mounted) setState(() => _saving = false); }
  }

  @override
  Widget build(BuildContext context) {
    final ownPhone = normalizeSbpPhone(widget.profilePhone);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Form(key: _form, child: Column(
        mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Реквизиты для получения оплаты', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: GpmColors.black)),
          const SizedBox(height: 8),
          const Text('Перевод физлицу по номеру телефона через СБП.', style: TextStyle(color: GpmColors.graphite)),
          const SizedBox(height: 24),
          InkWell(
            key: const Key('worker_sbp_bank'),
            onTap: _saving ? null : _chooseBank,
            borderRadius: BorderRadius.circular(14),
            child: InputDecorator(
              decoration: const InputDecoration(labelText: 'Банк', suffixIcon: Icon(Icons.expand_more)),
              child: Text(_bank?.name ?? 'Выберите банк'),
            ),
          ),
          const SizedBox(height: 16),
          TextFormField(
            key: const Key('worker_sbp_phone'), controller: _phone,
            enabled: !_saving, keyboardType: TextInputType.phone, textInputAction: TextInputAction.done,
            autofillHints: const [AutofillHints.telephoneNumber],
            inputFormatters: const [RegistrationPhoneFormatter('RU')],
            decoration: const InputDecoration(labelText: 'Телефон, привязанный к банку', hintText: '+7 900 000-00-00', prefixIcon: Icon(Icons.phone_outlined)),
            validator: (value) => normalizeSbpPhone(value ?? '') == null ? 'Укажите номер в формате +7 900 000-00-00' : null,
            onFieldSubmitted: (_) => _submit(),
          ),
          if (ownPhone != null) ...[
            const SizedBox(height: 8),
            Align(alignment: Alignment.centerLeft, child: TextButton.icon(
              key: const Key('worker_sbp_use_profile_phone'),
              onPressed: _saving ? null : () => setState(() => _phone.text = ownPhone),
              icon: const Icon(Icons.content_paste, size: 18),
              label: Text('Вставить мой номер $ownPhone'),
            )),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Semantics(liveRegion: true, child: Text(_error!, style: const TextStyle(color: GpmColors.redAction))),
          ],
          const SizedBox(height: 24),
          GpmActionButtons(minButtonWidth: 150, children: [
            OutlinedButton(onPressed: _saving ? null : () => Navigator.of(context).pop(), child: const Text('Отмена')),
            FilledButton(
              key: const Key('worker_sbp_save'), onPressed: _saving ? null : _submit,
              child: _saving ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Text('Добавить реквизиты'),
            ),
          ]),
        ],
      )),
    );
  }
}

class _BankPicker extends StatefulWidget {
  final String? selectedId;
  const _BankPicker({this.selectedId});
  @override
  State<_BankPicker> createState() => _BankPickerState();
}
class _BankPickerState extends State<_BankPicker> {
  late Future<List<SbpBank>> _future;
  String _query = '';
  @override
  void initState() { super.initState(); _future = loadSbpBanks(); }
  String _search(String value) => value.toLowerCase().replaceAll('ё', 'е').replaceAll(RegExp(r'[^a-zа-я0-9]'), '');
  @override
  Widget build(BuildContext context) => Column(children: [
    Padding(padding: const EdgeInsets.fromLTRB(12, 12, 20, 8), child: Row(children: [
      IconButton(tooltip: 'Назад', onPressed: () => Navigator.of(context).pop(), icon: const Icon(Icons.arrow_back)),
      const SizedBox(width: 8),
      const Expanded(child: Text('Выбор банка', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800))),
    ])),
    Padding(padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8), child: TextField(
      key: const Key('worker_sbp_bank_search'),
      decoration: const InputDecoration(hintText: 'Найти банк', prefixIcon: Icon(Icons.search)),
      onChanged: (value) => setState(() => _query = _search(value)),
    )),
    Expanded(child: FutureBuilder<List<SbpBank>>(future: _future, builder: (context, snapshot) {
      if (snapshot.hasError) return const Center(child: Text('Не удалось загрузить список банков'));
      if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
      final banks = snapshot.data!.where((bank) => _search(bank.name).contains(_query)).toList();
      if (banks.isEmpty) return const Center(child: Text('Банк не найден'));
      return ListView.separated(
        padding: const EdgeInsets.fromLTRB(8, 0, 8, 16), itemCount: banks.length,
        separatorBuilder: (_, index) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final bank = banks[index];
          return ListTile(
            title: Text(bank.name), contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            trailing: bank.id == widget.selectedId ? const Icon(Icons.check_circle, color: GpmColors.redAction) : null,
            onTap: () => Navigator.of(context).pop(bank),
          );
        },
      );
    })),
  ]);
}

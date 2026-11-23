import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../../main.dart' show gpmApi;
import '../../theme/gpm_theme.dart';
import '../../widgets/adaptive_buttons.dart';
import 'attendance_location.dart';
import 'order_attendance.dart' show AttendanceScannerScreen;

String crewTime(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (date == null) return '—';
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(date.day)}.${two(date.month)} ${two(date.hour)}:${two(date.minute)}';
}

String crewStatus(dynamic value) => switch (value) {
  'issued' => 'QR ожидает сканирования',
  'collected' => 'Старший отсканировал, ожидаем клиента',
  'awaiting_confirmation' => 'Ожидаем подтверждения клиента',
  'pending_review' => 'На проверке у логиста',
  'confirmed' => 'Подтверждено',
  'rejected' => 'Отклонено логистом',
  'expired' => 'Срок QR истек',
  _ => 'Ожидает отметки',
};

class CrewAttendanceGate extends StatefulWidget {
  final String orderId;
  final Widget child;
  final VoidCallback? onChanged;
  final Future<Map<String, dynamic>> Function() locationProvider;
  const CrewAttendanceGate({
    super.key, required this.orderId, required this.child, this.onChanged,
    this.locationProvider = readAttendanceLocation,
  });
  @override
  State<CrewAttendanceGate> createState() => _CrewAttendanceGateState();
}

class _CrewAttendanceGateState extends State<CrewAttendanceGate> {
  late Future<Map<String, dynamic>> _future;
  Timer? _timer;
  bool _busy = false;
  String get _base => '/app-api/me/crew-attendance/${Uri.encodeComponent(widget.orderId)}';

  @override
  void initState() {
    super.initState();
    _future = gpmApi.getCrewAttendance(widget.orderId);
    _timer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (mounted && !_busy && (ModalRoute.of(context)?.isCurrent ?? true) && TickerMode.of(context)) {
        setState(() => _future = gpmApi.getCrewAttendance(widget.orderId));
      }
    });
  }

  @override
  void dispose() { _timer?.cancel(); super.dispose(); }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
      widget.onChanged?.call();
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() {
        _busy = false;
        _future = gpmApi.getCrewAttendance(widget.orderId);
      });
    }
  }

  Future<void> _showQr(Map<String, dynamic> challenge) async {
    if (!mounted) return;
    await Navigator.push(context, MaterialPageRoute<void>(builder: (_) =>
      CrewAttendanceQrScreen(orderId: widget.orderId, challenge: challenge)));
  }

  Future<void> _start(String action) => _run(() async {
    final location = await widget.locationProvider();
    await gpmApi.crewAttendanceRequest('$_base/sessions', body: {'action': action, 'location': location});
  });

  Future<void> _presence() => _run(() async {
    final location = await widget.locationProvider();
    final challenge = await gpmApi.crewAttendanceRequest('$_base/presence', body: {'location': location});
    await _showQr(challenge);
  });

  Future<void> _scan(String sessionId) => _run(() async {
    final token = await Navigator.push<String>(context, MaterialPageRoute(
      builder: (_) => const AttendanceScannerScreen()));
    if (token == null) return;
    final location = await widget.locationProvider();
    await gpmApi.crewAttendanceRequest('/app-api/me/crew-sessions/$sessionId/scan',
      body: {'token': token, 'location': location});
  });

  Future<void> _freeze(String sessionId) => _run(() async {
    final challenge = await gpmApi.crewAttendanceRequest('/app-api/me/crew-sessions/$sessionId/freeze');
    await _showQr(challenge);
  });

  Future<void> _review(Map proof, String decision) async {
    final reason = TextEditingController();
    final answer = await showDialog<String>(context: context, builder: (context) =>
      AlertDialog(
        title: Text(decision == 'approve' ? 'Подтвердить отметку' : 'Отклонить отметку'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('${proof['worker_name']} · ${crewTime(proof['collected_at'])}'),
          const SizedBox(height: 12),
          TextField(key: const Key('crew_review_reason'), controller: reason, minLines: 2, maxLines: 4,
            maxLength: 1000, decoration: const InputDecoration(labelText: 'Причина решения')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Отмена')),
          FilledButton(onPressed: () {
            if (reason.text.trim().length >= 3) Navigator.pop(context, reason.text.trim());
          }, child: const Text('Сохранить решение')),
        ],
      ));
    reason.dispose();
    if (answer == null) return;
    await _run(() async {
      await gpmApi.crewAttendanceRequest('/app-api/me/crew-reviews/${proof['evidence_id']}',
        body: {'decision': decision, 'reason': answer});
    });
  }

  bool _eligible(List<Map> roster, List<Map> proofs, String action) => roster.any((person) {
    final eligible = action == 'check_in' ? person['check_in_at'] == null
      : person['check_in_at'] != null && person['check_out_at'] == null;
    return eligible && !proofs.any((p) => p['worker_account_id'] == person['worker_account_id'] &&
      p['action'] == action && ['collected','awaiting_confirmation','pending_review'].contains(p['status']));
  });

  Widget _button(String text, IconData icon, VoidCallback? onPressed, {Key? key}) =>
    FilledButton(key: key, onPressed: _busy ? null : onPressed,
      child: GpmButtonContent(icon: Icon(icon), label: Text(text)));

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
    future: _future,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
          const Text('Не удалось обновить онлайн-табель'),
          TextButton(onPressed: () => setState(() => _future = gpmApi.getCrewAttendance(widget.orderId)),
            child: const Text('Повторить')),
        ])));
      }
      if (!snapshot.hasData) return const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator());
      final data = snapshot.data!;
      if (data['enabled'] != true || data['role'] == 'client') return widget.child;
      final roster = (data['roster'] as List? ?? []).whereType<Map>().toList();
      final proofs = (data['proofs'] as List? ?? []).whereType<Map>().toList();
      final session = data['session'] as Map?;
      final isLeader = data['is_leader'] == true;
      final isLogist = data['role'] == 'logist';
      final paused = data['paused'] == true;
      final solo = data['mode'] == 'solo';
      return Card(key: const Key('crew_attendance_panel'), margin: EdgeInsets.zero,
        child: Padding(padding: const EdgeInsets.all(16), child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Учет рабочего времени', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            if (_busy) const LinearProgressIndicator(),
            if (paused) const Text('Новые QR временно приостановлены. Ранее созданные отметки сохранены.'),
            if (!isLogist) Text(solo ? 'Один исполнитель · свой QR'
              : isLeader ? 'Вы — старший бригады' : 'QR исполнителя сканирует старший'),
            const SizedBox(height: 8),
            for (final person in roster) Padding(padding: const EdgeInsets.symmetric(vertical: 5),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${person['worker_name']}${person['is_leader'] == true ? ' · старший' : ''}',
                  style: const TextStyle(fontWeight: FontWeight.w700)),
                Text('Приход: ${crewTime(person['check_in_at'])} · Уход: ${crewTime(person['check_out_at'])}'),
              ])),
            for (final proof in proofs) Padding(padding: const EdgeInsets.symmetric(vertical: 5),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${proof['worker_name']}: ${crewStatus(proof['status'])}'),
                if (proof['collected_at'] != null) Text('Сканирование: ${crewTime(proof['collected_at'])}'),
                if (proof['review_reason'] != null) Text('Решение: ${proof['review_reason']}'),
                if (isLogist && proof['status'] == 'pending_review') ...[
                  for (final evidence in [proof['worker_evidence'], proof['scanner_evidence']])
                    if (evidence is Map)
                      Text('${evidence['reason'] ?? ''}${evidence['distance_m'] != null ? ' · ${evidence['distance_m']} м от объекта' : ''}${evidence['accuracy'] != null ? ' · точность ${evidence['accuracy']} м' : ''}'),
                  GpmActionButtons(children: [
                    _button('Подтвердить', Icons.check, () => _review(proof, 'approve')),
                    OutlinedButton(onPressed: _busy ? null : () => _review(proof, 'reject'), child: const Text('Отклонить')),
                  ]),
                ],
              ])),
            if (isLogist && roster.length > 1) ...[
              const SizedBox(height: 12),
              if (data['leader_in_crm'] == true) const Text('Старший назначается в CRM')
              else DropdownButtonFormField<String>(
                key: const Key('crew_leader_selector'),
                initialValue: roster.any((p) => p['worker_account_id'] == data['leader_account_id'])
                    ? data['leader_account_id']?.toString() : null,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Старший по этой заявке'),
                items: [for (final person in roster) DropdownMenuItem(
                  value: person['worker_account_id'].toString(),
                  child: Text(person['worker_name'].toString(), overflow: TextOverflow.ellipsis))],
                onChanged: _busy || paused ? null : (value) => _run(() async {
                  await gpmApi.crewAttendanceRequest('$_base/leader', body: {'worker_account_id': value});
                }),
              ),
            ],
            if (isLogist && data['setup_required'] == true) ...[
              const SizedBox(height: 12),
              const Text('Включите новый QR-табель после настройки состава. Уже начатые смены продолжаются по прежним правилам.'),
              _button('Включить QR-табель', Icons.qr_code_2, paused ? null : () => _run(() async {
                await gpmApi.crewAttendanceRequest('$_base/enable');
              })),
            ],
            if (!isLogist) ...[
              const SizedBox(height: 12),
              const Text('Геолокация запрашивается только при отметке. Если ее нельзя проверить, отметку проверит логист.',
                style: TextStyle(color: GpmColors.muted, fontSize: 12)),
              const SizedBox(height: 10),
              if (solo) _button('Показать мой QR', Icons.qr_code_2,
                !paused && (_eligible(roster, proofs, 'check_in') || _eligible(roster, proofs, 'check_out')) ? _presence : null,
                key: const Key('crew_presence'))
              else if (!isLeader) ...[
                if ((data['leader_account_id']?.toString() ?? '').isEmpty)
                  const Text('Логист должен назначить старшего этой заявки'),
                _button('Показать QR старшему', Icons.qr_code_2,
                  !paused && (data['leader_account_id']?.toString() ?? '').isNotEmpty &&
                    (_eligible(roster,proofs,'check_in') || _eligible(roster,proofs,'check_out')) ? _presence : null,
                  key: const Key('crew_presence')),
              ] else if (session == null) GpmActionButtons(children: [
                _button('Собрать приход', Icons.login, !paused && _eligible(roster,proofs,'check_in') ? () => _start('check_in') : null),
                _button('Собрать уход', Icons.logout, !paused && _eligible(roster,proofs,'check_out') ? () => _start('check_out') : null),
              ]) else ...[
                Text(session['action'] == 'check_out' ? 'Сбор ухода' : 'Сбор прихода',
                  style: const TextStyle(fontWeight: FontWeight.w800)),
                for (final person in (session['members'] as List? ?? []).whereType<Map>())
                  ListTile(contentPadding: EdgeInsets.zero,
                    leading: Icon(person['geo_status']=='valid' ? Icons.check_circle_outline : Icons.pending_actions),
                    title: Text(person['worker_name'].toString()),
                    subtitle: Text('${crewTime(person['collected_at'])} · ${person['geo_status']=='valid' ? 'Геолокация проверена' : 'Потребуется решение логиста'}')),
                if (session['status']=='collecting')
                  _button('Сканировать QR исполнителя', Icons.qr_code_scanner,
                    paused ? null : () => _scan(session['session_id'].toString()),
                    key: const Key('crew_scan')),
                const SizedBox(height: 8),
                _button('Показать QR клиенту', Icons.qr_code_2,
                  !paused && (session['members'] as List? ?? []).isNotEmpty
                    ? () => _freeze(session['session_id'].toString()) : null,
                  key: const Key('crew_freeze')),
                TextButton(onPressed: _busy ? null : () => _run(() async {
                  await gpmApi.crewAttendanceRequest('/app-api/me/crew-sessions/${session['session_id']}/cancel');
                }), child: const Text('Отменить этот сбор')),
              ],
            ],
          ],
        )));
    });
}

class CrewAttendanceQrScreen extends StatefulWidget {
  final String orderId;
  final Map<String, dynamic> challenge;
  const CrewAttendanceQrScreen({super.key, required this.orderId, required this.challenge});
  @override
  State<CrewAttendanceQrScreen> createState() => _CrewAttendanceQrScreenState();
}

class _CrewAttendanceQrScreenState extends State<CrewAttendanceQrScreen> {
  Timer? _timer;
  int _seconds = 60;
  bool _busy = false;
  String _status = '';
  final _code = TextEditingController();
  bool get _presence => widget.challenge['kind'] == 'presence';
  bool get _guest => widget.challenge['verifier_mode'] == 'guest_code';

  @override
  void initState() {
    super.initState();
    _tick();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      _tick();
      if (_seconds % 3 == 0) _poll();
    });
  }

  void _tick() {
    if (!mounted) return;
    final expiry = DateTime.tryParse(widget.challenge['expires_at']?.toString() ?? '');
    setState(() => _seconds = expiry == null ? 0 : expiry.difference(DateTime.now()).inSeconds.clamp(0,60));
  }

  Future<void> _poll() async {
    if (_busy) return;
    _busy = true;
    try {
      if (_presence) {
        final data = await gpmApi.getCrewAttendance(widget.orderId);
        final found = (data['proofs'] as List? ?? []).whereType<Map>().where(
          (p) => p['evidence_id'] == widget.challenge['evidence_id']).firstOrNull;
        if (found != null && !['issued','expired'].contains(found['status']) && mounted) {
          Navigator.pop(context);
          return;
        }
      } else {
        final data = await gpmApi.crewAttendanceRequest(
          '/app-api/me/crew-sessions/${widget.challenge['session_id']}', method: 'GET');
        if (['pending_review','partially_confirmed','confirmed','rejected'].contains(data['status']) && mounted) {
          Navigator.pop(context);
          return;
        }
      }
    } catch (_) {
      if (mounted) setState(() => _status = 'Нет связи. Подтвержденные данные сохраняются на сервере.');
    } finally {
      _busy = false;
    }
  }

  Future<void> _complete() async {
    if (_busy || _code.text.trim().length != 6) return;
    setState(() => _busy = true);
    try {
      await gpmApi.completeGuestAttendance(_code.text.trim());
      if (mounted) Navigator.pop(context);
    } catch (error) {
      if (mounted) setState(() => _status = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() { _timer?.cancel(); _code.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(_presence ? 'QR для старшего' : 'QR для клиента')),
    body: SingleChildScrollView(padding: const EdgeInsets.all(20), child: Center(
      child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 460), child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(_seconds > 0 ? 'Осталось $_seconds сек.' : 'Срок QR истек',
            textAlign: TextAlign.center, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 16),
          if (_seconds > 0) Center(child: DecoratedBox(
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
            child: Padding(padding: const EdgeInsets.all(12),
              child: QrImageView(data: widget.challenge['confirmation_url'].toString(), size: 220)))),
          const SizedBox(height: 16),
          Text(_presence ? 'Покажите QR старшему этой заявки. Самостоятельно отмечать других исполнителей не нужно.'
            : _guest ? 'Представитель заказчика сканирует QR и сверяет весь список. Полученный код введите ниже.'
            : 'Клиент сканирует этот QR в GPM и подтверждает перечисленных исполнителей.'),
          if (!_presence) ...[
            const SizedBox(height: 12),
            Text('В списке: ${widget.challenge['participants']}'),
            SelectableText('Резервный код: ${widget.challenge['request_code']}'),
          ],
          if (_guest) ...[
            const SizedBox(height: 16),
            TextField(key: const Key('crew_guest_code'), controller: _code,
              keyboardType: TextInputType.number, maxLength: 6,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: const InputDecoration(labelText: 'Код от представителя заказчика')),
            FilledButton(onPressed: _seconds > 0 && !_busy ? _complete : null,
              child: const Text('Подтвердить код')),
          ],
          if (_status.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_status)),
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Вернуться к табелю')),
        ],
      )),
    )),
  );
}

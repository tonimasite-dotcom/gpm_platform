import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../main.dart' show gpmApi;
import '../../theme/gpm_theme.dart';

String? attendanceTokenFromQr(String rawValue) {
  final raw = rawValue.trim();
  if (raw.startsWith('gpm-attendance:')) {
    final token = raw.substring('gpm-attendance:'.length).trim();
    return token.isEmpty ? null : token;
  }
  final uri = Uri.tryParse(raw);
  if (uri == null || uri.pathSegments.length < 3) return null;
  final segments = uri.pathSegments;
  final marker = segments.length - 3;
  if (segments[marker] != 'attendance' || segments[marker + 1] != 'confirm') {
    return null;
  }
  final token = segments.last.trim();
  return token.isEmpty ? null : token;
}

String _attendanceDateTime(dynamic value) {
  final parsed = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (parsed == null) return '—';
  final day = parsed.day.toString().padLeft(2, '0');
  final month = parsed.month.toString().padLeft(2, '0');
  final hour = parsed.hour.toString().padLeft(2, '0');
  final minute = parsed.minute.toString().padLeft(2, '0');
  return '$day.$month.${parsed.year} $hour:$minute';
}

String _attendanceDuration(dynamic value) {
  final minutes = int.tryParse(value?.toString() ?? '');
  if (minutes == null) return '—';
  final hours = minutes ~/ 60;
  final rest = minutes % 60;
  if (hours == 0) return '$rest мин';
  return '$hours ч ${rest.toString().padLeft(2, '0')} мин';
}

class OrderAttendancePanel extends StatefulWidget {
  final String orderId;
  final bool allowClientConfirmation;

  const OrderAttendancePanel({
    super.key,
    required this.orderId,
    this.allowClientConfirmation = false,
  });

  @override
  State<OrderAttendancePanel> createState() => _OrderAttendancePanelState();
}

class _OrderAttendancePanelState extends State<OrderAttendancePanel> {
  late Future<Map<String, dynamic>> _future;
  bool _confirming = false;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _future = gpmApi.getOrderAttendance(widget.orderId);
  }

  Future<void> _scan() async {
    final rawValue = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (_) => const AttendanceScannerScreen()),
    );
    if (!mounted || rawValue == null) return;
    final token = attendanceTokenFromQr(rawValue);
    if (token == null) {
      _showError('Это не QR-код учета GPM');
      return;
    }
    await _confirm(token: token);
  }

  Future<void> _enterCode() async {
    final controller = TextEditingController();
    final code = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Код исполнителя'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 8,
          textCapitalization: TextCapitalization.characters,
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp('[A-Za-z0-9]')),
            UpperCaseTextFormatter(),
          ],
          decoration: const InputDecoration(
            hintText: 'Например, 8K7M2P4Q',
            helperText: 'Код действует 1 минуту',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, controller.text.trim().toUpperCase()),
            child: const Text('Подтвердить'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (!mounted || code == null || code.length != 8) return;
    await _confirm(requestCode: code);
  }

  Future<void> _confirm({String token = '', String requestCode = ''}) async {
    setState(() => _confirming = true);
    try {
      final preview = await gpmApi.previewAttendanceConfirmation(
        token: token,
        requestCode: requestCode,
      );
      if (!mounted) return;
      final approved = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(
            preview['action'] == 'check_out'
                ? 'Подтвердить уход'
                : 'Подтвердить приход',
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(preview['order_title']?.toString() ?? widget.orderId),
              const SizedBox(height: 12),
              const Text('Исполнитель:'),
              Text(
                preview['worker_name']?.toString() ?? 'Исполнитель',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              const Text(
                'Подтверждайте только если исполнитель находится рядом с вами.',
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Отмена'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Подтвердить'),
            ),
          ],
        ),
      );
      if (approved != true) return;
      final attendance = await gpmApi.confirmAttendance(
        token: token,
        requestCode: requestCode,
      );
      if (!mounted) return;
      setState(_reload);
      final action = attendance['status'] == 'completed' ? 'Уход' : 'Приход';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('$action подтверждён'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (error) {
      if (mounted) _showError(error.toString());
    } finally {
      if (mounted) setState(() => _confirming = false);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: FutureBuilder<Map<String, dynamic>>(
          future: _future,
          builder: (context, snapshot) {
            final data = snapshot.data;
            final rows = (data?['attendance'] as List? ?? const [])
                .whereType<Map>()
                .toList();
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.fact_check_outlined),
                    const SizedBox(width: 8),
                    const Expanded(
                      child: Text(
                        'Онлайн-табель',
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Обновить',
                      onPressed: () => setState(_reload),
                      icon: const Icon(Icons.refresh),
                    ),
                  ],
                ),
                if (snapshot.connectionState == ConnectionState.waiting)
                  const LinearProgressIndicator()
                else if (snapshot.hasError)
                  Text(
                    'Не удалось загрузить табель: ${snapshot.error}',
                    style: const TextStyle(color: Colors.red),
                  )
                else if (rows.isEmpty)
                  const Text('Назначенных исполнителей пока нет')
                else
                  ...rows.map((row) => _AttendanceRow(row: row)),
                if (widget.allowClientConfirmation) ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: _confirming ? null : _scan,
                          icon: const Icon(Icons.qr_code_scanner),
                          label: const Text('Сканировать QR'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton.outlined(
                        tooltip: 'Ввести код',
                        onPressed: _confirming ? null : _enterCode,
                        icon: const Icon(Icons.password_outlined),
                      ),
                    ],
                  ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class WorkerAttendancePanel extends StatefulWidget {
  final String orderId;

  const WorkerAttendancePanel({super.key, required this.orderId});

  @override
  State<WorkerAttendancePanel> createState() => _WorkerAttendancePanelState();
}

class _WorkerAttendancePanelState extends State<WorkerAttendancePanel> {
  late Future<Map<String, dynamic>> _future;
  bool _creating = false;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _future = gpmApi.getOrderAttendance(widget.orderId);
  }

  Future<void> _createChallenge() async {
    setState(() => _creating = true);
    try {
      final challenge = await gpmApi.createAttendanceChallenge(widget.orderId);
      if (!mounted) return;
      final completed = await Navigator.push<bool>(
        context,
        MaterialPageRoute(
          builder: (_) => AttendanceChallengeScreen(
            orderId: widget.orderId,
            challenge: challenge,
          ),
        ),
      );
      if (!mounted) return;
      setState(_reload);
      if (completed == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Отметка сохранена в табеле'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString()), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        final rows = (snapshot.data?['attendance'] as List? ?? const [])
            .whereType<Map>()
            .toList();
        final row = rows.isEmpty ? null : rows.first;
        final status = row?['status']?.toString() ?? 'not_started';
        final completed = status == 'completed';
        final buttonText = status == 'checked_in'
            ? 'Отметить уход'
            : 'Отметить приход';
        return Card(
          margin: EdgeInsets.zero,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Учет рабочего времени',
                  style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                if (snapshot.connectionState == ConnectionState.waiting)
                  const LinearProgressIndicator()
                else if (snapshot.hasError)
                  Text(
                    'Не удалось загрузить отметки: ${snapshot.error}',
                    style: const TextStyle(color: Colors.red),
                  )
                else if (row != null)
                  _AttendanceRow(row: row),
                if (!completed) ...[
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: _creating ? null : _createChallenge,
                      icon: const Icon(Icons.qr_code_2),
                      label: Text(buttonText),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class AttendanceChallengeScreen extends StatefulWidget {
  final String orderId;
  final Map<String, dynamic> challenge;

  const AttendanceChallengeScreen({
    super.key,
    required this.orderId,
    required this.challenge,
  });

  @override
  State<AttendanceChallengeScreen> createState() =>
      _AttendanceChallengeScreenState();
}

class _AttendanceChallengeScreenState extends State<AttendanceChallengeScreen> {
  final _confirmationCodeController = TextEditingController();
  Timer? _timer;
  int _secondsLeft = 60;
  bool _submitting = false;
  bool _checking = false;

  bool get _isGuest => widget.challenge['verifier_mode'] == 'guest_code';
  String get _action => widget.challenge['action']?.toString() ?? 'check_in';

  @override
  void initState() {
    super.initState();
    _syncCountdown();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      _syncCountdown();
    });
  }

  void _syncCountdown() {
    final expiresAt = DateTime.tryParse(
      widget.challenge['expires_at']?.toString() ?? '',
    )?.toLocal();
    final next = expiresAt == null
        ? 0
        : expiresAt.difference(DateTime.now()).inSeconds.clamp(0, 60);
    setState(() => _secondsLeft = next);
    if (next == 0) _timer?.cancel();
  }

  Future<void> _submitGuestCode() async {
    final code = _confirmationCodeController.text.trim();
    if (code.length != 6) return;
    setState(() => _submitting = true);
    try {
      await gpmApi.completeGuestAttendance(code);
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString()), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _checkClientConfirmation() async {
    setState(() => _checking = true);
    try {
      final data = await gpmApi.getOrderAttendance(widget.orderId);
      final rows = (data['attendance'] as List? ?? const []).whereType<Map>();
      final status = rows.isEmpty
          ? 'not_started'
          : rows.first['status']?.toString() ?? 'not_started';
      final confirmed = _action == 'check_in'
          ? status == 'checked_in' || status == 'completed'
          : status == 'completed';
      if (confirmed && mounted) {
        Navigator.pop(context, true);
        return;
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Клиент еще не подтвердил отметку')),
        );
      }
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _confirmationCodeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final url = widget.challenge['confirmation_url']?.toString() ?? '';
    final requestCode = widget.challenge['request_code']?.toString() ?? '';
    final confirmationUri = Uri.tryParse(url);
    final manualUrl = confirmationUri == null
        ? ''
        : confirmationUri.replace(path: '/attendance', query: '').toString();
    final expired = _secondsLeft == 0;
    final title = _action == 'check_out'
        ? 'Подтверждение ухода'
        : 'Подтверждение прихода';
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Text(
              expired ? 'Срок действия истек' : 'Осталось $_secondsLeft сек.',
              style: TextStyle(
                color: expired ? Colors.red : GpmColors.red,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            if (!expired && url.isNotEmpty)
              Container(
                color: Colors.white,
                padding: const EdgeInsets.all(12),
                child: QrImageView(data: url, size: 220),
              ),
            const SizedBox(height: 16),
            Text(
              _isGuest
                  ? 'Покажите QR представителю заказчика. После подтверждения он назовет шестизначный код.'
                  : 'Покажите QR клиенту. Клиент должен отсканировать его в приложении GPM.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 14),
            const Text('Резервный код запроса'),
            SelectableText(
              requestCode,
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                letterSpacing: 3,
              ),
            ),
            if (_isGuest && manualUrl.isNotEmpty) ...[
              const SizedBox(height: 8),
              const Text(
                'Если камера не работает, заказчик может открыть:',
                textAlign: TextAlign.center,
              ),
              SelectableText(manualUrl, textAlign: TextAlign.center),
            ],
            if (_isGuest) ...[
              const SizedBox(height: 20),
              TextField(
                controller: _confirmationCodeController,
                enabled: !expired && !_submitting,
                keyboardType: TextInputType.number,
                maxLength: 6,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: const InputDecoration(
                  labelText: 'Код от заказчика',
                  hintText: '000000',
                ),
              ),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: expired || _submitting ? null : _submitGuestCode,
                  child: const Text('Сохранить отметку'),
                ),
              ),
            ] else ...[
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: expired || _checking
                      ? null
                      : _checkClientConfirmation,
                  child: const Text('Проверить подтверждение'),
                ),
              ),
            ],
            if (expired) ...[
              const SizedBox(height: 12),
              const Text(
                'Закройте экран и создайте новый QR-код.',
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class AttendanceScannerScreen extends StatefulWidget {
  const AttendanceScannerScreen({super.key});

  @override
  State<AttendanceScannerScreen> createState() =>
      _AttendanceScannerScreenState();
}

class _AttendanceScannerScreenState extends State<AttendanceScannerScreen> {
  final MobileScannerController _controller = MobileScannerController(
    formats: const [BarcodeFormat.qrCode],
  );
  bool _handled = false;

  void _onDetect(BarcodeCapture capture) {
    if (_handled) return;
    for (final barcode in capture.barcodes) {
      final value = barcode.rawValue;
      if (value == null || value.trim().isEmpty) continue;
      _handled = true;
      _controller.stop();
      Navigator.pop(context, value);
      return;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Сканирование QR')),
      body: Stack(
        fit: StackFit.expand,
        children: [
          MobileScanner(controller: _controller, onDetect: _onDetect),
          Center(
            child: Container(
              width: 250,
              height: 250,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white, width: 3),
                borderRadius: BorderRadius.circular(18),
              ),
            ),
          ),
          const Positioned(
            left: 24,
            right: 24,
            bottom: 36,
            child: Text(
              'Наведите камеру на QR-код исполнителя',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white, fontSize: 16),
            ),
          ),
        ],
      ),
    );
  }
}

class _AttendanceRow extends StatelessWidget {
  final Map<dynamic, dynamic> row;

  const _AttendanceRow({required this.row});

  @override
  Widget build(BuildContext context) {
    final status = row['status']?.toString() ?? 'not_started';
    final color = switch (status) {
      'checked_in' => Colors.orange,
      'completed' => Colors.green,
      _ => Colors.grey,
    };
    final label = switch (status) {
      'checked_in' => 'На объекте',
      'completed' => 'Завершено',
      _ => 'Не отмечен',
    };
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  row['worker_name']?.toString() ?? 'Исполнитель',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  label,
                  style: TextStyle(fontSize: 11, color: color),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Приход: ${_attendanceDateTime(row['check_in_at'])}  '
            'Уход: ${_attendanceDateTime(row['check_out_at'])}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (status == 'completed')
            Text(
              'Фактически: ${_attendanceDuration(row['duration_minutes'])}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      ),
    );
  }
}

class UpperCaseTextFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    return newValue.copyWith(text: newValue.text.toUpperCase());
  }
}

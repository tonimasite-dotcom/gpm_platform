import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';

import 'worker_rating.dart';

Future<bool?> showRatingActionDialog({
  required BuildContext context,
  required String title,
  required String submitLabel,
  required Future<void> Function(
    String? result,
    String reason,
    String requestId,
  )
  save,
  Map<String, String>? results,
  String? initialResult,
  int? previousDelta,
  bool requireReason = true,
  String? description,
}) => showDialog<bool>(
  context: context,
  barrierDismissible: false,
  builder: (_) => _RatingActionDialog(
    title: title,
    submitLabel: submitLabel,
    save: save,
    results: results,
    initialResult: initialResult,
    previousDelta: previousDelta,
    requireReason: requireReason,
    description: description,
  ),
);

class _RatingActionDialog extends StatefulWidget {
  const _RatingActionDialog({
    required this.title,
    required this.submitLabel,
    required this.save,
    required this.requireReason,
    this.results,
    this.initialResult,
    this.previousDelta,
    this.description,
  });

  final String title;
  final String submitLabel;
  final Future<void> Function(String?, String, String) save;
  final Map<String, String>? results;
  final String? initialResult;
  final int? previousDelta;
  final bool requireReason;
  final String? description;

  @override
  State<_RatingActionDialog> createState() => _RatingActionDialogState();
}

class _RatingActionDialogState extends State<_RatingActionDialog> {
  final _form = GlobalKey<FormState>();
  final _reason = TextEditingController();
  String? _result;
  bool _saving = false;
  String? _error;
  String? _signature;
  String? _requestId;

  @override
  void initState() {
    super.initState();
    _result = widget.initialResult;
  }

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    final reason = _reason.text.trim();
    final signature = jsonEncode([_result, reason]);
    if (_signature != signature) {
      _signature = signature;
      _requestId =
          '${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(1 << 32)}';
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.save(_result, reason, _requestId!);
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = error.toString().replaceFirst(
            RegExp(r'^(Exception|Bad state):\s*'),
            '',
          );
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final reasonRequired =
        widget.requireReason || {'good', 'fail'}.contains(_result);
    final delta = _result == 'void' ? 0 : workerResultDeltas[_result];
    String points(int value) => '${value > 0 ? '+' : ''}$value';
    return PopScope(
      canPop: !_saving,
      child: AlertDialog(
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        scrollable: true,
        title: Text(widget.title),
        content: SizedBox(
          width: 420,
          child: Form(
            key: _form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (widget.description != null) ...[
                  Text(widget.description!),
                  const SizedBox(height: 12),
                ],
                if (widget.results != null) ...[
                  DropdownButtonFormField<String>(
                    isExpanded: true,
                    initialValue: _result,
                    decoration: const InputDecoration(labelText: 'Результат'),
                    items: [
                      for (final entry in widget.results!.entries)
                        DropdownMenuItem(
                          value: entry.key,
                          child: Text(
                            entry.value,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                    onChanged: _saving
                        ? null
                        : (value) => setState(() => _result = value),
                    validator: (value) =>
                        value == null ? 'Выберите результат' : null,
                  ),
                  const SizedBox(height: 12),
                ] else if (_result != null) ...[
                  Text(workerRatingResultLabel(_result)),
                  const SizedBox(height: 8),
                ],
                if (delta != null) ...[
                  Text(
                    widget.previousDelta == null
                        ? workerResultEffect(_result!)
                        : 'Было: ${points(widget.previousDelta!)}. '
                              'Станет: ${points(delta)}. '
                              'Изменение общих баллов: ${points(delta - widget.previousDelta!)}.',
                  ),
                  const SizedBox(height: 8),
                ],
                const Text('Оценка не меняет завершение заявки и начисления.'),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _reason,
                  enabled: !_saving,
                  minLines: 2,
                  maxLines: 4,
                  maxLength: 1000,
                  decoration: InputDecoration(
                    labelText: reasonRequired
                        ? 'Причина'
                        : 'Комментарий (необязательно)',
                  ),
                  validator: (value) =>
                      reasonRequired && (value?.trim().length ?? 0) < 5
                      ? 'Укажите причину: не менее 5 символов'
                      : null,
                ),
                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Можно повторить запрос. Если оценка изменилась, закройте окно и обновите историю.',
                  ),
                ],
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: _saving ? null : () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(_saving ? 'Сохранение…' : widget.submitLabel),
          ),
        ],
      ),
    );
  }
}

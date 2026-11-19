import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import '../../theme/gpm_theme.dart';
import '../../widgets/gpm_surface.dart';
import '../../widgets/rating_action_dialog.dart';
import '../../widgets/worker_rating.dart';

Map<String, dynamic> _ratingMap(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : {};
int _ratingNumber(Object? value) => int.tryParse('$value') ?? 0;
String _points(Object? value) {
  final number = _ratingNumber(value);
  return '${number > 0 ? '+' : ''}$number';
}

String _ratingDate(Object? value) {
  final date = DateTime.tryParse('$value')?.toLocal();
  if (date == null) return '';
  String two(int number) => number.toString().padLeft(2, '0');
  return '${two(date.day)}.${two(date.month)}.${date.year} '
      '${two(date.hour)}:${two(date.minute)}';
}

void _requireSaved(Map<String, dynamic> response) {
  if (response['success'] != true) {
    throw Exception(
      response['error'] ?? 'Не удалось сохранить. Повторите запрос.',
    );
  }
}

class WorkerRatingScreen extends StatefulWidget {
  const WorkerRatingScreen({
    super.key,
    this.workerId,
    this.workerName,
    this.orderId,
  });
  final String? workerId;
  final String? workerName;
  final String? orderId;

  @override
  State<WorkerRatingScreen> createState() => _WorkerRatingScreenState();
}

class _WorkerRatingScreenState extends State<WorkerRatingScreen> {
  Map<String, dynamic> _summary = {};
  final List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  bool _fetching = false;
  bool _hasMore = false;
  int _offset = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool reset = true}) async {
    if (!mounted || _fetching) return;
    setState(() {
      _fetching = true;
      _error = null;
    });
    try {
      final response = await gpmApi.getWorkerRatingHistory(
        workerId: widget.workerId,
        orderId: widget.orderId,
        offset: reset ? 0 : _offset,
      );
      final rows = (response['history'] as List? ?? [])
          .map(_ratingMap)
          .toList();
      if (!mounted) return;
      setState(() {
        _summary = _ratingMap(response['summary']);
        if (reset) _items.clear();
        final seen = _items.map((item) => item['order_id']).toSet();
        for (final row in rows) {
          if (seen.add(row['order_id'])) _items.add(row);
        }
        _offset = _ratingNumber(response['next_offset']);
        _hasMore = response['has_more'] == true;
      });
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Не удалось загрузить рейтинг. Попробуйте еще раз.',
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _fetching = false;
        });
      }
    }
  }

  Future<void> _review(Map<String, dynamic> item) async {
    await showRatingActionDialog(
      context: context,
      title: 'Оценить исполнителя',
      submitLabel: 'Сохранить оценку',
      results: workerResultLabels,
      requireReason: false,
      description: widget.workerName,
      save: (result, reason, _) async {
        _requireSaved(
          await gpmApi.completeOrderWithResult(
            orderId: item['order_id'].toString(),
            workerId: widget.workerId!,
            result: result!,
            reason: reason,
          ),
        );
      },
    );
    await _load();
  }

  Future<void> _correct(
    Map<String, dynamic> item,
    Map<String, dynamic> review,
  ) async {
    final results = Map<String, String>.from(workerResultLabels)
      ..remove(review['result']);
    if (review['result'] != 'void') results['void'] = 'Аннулировать оценку';
    await showRatingActionDialog(
      context: context,
      title: 'Исправить оценку',
      submitLabel: 'Сохранить исправление',
      results: results,
      previousDelta: _ratingNumber(review['rating_delta']),
      description:
          'Предыдущая оценка останется в истории. Укажите причину изменения.',
      save: (result, reason, requestId) async {
        _requireSaved(
          await gpmApi.correctWorkerRating(
            orderId: item['order_id'].toString(),
            workerId: widget.workerId!,
            result: result!,
            reason: reason,
            expectedRevision: _ratingNumber(review['revision'] ?? 1),
            requestId: requestId,
          ),
        );
      },
    );
    await _load();
  }

  Future<void> _appeal(
    Map<String, dynamic> item,
    Map<String, dynamic> review,
  ) async {
    await showRatingActionDialog(
      context: context,
      title: 'Обращение по оценке',
      submitLabel: 'Отправить обращение',
      description:
          'Опишите, с чем вы не согласны. Логист проверит факты и ответит. До решения баллы сохраняются.',
      save: (_, reason, requestId) async {
        _requireSaved(
          await gpmApi.appealWorkerRating(
            orderId: item['order_id'].toString(),
            reason: reason,
            expectedRevision: _ratingNumber(review['revision'] ?? 1),
            requestId: requestId,
          ),
        );
      },
    );
    await _load();
  }

  Future<void> _resolve(
    Map<String, dynamic> item,
    Map<String, dynamic> review,
  ) async {
    await showRatingActionDialog(
      context: context,
      title: 'Ответить и оставить оценку',
      submitLabel: 'Подтвердить оценку',
      description:
          'Объясните решение рабочему. Если оценка была ошибочной, отмените это действие и выберите «Исправить оценку».',
      save: (_, reason, requestId) async {
        _requireSaved(
          await gpmApi.resolveWorkerRatingAppeal(
            orderId: item['order_id'].toString(),
            workerId: widget.workerId!,
            reason: reason,
            expectedRevision: _ratingNumber(review['revision'] ?? 1),
            requestId: requestId,
          ),
        );
      },
    );
    await _load();
  }

  Widget _summaryCard() {
    final count = _ratingNumber(_summary['review_count']);
    final positive = _summary['positive_percent'];
    return GpmSurface(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Баллы рейтинга'),
          Text(
            '${_ratingNumber(_summary['rating'])}',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              Chip(label: Text('Оценок: $count')),
              if (count > 0 && positive != null)
                Chip(label: Text('Положительных: $positive%')),
            ],
          ),
          if (count == 0)
            const Text(
              'Сохраненных оценок пока нет. Это не означает плохую работу.',
            ),
          const SizedBox(height: 8),
          Text(
            'С нареканиями: ${_ratingNumber(_summary['concern_count'])}. '
            'Не справился: ${_ratingNumber(_summary['unsuccessful_count'])}. '
            'Аннулировано: ${_ratingNumber(_summary['void_count'])}.',
          ),
          if (_summary['has_legacy_balance'] == true) ...[
            const SizedBox(height: 8),
            const Text(
              'Общие баллы включают более ранний баланс. Число оценок и доля положительных рассчитаны по сохраненным записям. Старые баллы не пересчитывались.',
            ),
          ],
        ],
      ),
    );
  }

  Widget _historyCard(Map<String, dynamic> item) {
    final review = _ratingMap(item['review']);
    final hasReview = item['review'] is Map;
    final manages = widget.workerId != null && item['can_manage'] == true;
    final appeals = (review['appeals'] as List? ?? []).map(_ratingMap).toList();
    final open = appeals.any((appeal) => appeal['status'] == 'open');
    final revision = _ratingNumber(review['revision'] ?? 1);
    final alreadyAppealed = appeals.any(
      (appeal) => appeal['revision'] == revision,
    );
    final revisions = (review['revisions'] as List? ?? [])
        .map(_ratingMap)
        .toList();
    return GpmSurface(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            item['order_title']?.toString() ?? 'Заявка',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (_ratingDate(item['date']).isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              _ratingDate(item['date']),
              style: const TextStyle(color: GpmColors.muted),
            ),
          ],
          const SizedBox(height: 8),
          if (!hasReview)
            const Text('Оценка пока не выставлена')
          else ...[
            Text(
              'Оценка: ${workerRatingResultLabel(review['result'])} · '
              '${_points(review['rating_delta'])}',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            if ((review['reason']?.toString() ?? '').isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Причина: ${review['reason']}'),
            ] else if ({'good', 'fail'}.contains(review['result'])) ...[
              const SizedBox(height: 8),
              const Text('Причина в старой записи не указана.'),
            ],
            if (revisions.length > 1)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                shape: const Border(),
                collapsedShape: const Border(),
                title: Text('История изменений (${revisions.length})'),
                children: [
                  for (final previous in revisions)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(
                        '${workerRatingResultLabel(previous['result'])} · '
                        '${_points(previous['rating_delta'])}',
                      ),
                      subtitle: Text(
                        '${_ratingDate(previous['reviewed_at'])}\n'
                        '${previous['reason'] ?? ''}',
                      ),
                    ),
                ],
              ),
          ],
          for (final appeal in appeals) ...[
            const SizedBox(height: 12),
            Text(
              appeal['status'] == 'open'
                  ? 'Обращение рассматривается'
                  : 'Обращение рассмотрено',
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: appeal['status'] == 'open'
                    ? GpmColors.redInk
                    : GpmColors.graphite,
              ),
            ),
            const SizedBox(height: 4),
            Text(appeal['reason']?.toString() ?? ''),
            if ((appeal['resolution']?.toString() ?? '').isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Ответ: ${appeal['resolution']}'),
            ],
          ],
          if (manages) ...[
            const SizedBox(height: 12),
            if (!hasReview && item['can_review'] == true)
              FilledButton(
                onPressed: _fetching ? null : () => _review(item),
                child: const Text('Оценить исполнителя'),
              ),
            if (hasReview)
              OutlinedButton(
                onPressed: _fetching ? null : () => _correct(item, review),
                child: const Text('Исправить оценку'),
              ),
            if (hasReview && open) ...[
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: _fetching ? null : () => _resolve(item, review),
                child: const Text('Ответить и оставить оценку'),
              ),
            ],
          ] else if (widget.workerId == null &&
              hasReview &&
              review['result'] != 'void' &&
              !open &&
              !alreadyAppealed) ...[
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: _fetching ? null : () => _appeal(item, review),
              child: const Text('Оспорить оценку'),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.workerName == null
              ? 'Мой рейтинг'
              : 'Рейтинг · ${widget.workerName}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 840),
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    key: PageStorageKey(
                      'rating-history-${widget.workerId}-${widget.orderId}',
                    ),
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_error != null) ...[
                        Text(_error!),
                        TextButton(
                          onPressed: _fetching ? null : _load,
                          child: const Text('Повторить'),
                        ),
                      ],
                      _summaryCard(),
                      const WorkerRatingRules(),
                      if (widget.workerId != null)
                        const Text(
                          'Общие показатели — по всем оценкам. Подробная история и действия доступны только по вашим заявкам.',
                        ),
                      if (_items.isEmpty && _error == null)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 20),
                          child: Text(
                            'Здесь появятся оценки и заявки, ожидающие оценки.',
                          ),
                        ),
                      for (final item in _items) _historyCard(item),
                      if (_hasMore) ...[
                        const SizedBox(height: 12),
                        OutlinedButton(
                          onPressed: _fetching
                              ? null
                              : () => _load(reset: false),
                          child: Text(_fetching ? 'Загрузка…' : 'Показать еще'),
                        ),
                      ],
                    ],
                  ),
                ),
        ),
      ),
    );
  }
}

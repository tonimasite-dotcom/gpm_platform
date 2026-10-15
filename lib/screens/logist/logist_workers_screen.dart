import 'dart:async';

import 'package:flutter/material.dart';

import '../../main.dart' show gpmApi;
import 'worker_profile_review_screen.dart';

class LogistWorkersScreen extends StatefulWidget {
  const LogistWorkersScreen({super.key});

  @override
  State<LogistWorkersScreen> createState() => _LogistWorkersScreenState();
}

class _LogistWorkersScreenState extends State<LogistWorkersScreen> {
  final _search = TextEditingController();
  final _workers = <Map<String, dynamic>>[];
  Timer? _debounce;
  int _revision = 0;
  int _offset = 0;
  bool _loading = false;
  bool _hasMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _searchChanged(String value) {
    _debounce?.cancel();
    ++_revision;
    _debounce = Timer(const Duration(milliseconds: 300), () => _load());
  }

  Future<void> _load({bool more = false}) async {
    if (more && _loading) return;
    _debounce?.cancel();
    final revision = ++_revision;
    final offset = more ? _offset : 0;
    setState(() {
      _loading = true;
      _error = null;
      if (!more) {
        _workers.clear();
        _hasMore = false;
        _offset = 0;
      }
    });
    try {
      final result = await gpmApi.getWorkerDirectory(
        query: _search.text,
        offset: offset,
      );
      if (!mounted || revision != _revision) return;
      final rows = result['workers'];
      if (rows is! List) {
        throw const FormatException('Invalid worker directory');
      }
      final workers = rows
          .map((row) => Map<String, dynamic>.from(row as Map))
          .toList();
      setState(() {
        _workers.addAll(workers);
        _offset = (result['next_offset'] as int?) ?? offset + workers.length;
        _hasMore = result['has_more'] == true;
      });
    } catch (_) {
      if (mounted && revision == _revision) {
        setState(() => _error = 'Не удалось загрузить исполнителей');
      }
    } finally {
      if (mounted && revision == _revision) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _openWorker(Map<String, dynamic> worker) async {
    final id = worker['id'].toString();
    final changed = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => WorkerProfileReviewScreen(workerId: id),
      ),
    );
    if (changed != true || !mounted) return;
    try {
      final profile = await gpmApi.getWorkerProfile(id);
      if (!mounted || profile == null) return;
      final index = _workers.indexWhere((row) => row['id'].toString() == id);
      if (index >= 0) {
        setState(() => _workers[index] = {..._workers[index], ...profile});
      }
    } catch (_) {
      if (mounted) await _load();
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Text(
          'Исполнители',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
      ),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: TextField(
          controller: _search,
          onChanged: _searchChanged,
          onSubmitted: (_) => _load(),
          textInputAction: TextInputAction.search,
          decoration: const InputDecoration(
            labelText: 'Поиск по имени, логину или телефону',
            prefixIcon: Icon(Icons.search),
          ),
        ),
      ),
      const SizedBox(height: 8),
      if (_loading) const LinearProgressIndicator(),
      if (_error != null)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            children: [
              Text(_error!),
              TextButton(
                onPressed: () => _load(),
                child: const Text('Повторить'),
              ),
            ],
          ),
        ),
      Expanded(
        child: RefreshIndicator(
          onRefresh: () => _load(),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            children: [
              if (_workers.isEmpty && !_loading && _error == null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 32),
                  child: Text(
                    _search.text.trim().isEmpty
                        ? 'Исполнителей пока нет'
                        : 'Исполнители не найдены',
                    textAlign: TextAlign.center,
                  ),
                ),
              for (final worker in _workers)
                Card(
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    leading: const CircleAvatar(
                      child: Icon(Icons.person_outline),
                    ),
                    title: Text(
                      (worker['display_name'] ??
                              worker['username'] ??
                              'Исполнитель')
                          .toString(),
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    subtitle: Text(
                      [
                        if ((worker['phone_number'] ?? '')
                            .toString()
                            .isNotEmpty)
                          worker['phone_number'].toString(),
                        worker['nationality'] == null
                            ? 'Гражданство не указано'
                            : worker['nationality'] == true
                            ? 'РФ'
                            : 'Не РФ',
                        worker['employment_type'] == 'state'
                            ? 'Штатный'
                            : 'Подрядчик',
                        if (worker['is_active'] == false) 'Аккаунт отключён',
                      ].join(' · '),
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _openWorker(worker),
                  ),
                ),
              if (_hasMore)
                OutlinedButton(
                  onPressed: _loading ? null : () => _load(more: true),
                  child: const Text('Показать ещё'),
                ),
            ],
          ),
        ),
      ),
    ],
  );
}

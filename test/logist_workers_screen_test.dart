import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/logist/logist_home_screen.dart';
import 'package:gpm_platform/screens/logist/logist_workers_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';

Map<String, dynamic> _worker(String id, String name) => {
  'id': id,
  'display_name': name,
  'phone_number': '+7 900 123-45-67',
  'nationality': true,
  'employment_type': 'contract',
  'is_active': true,
};

Map<String, dynamic> _page(
  List<Map<String, dynamic>> workers, {
  bool hasMore = false,
  int offset = 0,
}) => {
  'workers': workers,
  'has_more': hasMore,
  'next_offset': offset + workers.length,
};

class _DirectoryApi extends GpmApiService {
  final profile = _worker('without-orders', 'Рабочий без заказов');
  final requests = <int>[];
  String? editedWorker;
  bool failNext = false;

  @override
  Future<List<Map<String, dynamic>>> getOrders() async => [];

  @override
  Future<Map<String, dynamic>> getWorkerDirectory({
    String query = '',
    int offset = 0,
    int limit = 20,
  }) async {
    requests.add(offset);
    if (failNext) {
      failNext = false;
      throw StateError('synthetic outage');
    }
    return offset == 0
        ? _page([Map.of(profile)], hasMore: true)
        : _page([_worker('second-worker', 'Другой рабочий')], offset: offset);
  }

  @override
  Future<Map<String, dynamic>?> getWorkerProfile(String workerId) async =>
      Map.of(profile);

  @override
  Future<Map<String, dynamic>> updateWorkerStaffProfile(
    String workerId,
    Map<String, dynamic> patch,
  ) async {
    editedWorker = workerId;
    profile.addAll(patch);
    return Map.of(profile);
  }
}

class _SearchApi extends GpmApiService {
  final responses = <String, Completer<Map<String, dynamic>>>{};

  @override
  Future<Map<String, dynamic>> getWorkerDirectory({
    String query = '',
    int offset = 0,
    int limit = 20,
  }) {
    if (query.isEmpty) return Future.value(_page([]));
    return (responses[query] = Completer<Map<String, dynamic>>()).future;
  }
}

void main() {
  setUp(() => dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n'));

  testWidgets('logist edits a worker from the directory without an order', (
    tester,
  ) async {
    // Five navigation items must also fit on a small phone.
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = _DirectoryApi();
    app.gpmApi = api;
    await tester.pumpWidget(const MaterialApp(home: LogistHomeScreen()));
    await tester.pumpAndSettle();
    expect(find.text('Заказов пока нет'), findsOneWidget);
    await tester.tap(find.text('Исполнители'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Рабочий без заказов'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<bool>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Не РФ').last);
    await tester.pumpAndSettle();
    expect(
      find.text(
        'После изменения гражданства потребуется повторное подтверждение паспорта.',
      ),
      findsOneWidget,
    );
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Штатный исполнитель').last);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Сохранить'));
    await tester.tap(find.text('Сохранить'));
    await tester.pumpAndSettle();
    expect(api.editedWorker, 'without-orders');
    expect(api.profile['nationality'], false);
    expect(api.profile['employment_type'], 'state');
    expect(find.text('Профиль исполнителя'), findsNothing);
    expect(find.textContaining('Не РФ · Штатный'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'pagination retries a failed page without losing earlier workers',
    (tester) async {
      final api = _DirectoryApi();
      app.gpmApi = api;
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: LogistWorkersScreen())),
      );
      await tester.pumpAndSettle();
      api.failNext = true;
      await tester.tap(find.text('Показать ещё'));
      await tester.pumpAndSettle();
      expect(find.text('Рабочий без заказов'), findsOneWidget);
      expect(find.text('Не удалось загрузить исполнителей'), findsOneWidget);
      await tester.tap(find.text('Показать ещё'));
      await tester.pumpAndSettle();
      expect(api.requests, [0, 1, 1]);
      expect(find.text('Рабочий без заказов'), findsOneWidget);
      expect(find.text('Другой рабочий'), findsOneWidget);
      expect(find.text('Показать ещё'), findsNothing);
      expect(find.text('Не удалось загрузить исполнителей'), findsNothing);
    },
  );

  testWidgets('older search responses cannot replace newer results', (
    tester,
  ) async {
    final api = _SearchApi();
    app.gpmApi = api;
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: LogistWorkersScreen())),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'старый');
    await tester.pump(const Duration(milliseconds: 300));
    await tester.enterText(find.byType(TextField), 'новый');
    await tester.pump(const Duration(milliseconds: 300));
    api.responses['новый']!.complete(
      _page([_worker('new', 'Новый результат')]),
    );
    await tester.pumpAndSettle();
    api.responses['старый']!.complete(
      _page([_worker('old', 'Старый результат')]),
    );
    await tester.pumpAndSettle();
    expect(find.text('Новый результат'), findsOneWidget);
    expect(find.text('Старый результат'), findsNothing);
  });
}

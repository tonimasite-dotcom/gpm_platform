import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/ratings/worker_rating_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'package:gpm_platform/widgets/worker_rating.dart';

class RatingUiApi extends GpmApiService {
  Map<String, dynamic>? review = {
    'result': 'fail', 'rating_delta': -2, 'revision': 1,
    'reason': 'Работы выполнены не полностью',
    'reviewed_at': '2026-11-19T12:00:00Z',
    'revisions': [
      {'result': 'fail', 'rating_delta': -2, 'revision': 1,
        'reason': 'Работы выполнены не полностью', 'reviewed_at': '2026-11-19T12:00:00Z'},
    ],
    'appeals': <Map<String, dynamic>>[],
  };
  bool allowManage = true;
  bool failAppealOnce = false;
  bool failCorrectionAfterSaveOnce = false;
  bool conflict = false;
  bool paged = false;
  int appliedCorrections = 0;
  int statusCalls = 0;
  final appealRequests = <String>[];
  final correctionRequests = <String>[];
  final offsets = <int>[];

  Map<String, dynamic> snapshot() => review == null ? {} :
      Map<String, dynamic>.from(jsonDecode(jsonEncode(review)) as Map);

  @override
  Future<Map<String, dynamic>> getWorkerRatingHistory({
    String? workerId, String? orderId, int offset = 0, int limit = 20,
  }) async {
    offsets.add(offset);
    final record = snapshot();
    final positive = {'success', 'excellent'}.contains(record['result']);
    final voided = record['result'] == 'void';
    return {
      'summary': {
        'rating': record['rating_delta'] ?? 0,
        'review_count': review == null || voided ? 0 : 1,
        'positive_percent': positive ? 100 : 0,
        'concern_count': record['result'] == 'good' ? 1 : 0,
        'unsuccessful_count': record['result'] == 'fail' ? 1 : 0,
        'void_count': voided ? 1 : 0,
        'has_legacy_balance': false,
      },
      'history': [
        {
          'order_id': offset == 0 ? 'job-1' : 'job-2',
          'order_title': offset == 0 ? 'Синтетическая заявка' : 'Вторая заявка',
          'order_status': 'CONVERTED',
          'can_manage': workerId != null && allowManage,
          'can_review': workerId != null && allowManage && review == null,
          'review': review == null ? null : record,
          'date': '2026-11-19T12:00:00Z',
        },
      ],
      'has_more': paged && offset == 0,
      'next_offset': offset + 1,
      'scope': workerId == null ? 'self' : 'own_orders',
    };
  }

  @override
  Future<Map<String, dynamic>> appealWorkerRating({
    required String orderId, required String reason,
    required int expectedRevision, required String requestId,
  }) async {
    appealRequests.add(requestId);
    if (failAppealOnce) {
      failAppealOnce = false;
      throw Exception('Связь потеряна. Повторите запрос.');
    }
    final appeals = review!['appeals'] as List;
    appeals.add({'revision': expectedRevision, 'reason': reason,
      'status': 'open', 'created_at': '2026-11-19T12:10:00Z'});
    return {'success': true};
  }

  @override
  Future<Map<String, dynamic>> correctWorkerRating({
    required String orderId, required String workerId, required String result,
    required String reason, required int expectedRevision, required String requestId,
  }) async {
    correctionRequests.add(requestId);
    if (review!['request_id'] == requestId) {
      return {'success': true, 'already_recorded': true};
    }
    if (conflict) {
      throw Exception('Оценка уже изменилась. Обновите историю');
    }
    appliedCorrections++;
    final newRecord = <String, dynamic>{
      'result': result,
      'rating_delta': workerResultDeltas[result] ?? 0,
      'revision': expectedRevision + 1,
      'reason': reason,
      'reviewed_at': '2026-11-19T12:15:00Z',
      'request_id': requestId,
    };
    review!.addAll(newRecord);
    final versions = List<dynamic>.from(review!['revisions'] as List)..add(newRecord);
    review!['revisions'] = versions;
    if (failCorrectionAfterSaveOnce) {
      failCorrectionAfterSaveOnce = false;
      throw Exception('Ответ сервера потерян. Повторите запрос.');
    }
    return {'success': true};
  }

  @override
  Future<bool> updateOrderStatus(String leadId, String newStatus) async {
    statusCalls++;
    return true;
  }
}

void main() {
  late RatingUiApi api;

  setUp(() {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    api = RatingUiApi();
    app.gpmApi = api;
  });

  Future<void> open(WidgetTester tester, {bool staff = false, double scale = 1}) async {
    await tester.pumpWidget(MaterialApp(
      theme: buildGpmTheme(),
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)),
        child: child!,
      ),
      home: WorkerRatingScreen(
        workerId: staff ? 'worker-1' : null,
        workerName: staff ? 'Тестовый рабочий' : null,
      ),
    ));
    await tester.pumpAndSettle();
  }

  Future<void> tap(WidgetTester tester, Finder finder) async {
    if (finder.evaluate().isEmpty) {
      await tester.scrollUntilVisible(finder, 180, scrollable: find.byType(Scrollable).first);
    }
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  testWidgets('worker sees own reason and appeal retry preserves the request identity', (tester) async {
    api.failAppealOnce = true;
    await open(tester);
    expect(find.textContaining('Работы выполнены не полностью'), findsOneWidget);
    expect(find.text('Исправить оценку'), findsNothing);
    await tap(tester, find.text('Оспорить оценку'));
    await tester.tap(find.text('Отправить обращение'));
    await tester.pumpAndSettle();
    expect(api.appealRequests, isEmpty);
    await tester.enterText(find.byType(TextFormField), 'Прошу проверить выполненную работу');
    await tester.tap(find.text('Отправить обращение'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Связь потеряна'), findsOneWidget);
    expect(find.text('Прошу проверить выполненную работу'), findsOneWidget);
    await tester.tap(find.text('Отправить обращение'));
    await tester.pumpAndSettle();
    expect(api.appealRequests.length, 2);
    expect(api.appealRequests[0], api.appealRequests[1]);
    expect(api.review!['rating_delta'], -2);
    expect(find.text('Обращение рассматривается'), findsOneWidget);
    expect(find.text('Оспорить оценку'), findsNothing);
    expect(api.statusCalls, 0);
  });

  testWidgets('staff correction requires reason, shows difference and retries a lost reply once', (tester) async {
    api.failCorrectionAfterSaveOnce = true;
    await open(tester, staff: true);
    expect(find.text('Оспорить оценку'), findsNothing);
    await tap(tester, find.text('Исправить оценку'));
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Справился хорошо').last);
    await tester.pumpAndSettle();
    expect(find.textContaining('Изменение общих баллов: +4'), findsOneWidget);
    await tester.tap(find.text('Сохранить исправление'));
    await tester.pumpAndSettle();
    expect(api.correctionRequests, isEmpty);
    await tester.enterText(find.byType(TextFormField), 'Ошибка устранена после проверки фактов');
    await tester.tap(find.text('Сохранить исправление'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Ответ сервера потерян'), findsOneWidget);
    await tester.tap(find.text('Сохранить исправление'));
    await tester.pumpAndSettle();
    expect(api.appliedCorrections, 1);
    expect(api.correctionRequests[0], api.correctionRequests[1]);
    expect(api.review!['rating_delta'], 2);
    expect(api.review!['revision'], 2);
    expect(find.text('История изменений (2)'), findsOneWidget);
    expect(api.statusCalls, 0);
  });

  testWidgets('stale revision remains visible without silently overwriting the review', (tester) async {
    api.conflict = true;
    await open(tester, staff: true);
    await tap(tester, find.text('Исправить оценку'));
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Аннулировать оценку').last);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), 'Нужно проверить спорную оценку');
    await tester.tap(find.text('Сохранить исправление'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Оценка уже изменилась'), findsOneWidget);
    expect(api.review!['rating_delta'], -2);
    expect(api.appliedCorrections, 0);
    await tester.tap(find.text('Отмена'));
    await tester.pumpAndSettle();
  });

  testWidgets('history pagination appends rows and a foreign order has no management controls', (tester) async {
    api.allowManage = false;
    api.paged = true;
    await open(tester, staff: true);
    expect(find.text('Исправить оценку'), findsNothing);
    expect(find.text('Оспорить оценку'), findsNothing);
    await tap(tester, find.text('Показать еще'));
    expect(api.offsets, [0, 1]);
    expect(find.text('Вторая заявка'), findsOneWidget);
    expect(find.text('Синтетическая заявка'), findsOneWidget);
  });

  testWidgets('history and appeal form remain usable on 320 px with keyboard and 200 percent text', (tester) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetViewInsets);
    await open(tester, scale: 2);
    expect(tester.takeException(), isNull);
    await tap(tester, find.text('Оспорить оценку'));
    tester.view.viewInsets = const FakeViewPadding(bottom: 260);
    await tester.enterText(find.byType(TextFormField), 'Проверка доступности поля');
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Проверка доступности поля'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('client receives a general summary with honest legacy wording and no internal detail', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: buildGpmTheme(),
      home: const Scaffold(body: WorkerPublicRating(worker: {
        'rating': 17,
        'rating_summary': {'rating': 17, 'review_count': 0, 'has_legacy_balance': true},
      })),
    ));
    expect(find.textContaining('Рейтинг: 17'), findsOneWidget);
    expect(find.textContaining('Есть более ранний баланс'), findsOneWidget);
    expect(find.textContaining('Оценок пока нет'), findsNothing);
    expect(find.text('Оспорить оценку'), findsNothing);
    expect(find.text('Исправить оценку'), findsNothing);
  });
}

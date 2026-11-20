import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/registration_preview_main.dart';
import 'support/registration_preview_fake.dart';

Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> primary(WidgetTester tester) =>
    tapVisible(tester, find.byKey(const Key('registration_primary')));
Future<void> enter(WidgetTester tester, String field, String value) async {
  final target = find.byKey(Key('registration_$field'));
  await tester.ensureVisible(target);
  await tester.enterText(target, value);
  await tester.pump();
}

void main() {
  testWidgets('nine answers are restored from server and false remains No', (
    tester,
  ) async {
    final gateway = FakeRegistrationGateway(step: 'review');
    await tester.pumpWidget(RegistrationPreviewApp(gateway: gateway));
    await tester.pumpAndSettle();
    expect(find.text('Нет'), findsNWidgets(3));
    expect(find.text('Иванович'), findsOneWidget);
    expect(
      find.text('Москва, Центральный район (Санкт-Петербург)'),
      findsOneWidget,
    );
    expect(find.byTooltip('Изменить: Телефон'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(RegistrationPreviewApp(gateway: gateway));
    await tester.pumpAndSettle();
    expect(gateway.loads, 2);
    expect(find.text('Иванович'), findsOneWidget);
  });

  testWidgets(
    'phone, district-only, optional patronymic, boolean No and completion flow',
    (tester) async {
      final gateway = FakeRegistrationGateway();
      await tester.pumpWidget(RegistrationPreviewApp(gateway: gateway));
      await tester.pumpAndSettle();
      await enter(tester, 'phone', '+70000000001');
      await primary(tester);
      await enter(tester, 'code', '000000');
      await primary(tester);
      expect(find.textContaining('Неверный код'), findsWidgets);
      await enter(tester, 'code', '123456');
      await primary(tester);
      await tapVisible(tester, find.byKey(const Key('location_502')));
      await primary(tester);
      await enter(tester, 'first_name', 'Иван');
      await enter(tester, 'last_name', 'Иванов');
      await enter(tester, 'birth_date', '01011994');
      await primary(tester);
      for (final field in ['citizenship_ru', 'has_straps', 'has_tools']) {
        final target = find.descendant(
          of: find.byKey(Key('answer_$field')),
          matching: find.text('Нет'),
        );
        await tapVisible(tester, target);
      }
      await primary(tester);
      expect(find.text('Центральный район (Санкт-Петербург)'), findsOneWidget);
      expect(find.text('Не указано'), findsOneWidget);
      expect(find.text('Нет'), findsNWidgets(3));
      expect((gateway.state['answers'] as Map)['city_ids'], isEmpty);
      await primary(tester);
      expect(find.text('Анкета завершена'), findsOneWidget);
      expect(gateway.completions, 1);
      expect(find.byTooltip('Изменить: Телефон'), findsNothing);
      expect(find.textContaining('Рабочий аккаунт'), findsOneWidget);
    },
  );

  testWidgets(
    'review editing validates again, keeps rejected input and returns to review',
    (tester) async {
      final gateway = FakeRegistrationGateway(step: 'review');
      await tester.pumpWidget(RegistrationPreviewApp(gateway: gateway));
      await tester.pumpAndSettle();
      await tapVisible(tester, find.byTooltip('Изменить: Имя'));
      gateway.rejectedField = 'first_name';
      await enter(tester, 'first_name', '123');
      await primary(tester);
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const Key('registration_first_name')),
            )
            .controller!
            .text,
        '123',
      );
      expect(find.textContaining('Используй буквы'), findsWidgets);
      gateway.rejectedField = null;
      await enter(tester, 'first_name', 'Петр');
      await primary(tester);
      expect(find.text('Петр'), findsOneWidget);
      expect(find.text('Все верно?'), findsOneWidget);
    },
  );

  testWidgets(
    'example goes through server gateway but does not complete automatically',
    (tester) async {
      final gateway = FakeRegistrationGateway();
      await tester.pumpWidget(RegistrationPreviewApp(gateway: gateway));
      await tester.pumpAndSettle();
      await tapVisible(tester, find.text('Заполнить пример'));
      expect(find.text('Все верно?'), findsOneWidget);
      expect(gateway.state['phone_verified'], true);
      expect(gateway.completions, 0);
      await tapVisible(tester, find.text('Начать заново'));
      await tester.tap(find.text('Отмена'));
      await tester.pumpAndSettle();
      expect(find.text('Все верно?'), findsOneWidget);
    },
  );

  testWidgets(
    'phone form and action remain usable at 320px, 200% text and keyboard',
    (tester) async {
      tester.view.physicalSize = const Size(320, 568);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final gateway = FakeRegistrationGateway();
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await tester.pumpWidget(RegistrationPreviewApp(gateway: gateway));
      await tester.pumpAndSettle();
      tester.view.viewInsets = const FakeViewPadding(bottom: 240);
      addTearDown(tester.view.resetViewInsets);
      await tester.pumpAndSettle();
      await enter(tester, 'phone', '+70000000002');
      await primary(tester);
      expect(find.byKey(const Key('registration_code')), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}

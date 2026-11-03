import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/screens/auth/login_screen.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';

void main() {
  Widget buildSubject() {
    return MaterialApp(
      theme: buildGpmTheme(),
      home: GpmLoginScreen(onSignedIn: () {}),
    );
  }

  testWidgets('login starts without public test credentials', (tester) async {
    await tester.pumpWidget(buildSubject());

    expect(find.text('Выберите роль'), findsOneWidget);
    expect(find.textContaining('Закрытое тестирование'), findsOneWidget);
    expect(find.textContaining('admin/admin'), findsNothing);

    await tester.tap(find.text('Клиент'));
    await tester.pumpAndSettle();

    final usernameField = tester.widget<TextFormField>(
      find.byType(TextFormField).first,
    );
    expect(usernameField.controller?.text, isEmpty);
  });

  testWidgets('registration requires a one-time invitation', (tester) async {
    await tester.pumpWidget(buildSubject());
    final workerRole = find.text('Исполнитель');
    await tester.ensureVisible(workerRole);
    await tester.tap(workerRole);
    await tester.pumpAndSettle();
    final registrationTab = find.text('Регистрация');
    await tester.ensureVisible(registrationTab);
    await tester.tap(registrationTab);
    await tester.pumpAndSettle();

    expect(find.textContaining('Регистрация по приглашению'), findsOneWidget);
    expect(find.text('Код приглашения'), findsOneWidget);
    expect(find.text('Гражданство РФ'), findsOneWidget);
    final citizenship = tester.widget<SegmentedButton<bool>>(
      find.byType(SegmentedButton<bool>),
    );
    expect(citizenship.selected, isEmpty);
    final createAccount = find.text('Создать аккаунт');
    await tester.ensureVisible(createAccount);
    await tester.tap(createAccount);
    await tester.pumpAndSettle();
    expect(find.text('Укажите гражданство'), findsOneWidget);
    await tester.ensureVisible(find.text('Нет'));
    await tester.tap(find.text('Нет'));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<SegmentedButton<bool>>(find.byType(SegmentedButton<bool>))
          .selected,
      {false},
    );
    expect(find.textContaining('одноразовый код'), findsOneWidget);
    expect(find.textContaining('admin/admin'), findsNothing);
  });
}

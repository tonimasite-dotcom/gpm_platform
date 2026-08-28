import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/worker/worker_profile_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';

void main() {
  testWidgets('worker profile exposes editable data and moderation actions', (
    tester,
  ) async {
    dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
    app.gpmApi = GpmApiService();

    await tester.pumpWidget(
      MaterialApp(
        theme: buildGpmTheme(),
        home: const Scaffold(body: WorkerProfileScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Кабинет исполнителя'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, 'ФИО'), findsOneWidget);
    expect(find.text('Такелажные ремни'), findsOneWidget);
    expect(find.text('Свои инструменты'), findsOneWidget);
    expect(find.text('Отправить паспорт на проверку'), findsOneWidget);
    expect(find.text('Отправить заявку на подтверждение'), findsOneWidget);
    expect(find.text('Dev действия'), findsNothing);
  });
}

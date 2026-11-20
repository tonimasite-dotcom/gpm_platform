import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'registration/registration_preview_api.dart';
import 'registration/registration_preview_screen.dart';
import 'theme/gpm_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const RegistrationPreviewApp());
}

/// Separate entry point: never participates in the main app's login or routing.
class RegistrationPreviewApp extends StatelessWidget {
  final RegistrationPreviewGateway? gateway;
  const RegistrationPreviewApp({super.key, this.gateway});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Регистрация исполнителя · GPM',
    debugShowCheckedModeBanner: false,
    theme: buildGpmTheme(),
    locale: const Locale('ru', 'RU'),
    supportedLocales: const [Locale('ru', 'RU')],
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    home: RegistrationPreviewScreen(gateway: gateway ?? RegistrationPreviewApi()),
  );
}

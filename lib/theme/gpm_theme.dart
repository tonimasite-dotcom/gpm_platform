import 'package:flutter/material.dart';

class GpmColors {
  // Darkened from the original accent so white text meets WCAG AA contrast.
  static const red = Color(0xFFD20A3C);
  static const yellow = Color(0xFFF8B800);
  static const black = Color(0xFF111111);
  static const graphite = Color(0xFF343434);
  static const line = Color(0xFFE1E1E1);
  static const surface = Color(0xFFFFFFFF);
  static const page = Color(0xFFF5F5F5);
}

ThemeData buildGpmTheme() {
  final colorScheme = ColorScheme.fromSeed(
    seedColor: GpmColors.red,
    primary: GpmColors.red,
    secondary: GpmColors.yellow,
    surface: GpmColors.surface,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: GpmColors.page,
    fontFamily: 'Arial',
    textTheme: const TextTheme(
      headlineSmall: TextStyle(
        color: GpmColors.black,
        fontSize: 24,
        fontWeight: FontWeight.w800,
      ),
      titleLarge: TextStyle(
        color: GpmColors.black,
        fontSize: 20,
        fontWeight: FontWeight.w800,
      ),
      titleMedium: TextStyle(
        color: GpmColors.black,
        fontSize: 16,
        fontWeight: FontWeight.w700,
      ),
      bodyMedium: TextStyle(color: GpmColors.graphite, fontSize: 14),
    ),
    appBarTheme: const AppBarTheme(
      elevation: 0,
      scrolledUnderElevation: 0,
      backgroundColor: GpmColors.surface,
      foregroundColor: GpmColors.black,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: GpmColors.black,
        fontSize: 20,
        fontWeight: FontWeight.w800,
      ),
    ),
    cardTheme: CardThemeData(
      color: GpmColors.surface,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: GpmColors.line),
      ),
    ),
    dividerTheme: const DividerThemeData(color: GpmColors.line, thickness: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: GpmColors.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: GpmColors.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: GpmColors.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: GpmColors.red, width: 1.4),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        elevation: 0,
        backgroundColor: GpmColors.yellow,
        foregroundColor: GpmColors.black,
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: GpmColors.red,
        foregroundColor: Colors.white,
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: GpmColors.red,
        side: const BorderSide(color: GpmColors.red),
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: GpmColors.red,
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        backgroundColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? GpmColors.red
              : GpmColors.surface,
        ),
        foregroundColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? Colors.white
              : GpmColors.black,
        ),
        side: const WidgetStatePropertyAll(BorderSide(color: GpmColors.line)),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: GpmColors.surface,
      selectedItemColor: GpmColors.red,
      unselectedItemColor: Color(0xFF777777),
      type: BottomNavigationBarType.fixed,
      elevation: 12,
      selectedLabelStyle: TextStyle(fontWeight: FontWeight.w800),
    ),
    tabBarTheme: const TabBarThemeData(
      labelColor: GpmColors.red,
      unselectedLabelColor: GpmColors.graphite,
      indicatorColor: GpmColors.red,
      labelStyle: TextStyle(fontWeight: FontWeight.w800),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    ),
  );
}

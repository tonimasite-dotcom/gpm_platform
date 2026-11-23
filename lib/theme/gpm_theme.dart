import 'package:flutter/material.dart';

class GpmColors {
  // Website tokens: design-system.css and corporate.css; font is bundled offline.
  static const brandRed = Color(0xFFEF4444);
  // Existing red labels also include errors and amounts: retain text contrast.
  static const red = Color(0xFFDC2626);
  static const redAction = Color(0xFFDC2626);
  static const business = Color(0xFF115E59);
  static const brandSoft = Color(0xFFFEF2F2);
  static const businessSoft = Color(0xFFECFDF5);
  static const redInk = Color(0xFFB91C1C);
  static const muted = Color(0xFF64748B);
  static const softLine = Color(0xFFE2E8F0);
  // Helmet fill sampled from the bundled GPM logo.
  static const helmetYellow = Color(0xFFFFCC00);
  static const yellow = helmetYellow;
  static const yellowSoft = Color(0xFFFFF3C2);
  static const yellowLine = Color(0xFFE8C75A);
  static const yellowInk = Color(0xFF705000);
  static const black = Color(0xFF020617);
  static const graphite = Color(0xFF1E293B);
  static const line = Color(0xFFCBD5E1);
  static const surface = Color(0xFFFFFFFF);
  static const page = Color(0xFFF5F6F8);
}

// Opt-in only: client role alone does not identify a legal entity.
enum GpmAudience { personal, business }

ThemeData buildGpmTheme({GpmAudience audience = GpmAudience.personal}) {
  final isBusiness = audience == GpmAudience.business;
  final brand = isBusiness ? GpmColors.business : GpmColors.brandRed;
  final action = isBusiness ? GpmColors.business : GpmColors.helmetYellow;
  final actionInk = isBusiness ? Colors.white : GpmColors.black;
  final ink = isBusiness ? GpmColors.business : GpmColors.graphite;
  final focus = isBusiness ? GpmColors.business : GpmColors.yellowInk;
  final soft = isBusiness ? GpmColors.businessSoft : GpmColors.yellowSoft;
  final colorScheme = ColorScheme.fromSeed(
    seedColor: brand,
    primary: brand,
    secondary: action,
    onSecondary: actionInk,
    secondaryContainer: soft,
    onSecondaryContainer: ink,
    error: GpmColors.red,
    surface: GpmColors.surface,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: GpmColors.page,
    fontFamily: 'Manrope',
    textTheme: const TextTheme(
      headlineSmall: TextStyle(
        color: GpmColors.black,
        fontSize: 24,
        fontWeight: FontWeight.w600,
      ),
      titleLarge: TextStyle(
        color: GpmColors.black,
        fontSize: 20,
        fontWeight: FontWeight.w600,
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
        fontFamily: 'Manrope',
        color: GpmColors.black,
        fontSize: 20,
        fontWeight: FontWeight.w600,
      ),
    ),
    cardTheme: CardThemeData(
      color: GpmColors.surface,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: GpmColors.line),
      ),
    ),
    dividerTheme: const DividerThemeData(color: GpmColors.line, thickness: 1),
    inputDecorationTheme: InputDecorationTheme(
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
      labelStyle: const TextStyle(color: GpmColors.muted),
      floatingLabelStyle: TextStyle(color: focus),
      prefixIconColor: GpmColors.muted,
      suffixIconColor: GpmColors.muted,
      filled: true,
      fillColor: GpmColors.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: GpmColors.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: GpmColors.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: focus, width: 1.8),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        elevation: 0,
        backgroundColor: action,
        foregroundColor: actionInk,
        minimumSize: const Size(48, 56),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        textStyle: const TextStyle(
          fontFamily: 'Manrope',
          fontSize: 15,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: action,
        foregroundColor: actionInk,
        minimumSize: const Size(48, 56),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        textStyle: const TextStyle(
          fontFamily: 'Manrope',
          fontSize: 15,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: ink,
        side: const BorderSide(color: GpmColors.line),
        minimumSize: const Size(48, 56),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        textStyle: const TextStyle(
          fontFamily: 'Manrope',
          fontSize: 15,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: ink,
        minimumSize: const Size(48, 48),
        textStyle: const TextStyle(
          fontFamily: 'Manrope',
          fontSize: 15,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(48, 48)),
        textStyle: const WidgetStatePropertyAll(
          TextStyle(
            fontFamily: 'Manrope',
            fontSize: 15,
            fontWeight: FontWeight.w700,
          ),
        ),
        backgroundColor: WidgetStateProperty.resolveWith(
          (states) =>
              states.contains(WidgetState.selected) ? soft : GpmColors.surface,
        ),
        foregroundColor: WidgetStateProperty.resolveWith(
          (states) =>
              states.contains(WidgetState.selected) ? ink : GpmColors.black,
        ),
        side: const WidgetStatePropertyAll(BorderSide(color: GpmColors.line)),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
      ),
    ),
    chipTheme: ChipThemeData(
      selectedColor: action,
      secondarySelectedColor: action,
      labelStyle: const TextStyle(color: GpmColors.graphite, fontSize: 14),
      secondaryLabelStyle: TextStyle(
        color: actionInk,
        fontSize: 14,
        fontWeight: FontWeight.w700,
      ),
      checkmarkColor: actionInk,
      side: const BorderSide(color: GpmColors.softLine),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    bottomNavigationBarTheme: BottomNavigationBarThemeData(
      backgroundColor: GpmColors.surface,
      selectedItemColor: ink,
      unselectedItemColor: GpmColors.muted,
      type: BottomNavigationBarType.fixed,
      elevation: 0,
      selectedLabelStyle: const TextStyle(fontWeight: FontWeight.w800),
    ),
    tabBarTheme: TabBarThemeData(
      labelColor: ink,
      unselectedLabelColor: GpmColors.graphite,
      indicatorColor: action,
      indicatorSize: TabBarIndicatorSize.label,
      labelStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: GpmColors.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: GpmColors.surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
    ),
  );
}

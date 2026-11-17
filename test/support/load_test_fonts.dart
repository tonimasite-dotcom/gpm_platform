import 'dart:io';

import 'package:flutter/services.dart';

/// Use real mobile font metrics instead of the square Ahem test font.
Future<void> loadMobileTestFonts() async {
  final loader = FontLoader('Manrope');
  for (final name in [
    'Manrope-Regular.ttf',
    'Manrope-Medium.ttf',
    'Manrope-SemiBold.ttf',
    'Manrope-Bold.ttf',
    'Manrope-ExtraBold.ttf',
  ]) {
    loader.addFont(
      File(
        'assets/fonts/$name',
      ).readAsBytes().then((bytes) => ByteData.sublistView(bytes)),
    );
  }
  await loader.load();
}

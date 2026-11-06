import 'dart:io';

import 'package:flutter/services.dart';

/// Use real mobile font metrics instead of the square Ahem test font.
Future<void> loadMobileTestFonts() async {
  final loader = FontLoader('Arial');
  for (final name in [
    'Roboto-Regular.ttf',
    'Roboto-Bold.ttf',
    'Roboto-Black.ttf',
  ]) {
    loader.addFont(
      File(
        'test/fonts/$name',
      ).readAsBytes().then((bytes) => ByteData.sublistView(bytes)),
    );
  }
  await loader.load();
}

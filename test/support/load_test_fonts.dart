import 'dart:io';

import 'package:flutter/services.dart';

/// Use real mobile font metrics instead of the square Ahem test font.
Future<void> loadMobileTestFonts() async {
  var directory = File(Platform.resolvedExecutable).parent;
  while (true) {
    final fonts = Directory(
      '${directory.path}/bin/cache/artifacts/material_fonts',
    );
    if (fonts.existsSync()) {
      final loader = FontLoader('Arial');
      for (final name in [
        'roboto-regular.ttf',
        'roboto-bold.ttf',
        'roboto-black.ttf',
      ]) {
        loader.addFont(
          File(
            '${fonts.path}/$name',
          ).readAsBytes().then((bytes) => ByteData.sublistView(bytes)),
        );
      }
      await loader.load();
      return;
    }
    final parent = directory.parent;
    if (parent.path == directory.path) {
      throw StateError('Flutter material fonts not found');
    }
    directory = parent;
  }
}

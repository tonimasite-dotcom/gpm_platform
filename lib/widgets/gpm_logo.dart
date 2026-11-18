import 'package:flutter/material.dart';

/// Use the owner-provided artwork and proportions on every entry point.
class GpmLogoImage extends StatelessWidget {
  final double? width;
  final double? height;

  const GpmLogoImage({super.key, this.width, this.height});

  @override
  Widget build(BuildContext context) => Image.asset(
    'assets/images/gpm_logo.png',
    width: width,
    height: height ?? (width == null ? null : width! * 241 / 600),
    fit: BoxFit.contain,
    // Mipmaps retain smooth edges when the large source is reduced to an icon.
    filterQuality: FilterQuality.medium,
    isAntiAlias: true,
  );
}

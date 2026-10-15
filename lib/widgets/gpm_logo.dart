import 'package:flutter/material.dart';

/// Use the same restored artwork and downsampling on every entry point.
class GpmLogoImage extends StatelessWidget {
  final double? width;
  final double? height;

  const GpmLogoImage({super.key, this.width, this.height});

  @override
  Widget build(BuildContext context) => Image.asset(
    'assets/images/gpm_logo_refined.png',
    width: width,
    height: height,
    fit: BoxFit.contain,
    filterQuality: FilterQuality.high,
    isAntiAlias: true,
  );
}

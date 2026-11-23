import 'package:flutter/material.dart';

import '../theme/gpm_theme.dart';

/// Full-width mobile navigation and an inset, rounded desktop surface.
class GpmBottomNavigationBar extends StatelessWidget {
  const GpmBottomNavigationBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
    required this.items,
    this.type = BottomNavigationBarType.fixed,
    this.selectedFontSize = 14,
    this.unselectedFontSize = 12,
  });

  final int currentIndex;
  final ValueChanged<int> onTap;
  final List<BottomNavigationBarItem> items;
  final BottomNavigationBarType type;
  final double selectedFontSize;
  final double unselectedFontSize;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final navigation = BottomNavigationBar(
          currentIndex: currentIndex,
          onTap: onTap,
          items: items,
          type: type,
          selectedFontSize: selectedFontSize,
          unselectedFontSize: unselectedFontSize,
        );
        if (constraints.maxWidth < 720) return navigation;

        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          child: Material(
            color: GpmColors.surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
              side: const BorderSide(color: GpmColors.softLine),
            ),
            clipBehavior: Clip.antiAlias,
            child: navigation,
          ),
        );
      },
    );
  }
}

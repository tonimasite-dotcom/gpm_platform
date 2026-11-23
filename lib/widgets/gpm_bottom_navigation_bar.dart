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
    this.unselectedFontSize = 14,
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
        final scheme = Theme.of(context).colorScheme;
        final business = scheme.primary == GpmColors.business;
        final navigation = BottomNavigationBar(
          currentIndex: currentIndex,
          onTap: onTap,
          items: [for (final item in items) BottomNavigationBarItem(
            icon: item.icon,
            activeIcon: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
              decoration: BoxDecoration(
                color: business ? GpmColors.businessSoft : GpmColors.helmetYellow,
                borderRadius: BorderRadius.circular(14),
              ),
              child: item.activeIcon,
            ),
            label: item.label, tooltip: item.tooltip, backgroundColor: item.backgroundColor,
          )],
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

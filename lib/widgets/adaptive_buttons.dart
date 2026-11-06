import 'package:flutter/material.dart';

/// At large text sizes move the label below its icon instead of squeezing it.
class GpmButtonContent extends StatelessWidget {
  final Widget icon;
  final Widget label;

  const GpmButtonContent({super.key, required this.icon, required this.label});

  @override
  Widget build(BuildContext context) => Wrap(
    alignment: WrapAlignment.center,
    crossAxisAlignment: WrapCrossAlignment.center,
    spacing: 8,
    runSpacing: 4,
    children: [icon, label],
  );
}

/// Keep readable button labels by moving whole actions onto separate rows.
class GpmActionButtons extends StatelessWidget {
  final List<Widget> children;
  final double minButtonWidth;
  final double spacing;

  const GpmActionButtons({
    super.key,
    required this.children,
    this.minButtonWidth = 180,
    this.spacing = 8,
  });

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final scale = MediaQuery.textScalerOf(context).scale(15) / 15;
      final needed =
          children.length * minButtonWidth * scale +
          (children.length - 1) * spacing;
      final stacked = constraints.maxWidth < needed;
      final items = <Widget>[
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0)
            SizedBox(
              width: stacked ? 0 : spacing,
              height: stacked ? spacing : 0,
            ),
          if (stacked)
            SizedBox(width: double.infinity, child: children[i])
          else
            Expanded(child: children[i]),
        ],
      ];
      return stacked
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: items,
            )
          : Row(children: items);
    },
  );
}

/// Preserve native selection/accessibility while adapting to label width.
class GpmSegmentedButton<T> extends StatelessWidget {
  final List<ButtonSegment<T>> segments;
  final Set<T> selected;
  final ValueChanged<Set<T>>? onSelectionChanged;
  final bool emptySelectionAllowed;
  final bool showSelectedIcon;
  final ButtonStyle? style;

  const GpmSegmentedButton({
    super.key,
    required this.segments,
    required this.selected,
    this.onSelectionChanged,
    this.emptySelectionAllowed = false,
    this.showSelectedIcon = true,
    this.style,
  });

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final themeStyle = Theme.of(context).segmentedButtonTheme.style;
      final textStyle = Theme.of(context).textTheme.labelLarge!
          .merge(themeStyle?.textStyle?.resolve({}))
          .merge(style?.textStyle?.resolve({}));
      var segmentWidth = 48.0;
      for (final segment in segments) {
        final label = segment.label;
        final painter = TextPainter(
          text: label is Text
              ? TextSpan(text: label.data, style: textStyle.merge(label.style))
              : TextSpan(text: 'MMMMMMMMMMMM', style: textStyle),
          textDirection: Directionality.of(context),
          textScaler: MediaQuery.textScalerOf(context),
          locale: Localizations.maybeLocaleOf(context),
        )..layout();
        final width =
            painter.width +
            40 +
            (showSelectedIcon || segment.icon != null ? 32 : 0);
        if (width > segmentWidth) segmentWidth = width;
        painter.dispose();
      }
      final vertical = segmentWidth * segments.length > constraints.maxWidth;
      return SizedBox(
        width: constraints.hasBoundedWidth ? constraints.maxWidth : null,
        child: SegmentedButton<T>(
          segments: segments,
          selected: selected,
          onSelectionChanged: onSelectionChanged,
          emptySelectionAllowed: emptySelectionAllowed,
          showSelectedIcon: showSelectedIcon,
          style: style,
          expandedInsets: vertical ? null : EdgeInsets.zero,
          direction: vertical ? Axis.vertical : Axis.horizontal,
        ),
      );
    },
  );
}

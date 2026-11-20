import 'dart:math';

import 'package:flutter/material.dart';

import '../theme/gpm_theme.dart';

/// Full-height choices keep labels centered, including the selected checkmark.
class RegistrationAnswerChoices extends StatelessWidget {
  final String field;
  final bool? value;
  final ValueChanged<bool>? onChanged;

  const RegistrationAnswerChoices({
    super.key,
    required this.field,
    required this.value,
    this.onChanged,
  });

  static const _labelStyle = TextStyle(
    fontFamily: 'Manrope',
    fontSize: 15,
    fontWeight: FontWeight.w700,
  );

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      var width = 112.0;
      var height = 56.0;
      for (final label in ['Да', 'Нет']) {
        final painter = TextPainter(
          text: TextSpan(text: label, style: _labelStyle),
          textDirection: Directionality.of(context),
          textScaler: MediaQuery.textScalerOf(context),
        )..layout();
        width = max(width, painter.width + 80);
        height = max(height, painter.height + 32);
        painter.dispose();
      }
      Widget choice(bool answer) {
        final selected = value == answer;
        bool active(Set<WidgetState> states) => selected ||
            states.contains(WidgetState.hovered) ||
            states.contains(WidgetState.focused) ||
            states.contains(WidgetState.pressed);
        return SizedBox(
          width: double.infinity,
          height: height,
          child: Semantics(
            selected: selected,
            child: OutlinedButton(
              key: Key('choice_${field}_${answer ? 'yes' : 'no'}'),
              onPressed: onChanged == null ? null : () => onChanged!(answer),
              style: ButtonStyle(
                alignment: Alignment.center,
                padding: const WidgetStatePropertyAll(EdgeInsets.zero),
                minimumSize: const WidgetStatePropertyAll(Size.zero),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                visualDensity: VisualDensity.standard,
                textStyle: const WidgetStatePropertyAll(_labelStyle),
                backgroundColor: WidgetStateProperty.resolveWith((states) {
                  if (states.contains(WidgetState.disabled)) {
                    return selected ? GpmColors.softLine : GpmColors.surface;
                  }
                  return active(states) ? GpmColors.redAction : GpmColors.surface;
                }),
                foregroundColor: WidgetStateProperty.resolveWith((states) {
                  if (states.contains(WidgetState.disabled)) {
                    return GpmColors.muted;
                  }
                  return active(states) ? Colors.white : GpmColors.black;
                }),
                overlayColor: const WidgetStatePropertyAll(Colors.transparent),
                side: WidgetStateProperty.resolveWith((states) => BorderSide(
                  color: active(states) && !states.contains(WidgetState.disabled)
                      ? GpmColors.redAction
                      : GpmColors.line,
                )),
                shape: WidgetStatePropertyAll(RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                )),
              ),
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Center(child: Text(answer ? 'Да' : 'Нет')),
                  if (selected)
                    const Positioned.fill(
                      left: 12,
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Icon(Icons.check, size: 20),
                      ),
                    ),
                ],
              ),
            ),
          ),
        );
      }
      if (width * 2 + 12 > constraints.maxWidth) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [choice(true), const SizedBox(height: 12), choice(false)],
        );
      }
      return Row(
        children: [
          Expanded(child: choice(true)),
          const SizedBox(width: 12),
          Expanded(child: choice(false)),
        ],
      );
    },
  );
}

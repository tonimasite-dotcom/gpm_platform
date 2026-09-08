import 'package:flutter/services.dart';

/// Auto-inserts [separator] between digit groups as the user types, so
/// masked inputs like dates (ДД.ММ.ГГГГ) or times (ЧЧ:ММ) never require the
/// separator to be typed manually.
class DigitGroupInputFormatter extends TextInputFormatter {
  const DigitGroupInputFormatter(this.groupSizes, this.separator);

  final List<int> groupSizes;
  final String separator;

  int get _maxDigits => groupSizes.fold<int>(0, (sum, size) => sum + size);

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final oldDigits = _digitsOf(oldValue.text);
    var digits = _digitsOf(newValue.text);
    var digitsBeforeCursor = _digitsOf(
      newValue.text.substring(
        0,
        newValue.selection.end.clamp(0, newValue.text.length),
      ),
    ).length;

    // A backspace right after an auto-inserted separator removes only the
    // separator (it isn't a digit), so drop the preceding digit too -
    // otherwise the separator reappears immediately and backspace feels
    // broken.
    final isDeletion = newValue.text.length < oldValue.text.length;
    if (isDeletion && digits.length == oldDigits.length && digitsBeforeCursor > 0) {
      digits = digits.substring(0, digitsBeforeCursor - 1) +
          digits.substring(digitsBeforeCursor);
      digitsBeforeCursor -= 1;
    }

    if (digits.length > _maxDigits) digits = digits.substring(0, _maxDigits);
    if (digitsBeforeCursor > digits.length) digitsBeforeCursor = digits.length;

    return TextEditingValue(
      text: _format(digits),
      selection: TextSelection.collapsed(
        offset: _format(digits.substring(0, digitsBeforeCursor)).length,
      ),
    );
  }

  String _format(String digits) {
    final buffer = StringBuffer();
    var consumed = 0;
    for (var i = 0; i < groupSizes.length && consumed < digits.length; i++) {
      if (i > 0) buffer.write(separator);
      final end = (consumed + groupSizes[i]).clamp(0, digits.length);
      buffer.write(digits.substring(consumed, end));
      consumed = end;
    }
    return buffer.toString();
  }

  static String _digitsOf(String value) =>
      value.replaceAll(RegExp('[^0-9]'), '');
}

/// ДД.ММ.ГГГГ
final List<TextInputFormatter> dateAutoSeparatorFormatters = [
  const DigitGroupInputFormatter([2, 2, 4], '.'),
];

/// ЧЧ:ММ
final List<TextInputFormatter> timeAutoSeparatorFormatters = [
  const DigitGroupInputFormatter([2, 2], ':'),
];

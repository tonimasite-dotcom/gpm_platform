import 'package:flutter/services.dart';

/// Limit digits for typing, paste and autofill without counting separators.
class RegistrationPhoneFormatter extends TextInputFormatter {
  final String country;
  const RegistrationPhoneFormatter(this.country);

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final raw = newValue.text;
    final hasPlus = raw.trimLeft().startsWith('+');
    var digits = raw.replaceAll(RegExp(r'[^0-9]'), '');
    final limit = country == 'INT'
        ? 15
        : hasPlus || digits.startsWith('7') || digits.startsWith('8')
        ? 11
        : 10;
    if (digits.length > limit) {
      digits = digits.substring(0, limit);
    }
    final text = '${hasPlus ? '+' : ''}$digits';
    if (text == raw) {
      return newValue;
    }
    int offset(int value) {
      if (value < 0) {
        return text.length;
      }
      final before = raw.substring(0, value.clamp(0, raw.length).toInt());
      final count = before.replaceAll(RegExp(r'[^0-9]'), '').length;
      final plus = hasPlus && before.contains('+') ? 1 : 0;
      return (count.clamp(0, limit) + plus).clamp(0, text.length).toInt();
    }

    return TextEditingValue(
      text: text,
      selection: TextSelection(
        baseOffset: offset(newValue.selection.baseOffset),
        extentOffset: offset(newValue.selection.extentOffset),
      ),
    );
  }
}

String? registrationPhoneError(String value, String country) {
  if (value.isEmpty) {
    return 'Укажи номер телефона';
  }
  if (country == 'RU') {
    if (!RegExp(
      r'^(?:\+7[0-9]{10}|[78][0-9]{10}|[0-9]{10})$',
    ).hasMatch(value)) {
      return 'Нужно 10 цифр или 11 с кодом 7/8';
    }
  } else if (!RegExp(r'^\+[1-9][0-9]{7,14}$').hasMatch(value)) {
    return 'Укажи + и от 8 до 15 цифр, первая — не 0';
  }
  return null;
}

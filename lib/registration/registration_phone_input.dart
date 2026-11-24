import 'package:flutter/services.dart';

/// Canonical identity used for comparisons; formatting never changes identity.
String? normalizeRussianPhone(String value) {
  if (value.length > 64 ||
      !RegExp(r'^[+0-9()\s.-]+$').hasMatch(value) ||
      '+'.allMatches(value).length > 1 ||
      (value.contains('+') && !value.trimLeft().startsWith('+'))) {
    return null;
  }
  final compact = value.replaceAll(RegExp(r'[()\s.-]'), '');
  if (RegExp(r'^\+7[0-9]{10}$').hasMatch(compact)) return compact;
  if (RegExp(r'^[78][0-9]{10}$').hasMatch(compact)) {
    return '+7${compact.substring(1)}';
  }
  if (RegExp(r'^[0-9]{10}$').hasMatch(compact)) return '+7$compact';
  return null;
}

String _russianMask(String national) {
  if (national.isEmpty) return '+7';
  final buffer = StringBuffer('+7 (');
  for (var i = 0; i < national.length; i++) {
    if (i == 3) buffer.write(' ');
    if (i == 6 || i == 8) buffer.write('-');
    buffer.write(national[i]);
    if (i == 2) buffer.write(')');
  }
  return buffer.toString();
}

/// Do not truncate or hide invalid saved legacy data.
String phoneForDisplay(String value, [String country = 'RU']) {
  if (country != 'RU') return value;
  final normalized = normalizeRussianPhone(value);
  return normalized == null ? value : _russianMask(normalized.substring(2));
}

String? russianPhoneError(String? value, {bool required = true}) {
  if ((value ?? '').trim().isEmpty && !required) return null;
  return registrationPhoneError(value ?? '', 'RU');
}

/// Shared by registration, profiles, contact and SBP forms.
class RegistrationPhoneFormatter extends TextInputFormatter {
  final String country;
  const RegistrationPhoneFormatter(this.country);

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    if (newValue.composing.isValid && !newValue.composing.isCollapsed) {
      return newValue;
    }
    var raw = newValue.text;
    var selection = newValue.selection;
    if (raw.isEmpty) return TextEditingValue.empty;
    // Deleting a separator must not restore it forever.
    if (country == 'RU' &&
        oldValue.selection.isCollapsed &&
        selection.isCollapsed &&
        oldValue.text.length > raw.length &&
        oldValue.text.replaceAll(RegExp(r'[^0-9]'), '') ==
            raw.replaceAll(RegExp(r'[^0-9]'), '')) {
      final backward = selection.baseOffset < oldValue.selection.baseOffset;
      var index = selection.baseOffset.clamp(0, raw.length).toInt();
      if (backward) index--;
      while (index >= 2 &&
          index < raw.length &&
          !RegExp(r'[0-9]').hasMatch(raw[index])) {
        index += backward ? -1 : 1;
      }
      if (index >= 2 && index < raw.length) {
        raw = raw.replaceRange(index, index + 1, '');
        selection = TextSelection.collapsed(offset: index);
      }
    }

    final hasPlus = raw.trimLeft().startsWith('+');
    var digits = raw.replaceAll(RegExp(r'[^0-9]'), '');
    if (digits.isEmpty) {
      return hasPlus
          ? const TextEditingValue(
              text: '+',
              selection: TextSelection.collapsed(offset: 1),
            )
          : TextEditingValue.empty;
    }
    if (country == 'INT') {
      if (digits.length > 15) digits = digits.substring(0, 15);
      final text = '${hasPlus ? '+' : ''}$digits';
      return _withSelection(raw, selection, text, 0);
    }
    // Keep foreign codes invalid rather than silently relabeling them as +7.
    if (hasPlus && !digits.startsWith('7')) {
      if (digits.length > 11) digits = digits.substring(0, 11);
      return _withSelection(raw, selection, '+$digits', 0);
    }
    final sourcePrefix =
        hasPlus ||
        ((digits.startsWith('7') || digits.startsWith('8')) &&
            digits.length != 10);
    if (sourcePrefix) digits = digits.substring(1);
    if (digits.length > 10) digits = digits.substring(0, 10);
    final text = _russianMask(digits);
    return _withSelection(raw, selection, text, sourcePrefix ? 0 : 1);
  }

  TextEditingValue _withSelection(
    String raw,
    TextSelection selection,
    String text,
    int addedDigits,
  ) {
    if (text == raw) return TextEditingValue(text: text, selection: selection);
    int offset(int position) {
      if (position < 0 || position >= raw.length) return text.length;
      final count =
          raw.substring(0, position).replaceAll(RegExp(r'[^0-9]'), '').length +
          addedDigits;
      if (count <= 0) return 0;
      var seen = 0;
      for (var i = 0; i < text.length; i++) {
        if (RegExp(r'[0-9]').hasMatch(text[i]) && ++seen == count) {
          var end = i + 1;
          if (end < text.length && text[end] == ')') end++;
          return end;
        }
      }
      return text.length;
    }

    return TextEditingValue(
      text: text,
      selection: TextSelection(
        baseOffset: offset(selection.baseOffset),
        extentOffset: offset(selection.extentOffset),
      ),
    );
  }
}

String? registrationPhoneError(String value, String country) {
  if (value.isEmpty) return 'Укажи номер телефона';
  if (country == 'RU') {
    if (normalizeRussianPhone(value) == null) {
      return 'Нужно 10 цифр или 11 с кодом 7/8';
    }
  } else {
    final compact = value.replaceAll(RegExp(r'[()\s.-]'), '');
    if (!RegExp(r'^\+[1-9][0-9]{7,14}$').hasMatch(compact)) {
      return 'Укажи + и от 8 до 15 цифр, первая — не 0';
    }
  }
  return null;
}

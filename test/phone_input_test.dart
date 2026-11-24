import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/registration/registration_phone_input.dart';

TextEditingValue edit(String value, [int? offset]) => TextEditingValue(
  text: value,
  selection: TextSelection.collapsed(offset: offset ?? value.length),
);

void main() {
  const formatter = RegistrationPhoneFormatter('RU');
  const display = '+7 (999) 999-99-77';
  test('CRM variants share identity and presentation without truncation', () {
    for (final raw in [
      '89999999977', '79999999977', '+79999999977',
      '+7 999 999 99 77', '(999) 999-99-77', '8 (999) 999-99-77',
      '8.999.999.99.77', '9999999977',
    ]) {
      expect(normalizeRussianPhone(raw), '+79999999977', reason: raw);
      expect(phoneForDisplay(raw), display, reason: raw);
      expect(registrationPhoneError(raw, 'RU'), isNull, reason: raw);
      expect(formatter.formatEditUpdate(TextEditingValue.empty, edit(raw)).text,
          display, reason: raw);
    }
    for (final invalid in [
      '999', '+799999999770', '179999999977', '+49999999977',
      '++79999999977', '7+9999999977', 'abc9999999977',
    ]) {
      expect(normalizeRussianPhone(invalid), isNull, reason: invalid);
      expect(phoneForDisplay(invalid), invalid, reason: invalid);
      expect(registrationPhoneError(invalid, 'RU'), isNotNull);
    }
  });
  test('typing 7 or 8 immediately gives +7 and completes the mask', () {
    for (final leading in ['7', '8']) {
      var value = formatter.formatEditUpdate(TextEditingValue.empty, edit(leading));
      expect(value.text, '+7');
      for (final digit in '9999999977'.split('')) {
        value = formatter.formatEditUpdate(value, edit(value.text + digit));
      }
      expect(value.text, display);
      expect(value.selection.baseOffset, display.length);
      expect(formatter.formatEditUpdate(value, edit(value.text + '123')).text,
          display);
    }
    expect(formatter.formatEditUpdate(TextEditingValue.empty, edit('999')).text,
        '+7 (999)');
  });
  test('caret, selection, separator deletion and clearing remain editable', () {
    final value = edit(display);
    final same = formatter.formatEditUpdate(value, edit(display, 8));
    expect(same.selection.baseOffset, 8);
    final replaced = formatter.formatEditUpdate(
      edit(display, 6), edit('+7 (919) 999-99-77', 6));
    expect(replaced.text, '+7 (919) 999-99-77');
    expect(replaced.selection.baseOffset, 6);
    final separator = formatter.formatEditUpdate(
      edit(display, 13), edit('+7 (999) 99999-77', 12));
    expect(separator.text, '+7 (999) 999-97-7');
    expect(separator.selection.isCollapsed, true);
    expect(formatter.formatEditUpdate(value, TextEditingValue.empty).text, '');
  });
  test('international option keeps its own code and length', () {
    const intl = RegistrationPhoneFormatter('INT');
    expect(intl.formatEditUpdate(TextEditingValue.empty,
        edit('+491234567890123456')).text, '+491234567890123');
    expect(registrationPhoneError('+49 (123) 456789', 'INT'), isNull);
    expect(registrationPhoneError('+01234567', 'INT'), isNotNull);
    expect(russianPhoneError('', required: false), isNull);
    expect(russianPhoneError('999', required: false), isNotNull);
  });
}

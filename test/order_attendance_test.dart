import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/screens/attendance/order_attendance.dart';
import 'package:qr_flutter/qr_flutter.dart';

void main() {
  group('attendanceTokenFromQr', () {
    test('extracts a token from the public confirmation URL', () {
      expect(
        attendanceTokenFromQr(
          'https://app-api.gpmbot.ru/attendance/confirm/token-123',
        ),
        'token-123',
      );
    });

    test('accepts the native payload and rejects unrelated QR values', () {
      expect(attendanceTokenFromQr('gpm-attendance:token-456'), 'token-456');
      expect(
        attendanceTokenFromQr('https://example.test/not-attendance'),
        isNull,
      );
      expect(attendanceTokenFromQr(''), isNull);
    });
  });

  testWidgets('guest challenge shows QR, one-minute timer, and code field', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AttendanceChallengeScreen(
          orderId: 'L1-011026-1',
          challenge: {
            'action': 'check_in',
            'verifier_mode': 'guest_code',
            'confirmation_url':
                'https://app-api.gpmbot.ru/attendance/confirm/token-123',
            'request_code': 'ABCD2345',
            'expires_at': DateTime.now()
                .add(const Duration(minutes: 1))
                .toUtc()
                .toIso8601String(),
          },
        ),
      ),
    );

    expect(find.byType(QrImageView), findsOneWidget);
    expect(find.text('Резервный код запроса'), findsOneWidget);
    expect(find.text('ABCD2345'), findsOneWidget);
    expect(find.text('Код от заказчика'), findsOneWidget);
    expect(find.textContaining('сек.'), findsOneWidget);
  });
}

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:gpm_platform/main.dart' as app;
import 'package:gpm_platform/screens/logist/logist_orders_screen.dart';
import 'package:gpm_platform/services/gpm_api_service.dart';
import 'package:gpm_platform/theme/gpm_theme.dart';
import 'package:gpm_platform/widgets/adaptive_buttons.dart';
import 'support/load_test_fonts.dart';

Widget _host(Widget child, double scale, {double padding = 32}) => MaterialApp(
  theme: buildGpmTheme(),
  builder: (context, child) => MediaQuery(
    data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)),
    child: child!,
  ),
  home: Scaffold(
    body: Padding(padding: EdgeInsets.all(padding), child: child),
  ),
);

void _expectWholeWords(WidgetTester tester, String label) {
  final paragraph = tester.renderObject<RenderParagraph>(find.text(label));
  var offset = 0;
  for (final word in label.split(' ')) {
    final boxes = paragraph.getBoxesForSelection(
      TextSelection(baseOffset: offset, extentOffset: offset + word.length),
    );
    expect(boxes.map((box) => box.top).toSet(), hasLength(1), reason: word);
    for (final box in boxes) {
      expect(box.left, greaterThanOrEqualTo(-0.1));
      expect(box.right, lessThanOrEqualTo(paragraph.size.width + 0.1));
    }
    offset += word.length + 1;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(loadMobileTestFonts);
  for (final scale in [1.0, 1.3, 2.0]) {
    testWidgets('actual moderation card at 320 px, scale=$scale', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(320, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      dotenv.testLoad(fileInput: 'GPM_APP_MODE=demo\n');
      app.gpmApi = GpmApiService();
      await tester.pumpWidget(
        _host(
          SingleChildScrollView(
            child: LogistOrderCard(
              order: {
                'id': 'mobile-draft',
                'title': 'Заявка',
                'status': 'NEW',
                'source': 'manual',
                'city': 'Москва',
                'workers_count': 2,
                'hours': 4,
                'price_per_hour': 450,
              },
              onUpdate: () {},
            ),
          ),
          scale,
          padding: 8,
        ),
      );
      await tester.pumpAndSettle();
      for (final label in ['Редактировать', 'Отклонить', 'Опубликовать']) {
        await tester.ensureVisible(find.text(label));
        await tester.pumpAndSettle();
        _expectWholeWords(tester, label);
      }
      expect(tester.takeException(), isNull);
    });
  }
  for (final width in [320.0, 360.0, 390.0, 430.0, 600.0, 1024.0]) {
    for (final scale in [1.0, 1.3, 2.0]) {
      testWidgets('actions fit width=$width text scale=$scale', (tester) async {
        tester.view.physicalSize = Size(width, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        await tester.pumpWidget(
          _host(
            GpmActionButtons(
              children: [
                OutlinedButton(
                  onPressed: () {},
                  child: const Text('Отклонить'),
                ),
                ElevatedButton(
                  onPressed: () {},
                  child: const Text('Опубликовать'),
                ),
              ],
            ),
            scale,
          ),
        );
        await tester.pumpAndSettle();
        for (final label in ['Отклонить', 'Опубликовать']) {
          _expectWholeWords(tester, label);
          final button = find
              .ancestor(
                of: find.text(label),
                matching: find.byWidgetPredicate((w) => w is ButtonStyleButton),
              )
              .first;
          final rect = tester.getRect(button);
          expect(rect.left, greaterThanOrEqualTo(32));
          expect(rect.right, lessThanOrEqualTo(width - 32));
          expect(rect.height, greaterThanOrEqualTo(48));
          final paragraph = tester.renderObject<RenderParagraph>(
            find.text(label),
          );
          expect((paragraph.text as TextSpan).style!.fontSize, 15);
        }
        final first = tester.getRect(find.byType(OutlinedButton));
        final second = tester.getRect(find.byType(ElevatedButton));
        expect(first.overlaps(second), isFalse);
        if (width <= 430) expect(second.top, greaterThan(first.bottom));
        if (width == 1024) expect(second.top, first.top);
        expect(tester.takeException(), isNull);
      });

      testWidgets('choices fit width=$width text scale=$scale', (tester) async {
        tester.view.physicalSize = Size(width, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        var selected = <String>{};
        await tester.pumpWidget(
          _host(
            StatefulBuilder(
              builder: (context, setState) => GpmSegmentedButton<String>(
                segments: const [
                  ButtonSegment(
                    value: 'person',
                    label: Text('Физическое лицо'),
                  ),
                  ButtonSegment(
                    value: 'company',
                    label: Text('Юридическое лицо'),
                  ),
                ],
                selected: selected,
                emptySelectionAllowed: true,
                onSelectionChanged: (value) => setState(() => selected = value),
              ),
            ),
            scale,
          ),
        );
        await tester.pumpAndSettle();
        _expectWholeWords(tester, 'Физическое лицо');
        _expectWholeWords(tester, 'Юридическое лицо');
        await tester.tap(find.text('Юридическое лицо'));
        await tester.pumpAndSettle();
        expect(selected, {'company'});
        _expectWholeWords(tester, 'Юридическое лицо');
        expect(tester.takeException(), isNull);
      });
    }
  }
}

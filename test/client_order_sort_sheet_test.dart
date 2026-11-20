import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpm_platform/screens/orders/client_order_sort_sheet.dart';
import 'package:gpm_platform/utils/client_order_sort.dart';

void main() {
  testWidgets('multiple criteria can be prioritized and cancelled', (tester) async {
    List<ClientOrderSort>? result;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (context) => TextButton(
      onPressed: () async { result = await showClientOrderSortSheet(context, [ClientOrderSort.dateDesc]); },
      child: const Text('Open'),
    )))));
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('По статусу'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Выше: По статусу'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Применить'));
    await tester.pumpAndSettle();
    expect(result, [ClientOrderSort.status, ClientOrderSort.dateDesc]);
    result = null;
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('По статусу'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Отмена'));
    await tester.pumpAndSettle();
    expect(result, isNull);
  });

  testWidgets('date directions exclude each other, reset restores default on narrow screen', (tester) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    List<ClientOrderSort>? result;
    await tester.pumpWidget(MaterialApp(builder: (context, child) => MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(2)), child: child!),
      home: Scaffold(body: Builder(builder: (context) => TextButton(
        onPressed: () async { result = await showClientOrderSortSheet(context, [ClientOrderSort.dateDesc]); },
        child: const Text('Open'),
      )))));
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    final asc = find.text('По дате: сначала старые');
    await tester.ensureVisible(asc);
    await tester.tap(asc);
    await tester.pumpAndSettle();
    final checked = tester.widgetList<CheckboxListTile>(find.byType(CheckboxListTile)).where((tile) => tile.value == true);
    expect(checked, hasLength(1));
    await tester.tap(find.text('Сбросить'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Применить'));
    await tester.pumpAndSettle();
    expect(result, [ClientOrderSort.dateDesc]);
    expect(tester.takeException(), isNull);
  });
}

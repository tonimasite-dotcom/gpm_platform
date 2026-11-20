import 'package:flutter/material.dart';
import '../../utils/client_order_sort.dart';

Future<List<ClientOrderSort>?> showClientOrderSortSheet(
  BuildContext context,
  List<ClientOrderSort> current,
) {
  var selected = [...current];
  return showModalBottomSheet<List<ClientOrderSort>>(
    context: context,
    isScrollControlled: true,
    builder: (sheetContext) => StatefulBuilder(
      builder: (context, update) => SafeArea(
        child: SizedBox(
          height: MediaQuery.sizeOf(context).height * 0.8,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: SingleChildScrollView(
              child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Сортировка заказов', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                const Text('Выберите несколько критериев. Верхний применяется первым, остальные — при совпадении значений.'),
                const SizedBox(height: 8),
                Column(
                      children: [
                        for (final field in [
                          ...selected,
                          ...ClientOrderSort.values.where((item) => !selected.contains(item)),
                        ]) ...[
                          CheckboxListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text(field.label),
                            subtitle: selected.contains(field)
                                ? Text('Приоритет: ${selected.indexOf(field) + 1}')
                                : null,
                            value: selected.contains(field),
                            onChanged: (value) => update(() {
                              if (value != true) {
                                selected.remove(field);
                              } else {
                                if (field.isDate) {
                                  selected.removeWhere((item) => item.isDate);
                                }
                                selected.add(field);
                              }
                            }),
                          ),
                          if (selected.contains(field))
                            Align(
                              alignment: Alignment.centerRight,
                              child: Wrap(
                                children: [
                                  IconButton(
                                    tooltip: 'Выше: ${field.label}',
                                    onPressed: selected.indexOf(field) > 0
                                        ? () => update(() {
                                            final index = selected.indexOf(field);
                                            selected.removeAt(index);
                                            selected.insert(index - 1, field);
                                          })
                                        : null,
                                    icon: const Icon(Icons.arrow_upward),
                                  ),
                                  IconButton(
                                    tooltip: 'Ниже: ${field.label}',
                                    onPressed: selected.indexOf(field) < selected.length - 1
                                        ? () => update(() {
                                            final index = selected.indexOf(field);
                                            selected.removeAt(index);
                                            selected.insert(index + 1, field);
                                          })
                                        : null,
                                    icon: const Icon(Icons.arrow_downward),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ],
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.end,
                  children: [
                    TextButton(
                      onPressed: () => update(() => selected = [ClientOrderSort.dateDesc]),
                      child: const Text('Сбросить'),
                    ),
                    TextButton(
                      onPressed: () => Navigator.pop(sheetContext),
                      child: const Text('Отмена'),
                    ),
                    FilledButton(
                      onPressed: selected.isEmpty
                          ? null
                          : () => Navigator.pop(sheetContext, [...selected]),
                      child: const Text('Применить'),
                    ),
                  ],
                ),
              ],
            ),
            ),
          ),
        ),
      ),
    ),
  );
}

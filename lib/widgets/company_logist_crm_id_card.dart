import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/gpm_theme.dart';

class CompanyLogistCrmIdCard extends StatelessWidget {
  final int? crmId;
  const CompanyLogistCrmIdCard({super.key, this.crmId});

  @override
  Widget build(BuildContext context) {
    if (crmId == null || crmId! <= 0) {
      return const SizedBox.shrink();
    }
    final label = '#$crmId';
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: GpmColors.surface,
          border: Border.all(color: GpmColors.line),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: SelectableText(
                      'Ваш ID для CRM: $label',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: GpmColors.redInk,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    tooltip: 'Скопировать ID для CRM',
                    icon: const Icon(Icons.copy_outlined),
                    onPressed: () async {
                      await Clipboard.setData(ClipboardData(text: label));
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('ID скопирован')),
                        );
                      }
                    },
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'Укажи этот ID в поле «ID в приложении» при отправке заявки из CRM.',
                style: TextStyle(color: GpmColors.muted),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

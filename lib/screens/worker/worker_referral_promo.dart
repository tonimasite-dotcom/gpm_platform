import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../theme/gpm_theme.dart';

const _dialogBreakpoint = 600.0;

Future<void> showWorkerReferralPromo(BuildContext context) async {
  Future<void> openTelegram(String username) async {
    final uri = Uri.https('t.me', username);
    var launched = false;
    try {
      launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      launched = false;
    }

    if (!launched && context.mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Не удалось открыть @$username')));
    }
  }

  if (MediaQuery.sizeOf(context).width >= _dialogBreakpoint) {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: SingleChildScrollView(
            child: _ReferralDetails(
              onClose: () => Navigator.of(dialogContext).pop(),
              onContact: openTelegram,
            ),
          ),
        ),
      ),
    );
    return;
  }

  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    useSafeArea: true,
    builder: (sheetContext) => ConstrainedBox(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.9,
      ),
      child: SingleChildScrollView(
        child: _ReferralDetails(
          onClose: () => Navigator.of(sheetContext).pop(),
          onContact: openTelegram,
        ),
      ),
    ),
  );
}

class WorkerReferralPromoCard extends StatelessWidget {
  final VoidCallback onTap;

  const WorkerReferralPromoCard({required this.onTap, super.key});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: Ink(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [GpmColors.surface, GpmColors.red.withValues(alpha: 0.055)],
          ),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: GpmColors.red.withValues(alpha: 0.28)),
        ),
        child: InkWell(
          key: const Key('worker_referral_promo_card'),
          onTap: onTap,
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        color: GpmColors.red.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.card_giftcard_rounded,
                        color: GpmColors.red,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Приведи друга — получи бонус',
                            style: TextStyle(
                              color: GpmColors.black,
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          SizedBox(height: 4),
                          Text(
                            'Чем больше смен отработает друг, тем больше бонус.',
                            style: TextStyle(
                              color: GpmColors.graphite,
                              fontSize: 13,
                              height: 1.3,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                const Row(
                  children: [
                    Expanded(
                      child: _RewardBadge(shifts: '5 смен', amount: '3 500 ₽'),
                    ),
                    SizedBox(width: 10),
                    Expanded(
                      child: _RewardBadge(shifts: '10 смен', amount: '5 000 ₽'),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: onTap,
                    icon: const Icon(Icons.person_add_alt_1_rounded, size: 19),
                    label: const Text('Подробнее и пригласить'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _RewardBadge extends StatelessWidget {
  final String shifts;
  final String amount;

  const _RewardBadge({required this.shifts, required this.amount});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: GpmColors.surface.withValues(alpha: 0.86),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            shifts,
            style: const TextStyle(
              color: GpmColors.graphite,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 2),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              amount,
              style: const TextStyle(
                color: GpmColors.black,
                fontSize: 20,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReferralDetails extends StatelessWidget {
  final VoidCallback onClose;
  final Future<void> Function(String username) onContact;

  const _ReferralDetails({required this.onClose, required this.onContact});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: GpmColors.red.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.card_giftcard_rounded,
                  color: GpmColors.red,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 3),
                  child: Text(
                    'Пригласить друга',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
              ),
              IconButton(
                tooltip: 'Закрыть',
                onPressed: onClose,
                icon: const Icon(Icons.close_rounded),
              ),
            ],
          ),
          const SizedBox(height: 14),
          const Text(
            'Можно привести друга на работу в GPM и получить бонус после того, '
            'как он отработает нужное количество смен.',
            style: TextStyle(color: GpmColors.graphite, height: 1.4),
          ),
          const SizedBox(height: 16),
          const _DetailRewardRow(shifts: '5 смен', amount: '3 500 ₽'),
          const SizedBox(height: 8),
          const _DetailRewardRow(shifts: '10 смен', amount: '5 000 ₽'),
          const SizedBox(height: 18),
          const Divider(height: 1),
          const SizedBox(height: 18),
          const Text(
            'Свяжитесь с одним из специалистов в Telegram:',
            style: TextStyle(
              color: GpmColors.black,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          _TelegramContactButton(
            name: 'Дарья',
            username: 'GPMHRDaria',
            onPressed: () => onContact('GPMHRDaria'),
          ),
          const SizedBox(height: 10),
          _TelegramContactButton(
            name: 'Екатерина',
            username: 'GpmHREkaterina',
            onPressed: () => onContact('GpmHREkaterina'),
          ),
        ],
      ),
    );
  }
}

class _DetailRewardRow extends StatelessWidget {
  final String shifts;
  final String amount;

  const _DetailRewardRow({required this.shifts, required this.amount});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: GpmColors.page,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GpmColors.line),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.calendar_today_outlined,
            color: GpmColors.red,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Друг отработал $shifts',
              style: const TextStyle(
                color: GpmColors.graphite,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            amount,
            style: const TextStyle(
              color: GpmColors.black,
              fontSize: 18,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _TelegramContactButton extends StatelessWidget {
  final String name;
  final String username;
  final VoidCallback onPressed;

  const _TelegramContactButton({
    required this.name,
    required this.username,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        icon: const Icon(Icons.send_rounded, size: 20),
        label: Align(
          alignment: Alignment.centerLeft,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Написать: $name'),
              Text(
                '@$username',
                style: const TextStyle(
                  color: GpmColors.graphite,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

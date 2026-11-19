import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../theme/gpm_theme.dart';

const _dialogBreakpoint = 600.0;
const _promoBackground = GpmColors.surface;
const _promoBorder = GpmColors.softLine;

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
        backgroundColor: _promoBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
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
    backgroundColor: _promoBackground,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
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
          color: GpmColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _promoBorder, width: 1),
        ),
        child: InkWell(
          key: const Key('worker_referral_promo_card'),
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        color: GpmColors.brandSoft,
                        borderRadius: BorderRadius.circular(7),
                      ),
                      child: const Icon(
                        Icons.card_giftcard,
                        color: GpmColors.graphite,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Приведи друга — получи бонус',
                            style: TextStyle(
                              color: GpmColors.black,
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          SizedBox(height: 4),
                          Text(
                            'Чем больше смен отработает друг, тем больше бонус.',
                            style: TextStyle(
                              color: GpmColors.graphite,
                              fontSize: 12,
                              height: 1.25,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                const Row(
                  children: [
                    Expanded(
                      child: _RewardBadge(shifts: '5 смен', amount: '3 500 ₽'),
                    ),
                    SizedBox(width: 8),
                    Expanded(
                      child: _RewardBadge(shifts: '10 смен', amount: '5 000 ₽'),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: onTap,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: GpmColors.redAction,
                      foregroundColor: Colors.white,
                      minimumSize: const Size(48, 44),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 10,
                      ),
                    ),
                    child: const Text('Подробнее и пригласить'),
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
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: GpmColors.surface.withValues(alpha: 0.86),
        borderRadius: BorderRadius.circular(20),
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
                fontSize: 18,
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
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: GpmColors.brandSoft,
                  borderRadius: BorderRadius.circular(7),
                ),
                child: const Icon(
                  Icons.card_giftcard,
                  color: GpmColors.graphite,
                  size: 21,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Padding(
                  padding: EdgeInsets.zero,
                  child: const Text(
                    'Пригласить друга',
                    style: TextStyle(
                      color: GpmColors.black,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
              IconButton(
                tooltip: 'Закрыть',
                onPressed: onClose,
                constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                padding: const EdgeInsets.all(6),
                icon: const Icon(Icons.close, size: 20),
              ),
            ],
          ),
          const SizedBox(height: 10),
          const Text(
            'Можно привести друга на работу в Джи Пи Эм и получить бонус после '
            'того, как он отработает нужное количество смен.',
            style: TextStyle(
              color: GpmColors.graphite,
              fontSize: 13,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 12),
          const _DetailRewardRow(shifts: '5 смен', amount: '3 500 ₽'),
          const SizedBox(height: 7),
          const _DetailRewardRow(shifts: '10 смен', amount: '5 000 ₽'),
          const SizedBox(height: 14),
          Divider(height: 1, color: _promoBorder.withValues(alpha: 0.45)),
          const SizedBox(height: 14),
          const Text(
            'Свяжитесь с одним из специалистов в Telegram:',
            style: TextStyle(
              color: GpmColors.black,
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          _TelegramContactButton(
            name: 'Дарья',
            username: 'GPMHRDaria',
            onPressed: () => onContact('GPMHRDaria'),
          ),
          const SizedBox(height: 8),
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
    final stacked = MediaQuery.textScalerOf(context).scale(13) > 18;
    final description = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.calendar_today_outlined, color: GpmColors.graphite, size: 18),
        const SizedBox(width: 10),
        Flexible(child: Text(
          'Друг отработал $shifts',
          textAlign: stacked ? TextAlign.center : TextAlign.start,
          style: const TextStyle(color: GpmColors.graphite, fontSize: 13,
            fontWeight: FontWeight.w600, height: 1.4),
        )),
      ],
    );
    final reward = Text(amount, textAlign: TextAlign.center,
      style: const TextStyle(color: GpmColors.black, fontSize: 18,
        fontWeight: FontWeight.w800, height: 1.3));
    return Container(
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: GpmColors.page, borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _promoBorder),
      ),
      child: stacked
        ? Column(children: [description, const SizedBox(height: 8), reward])
        : Row(children: [Expanded(child: description), const SizedBox(width: 12), reward]),
    );
  }
}

class _TelegramContactButton extends StatelessWidget {
  final String name;
  final String username;
  final VoidCallback onPressed;
  const _TelegramContactButton({
    required this.name, required this.username, required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          foregroundColor: GpmColors.graphite,
          backgroundColor: GpmColors.surface,
          side: const BorderSide(color: _promoBorder),
          minimumSize: const Size(48, 72),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          alignment: Alignment.center,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const DecoratedBox(
              decoration: BoxDecoration(color: Color(0xFFEAF6FD), shape: BoxShape.circle),
              child: Padding(padding: EdgeInsets.all(9),
                child: Icon(Icons.telegram, color: Color(0xFF229ED9), size: 24)),
            ),
            const SizedBox(width: 12),
            Flexible(child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Text(name, textAlign: TextAlign.center,
                  style: const TextStyle(color: GpmColors.black, fontSize: 15,
                    fontWeight: FontWeight.w700, height: 1.3)),
                const SizedBox(height: 3),
                Text('@$username', textAlign: TextAlign.center,
                  style: const TextStyle(color: GpmColors.graphite, fontSize: 12,
                    fontWeight: FontWeight.w500, height: 1.3)),
              ],
            )),
          ],
        ),
      ),
    );
  }
}

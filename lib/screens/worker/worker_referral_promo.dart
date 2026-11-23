import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../theme/gpm_theme.dart';

const _referralTitle = 'Приведи друга - получи бонус от 3500 до 5000 рублей!';

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
  Widget build(BuildContext context) => SizedBox(
    width: double.infinity,
    child: Material(
      color: Colors.transparent,
      child: Ink(
        decoration: BoxDecoration(
          color: GpmColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: GpmColors.brandRed, width: 2),
        ),
        child: InkWell(
          key: const Key('worker_referral_promo_card'),
          onTap: onTap,
          borderRadius: BorderRadius.circular(18),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 680;
              final stacked = MediaQuery.textScalerOf(context).scale(14) > 19;
              final showGift = wide || constraints.maxWidth >= 350 || stacked;
              final gift = Container(
                width: wide ? 52 : 42,
                height: wide ? 52 : 42,
                decoration: BoxDecoration(
                  color: GpmColors.helmetYellow,
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x145F4500),
                      blurRadius: 8,
                      offset: Offset(0, 3),
                    ),
                  ],
                ),
                child: Stack(
                  alignment: Alignment.center,
                  clipBehavior: Clip.none,
                  children: [
                    Icon(
                      Icons.card_giftcard,
                      color: GpmColors.black,
                      size: wide ? 27 : 24,
                    ),
                    const Positioned(
                      top: -3,
                      right: -4,
                      child: Icon(
                        Icons.auto_awesome,
                        size: 15,
                        color: GpmColors.yellowInk,
                      ),
                    ),
                  ],
                ),
              );
              final heading = Text(
                'Акция «Приведи друга»',
                style: TextStyle(
                  color: GpmColors.black,
                  fontWeight: FontWeight.w800,
                  fontSize: wide ? 18 : 14,
                  height: 1.3,
                ),
              );
              final cta = Container(
                key: const Key('worker_referral_promo_cta'),
                padding: EdgeInsets.symmetric(
                  horizontal: wide ? 22 : 14,
                  vertical: 11,
                ),
                decoration: BoxDecoration(
                  color: GpmColors.redAction,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  wide || stacked ? 'Пригласить друга' : 'Пригласить',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              );
              final main = Row(
                children: [
                  if (showGift) ...[gift, const SizedBox(width: 12)],
                  Expanded(child: heading),
                  if (wide) ...[
                    const SizedBox(width: 20),
                    const Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          'до 5 000 ₽',
                          style: TextStyle(
                            color: GpmColors.black,
                            fontSize: 28,
                            fontWeight: FontWeight.w800,
                            height: 1.15,
                          ),
                        ),
                        SizedBox(height: 2),
                        Text(
                          'за приглашенного друга',
                          style: TextStyle(
                            color: GpmColors.muted,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(width: 28),
                  ],
                  if (!stacked) ...[const SizedBox(width: 12), cta],
                ],
              );
              return Padding(
                padding: EdgeInsets.symmetric(
                  horizontal: wide ? 20 : 14,
                  vertical: wide ? 16 : 12,
                ),
                child: stacked
                    ? Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [main, const SizedBox(height: 12), cta],
                      )
                    : main,
              );
            },
          ),
        ),
      ),
    ),
  );
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
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [GpmColors.yellowSoft, Color(0xFFFFE59A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: GpmColors.yellowLine),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const DecoratedBox(
                      decoration: BoxDecoration(
                        color: Colors.white,
                        shape: BoxShape.circle,
                      ),
                      child: Padding(
                        padding: EdgeInsets.all(10),
                        child: Icon(
                          Icons.card_giftcard_rounded,
                          color: GpmColors.yellowInk,
                          size: 22,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Text(
                        'Бонус за рекомендацию',
                        style: TextStyle(
                          color: GpmColors.yellowInk,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Закрыть',
                      onPressed: onClose,
                      icon: const Icon(Icons.close, size: 20),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                const Text(
                  _referralTitle,
                  style: TextStyle(
                    color: GpmColors.black,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  'Друг выходит на работу в Джи Пи Эм. '
                  'Он получает работу, вы — бонус за его смены.',
                  style: TextStyle(
                    color: GpmColors.graphite,
                    fontSize: 13,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
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
        const Icon(
          Icons.calendar_today_outlined,
          color: Color(0xFF9A5700),
          size: 18,
        ),
        const SizedBox(width: 10),
        Flexible(
          child: Text(
            'Друг отработал $shifts',
            textAlign: stacked ? TextAlign.center : TextAlign.start,
            style: const TextStyle(
              color: GpmColors.graphite,
              fontSize: 13,
              fontWeight: FontWeight.w600,
              height: 1.4,
            ),
          ),
        ),
      ],
    );
    final reward = Text(
      amount,
      textAlign: TextAlign.center,
      style: const TextStyle(
        color: GpmColors.yellowInk,
        fontSize: 20,
        fontWeight: FontWeight.w800,
        height: 1.3,
      ),
    );
    return Container(
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFAE9),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: GpmColors.yellowLine),
      ),
      child: stacked
          ? Column(children: [description, const SizedBox(height: 8), reward])
          : Row(
              children: [
                Expanded(child: description),
                const SizedBox(width: 12),
                reward,
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
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          foregroundColor: GpmColors.graphite,
          backgroundColor: const Color(0xFFF4FAFF),
          side: const BorderSide(color: Color(0xFFCEE6F7)),
          minimumSize: const Size(48, 72),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          alignment: Alignment.center,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const DecoratedBox(
              decoration: BoxDecoration(
                color: Color(0xFFEAF6FD),
                shape: BoxShape.circle,
              ),
              child: Padding(
                padding: EdgeInsets.all(9),
                child: Icon(Icons.telegram, color: Color(0xFF229ED9), size: 24),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    name,
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                      color: GpmColors.black,
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      height: 1.3,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    '@$username',
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                      color: GpmColors.graphite,
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      height: 1.3,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

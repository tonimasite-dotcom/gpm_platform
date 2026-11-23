<?php
namespace App\Services\Order;

/** Pure validation shared by the TS adapter and isolated tests. */
class GpmCrewBridgePolicy
{
    public const INSTANCE = 'https://ts.workstaffcrm.ru';
    public const PROTOCOL = 'gpm-crew-attendance-v1';

    public static function profileId($value): string
    {
        $text = trim((string) $value);
        if (!preg_match('/^#?([1-9][0-9]{0,8})$/D', $text, $match)) {
            throw new \InvalidArgumentException('Сначала сохраните ID в приложении в своем профиле CRM');
        }
        return '#' . $match[1];
    }

    public static function snapshot(array $value, string $orderNumber): array
    {
        if (($value['protocol'] ?? '') !== self::PROTOCOL
            || ($value['source_instance'] ?? '') !== self::INSTANCE
            || ($value['order_id'] ?? '') !== $orderNumber
            || !is_int($value['revision_number'] ?? null) || $value['revision_number'] < 0
            || !preg_match('/^[a-f0-9]{64}$/D', (string) ($value['revision'] ?? ''))
            || !preg_match('/^[a-f0-9]{64}$/D', (string) ($value['roster_fingerprint'] ?? ''))
            || !is_array($value['rows'] ?? null) || !is_array($value['proofs'] ?? null)) {
            throw new \RuntimeException('Некорректный ответ онлайн-табеля');
        }
        return $value;
    }

    public static function newer(?array $previous, array $next, string $number): array
    {
        $next = self::snapshot($next, $number);
        if ($previous && ($previous['order_id'] ?? '') === $number
            && (int) ($previous['revision_number'] ?? -1) > $next['revision_number']) {
            return $previous;
        }
        return $next;
    }
}

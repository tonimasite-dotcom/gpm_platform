<?php
namespace App\Services\Gpm;

/** Side-effect-free matching. Inputs must come from authenticated servers. */
final class GpmWorkerMatchPolicy
{
    public static function phone($raw, string $country = 'RU'): ?string
    {
        if (!is_string($raw) || strlen($raw) > 64
            || preg_match('/[^+0-9()\s-]/', $raw)) return null;
        $value = preg_replace('/[()\s-]/', '', $raw);
        if ($country === 'RU') {
            if (preg_match('/^8[0-9]{10}$/D', $value)) $value = '+7' . substr($value, 1);
            elseif (preg_match('/^[0-9]{10}$/D', $value)) $value = '+7' . $value;
            elseif (preg_match('/^7[0-9]{10}$/D', $value)) $value = '+' . $value;
            return preg_match('/^\+7[0-9]{10}$/D', $value) ? $value : null;
        }
        return $country === 'INT' && preg_match('/^\+[1-9][0-9]{7,14}$/D', $value) ? $value : null;
    }

    private static function decision(string $action, string $reason, ?string $id = null): array
    {
        return ['action' => $action, 'reason' => $reason, 'crm_worker_id' => $id];
    }

    public static function verifiedPhone(array $profile, int $now): ?string
    {
        $country = $profile['phone_country'] ?? 'RU';
        if (!is_string($country)) return null;
        $phone = self::phone($profile['phone'] ?? null, $country);
        $proof = $profile['phone_verification'] ?? null;
        if (!$phone || !is_array($proof)
            || !in_array($proof['method'] ?? '', ['sms','call'], true)
            || ($proof['environment'] ?? '') !== 'production'
            || ($proof['phone'] ?? '') !== $phone
            || !is_string($proof['proof_id'] ?? null)
            || !preg_match('/^[A-Za-z0-9_-]{20,100}$/D', $proof['proof_id'])) return null;
        $instant = is_string($proof['verified_at'] ?? null) ? strtotime($proof['verified_at']) : false;
        // Initial automatic binding needs recent ownership proof. A linked pair
        // remains stable later; this is not a periodic SMS requirement.
        if ($instant === false || $instant > $now + 30 || $instant < $now - 86400) return null;
        return $phone;
    }

    public static function resolve(array $profile, array $candidates, ?array $link,
                                   array $phoneOwners, int $now): array
    {
        $account = $profile['account_id'] ?? '';
        if (!is_string($account) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/Di', $account)
            || ($profile['role'] ?? '') !== 'worker') {
            return self::decision('review', 'invalid_worker');
        }
        if (($profile['active'] ?? false) !== true) return self::decision('skip', 'inactive_app_worker');

        if ($link && ($link['account_id'] ?? '') !== $account) {
            return self::decision('review', 'invalid_existing_link');
        }
        if ($link && !empty($link['crm_worker_id'])) {
            $bound = array_values(array_filter($candidates, function ($person) use ($link) {
                return (string) $person['id'] === (string) $link['crm_worker_id'];
            }));
            if (count($bound) !== 1 || !empty($bound[0]['deleted'])
                || !in_array('loader', $bound[0]['roles'] ?? [], true)
                || count(array_diff($bound[0]['roles'] ?? [], ['loader'])) > 0) {
                return self::decision('review', 'linked_card_unavailable', (string) $link['crm_worker_id']);
            }
            // Never rebind an already linked account because its phone changed.
            return self::decision('keep_link', 'stable_identity', (string) $link['crm_worker_id']);
        }

        $phone = self::verifiedPhone($profile, $now);
        if (!$phone) return self::decision('wait', 'phone_not_verified');
        $owners = array_values(array_unique($phoneOwners));
        if (count($owners) !== 1 || $owners[0] !== $account) {
            return self::decision('review', 'duplicate_app_phone');
        }
        $matches = [];
        foreach ($candidates as $person) {
            // Only personal phone participates, never office/shared work_phone.
            $candidate = self::phone($person['phone'] ?? null, 'RU');
            if ($candidate === null) $candidate = self::phone($person['phone'] ?? null, 'INT');
            if ($candidate === $phone) $matches[] = $person;
        }
        if (count($matches) > 1) return self::decision('review', 'duplicate_crm_phone');
        if ($matches) {
            $person = $matches[0];
            if (!empty($person['deleted'])) return self::decision('review', 'deleted_crm_card');
            if (!in_array('loader', $person['roles'] ?? [], true)
                || count(array_diff($person['roles'] ?? [], ['loader'])) > 0) {
                return self::decision('review', 'staff_role_collision');
            }
            if (!empty($person['app_account_id']) && $person['app_account_id'] !== $account) {
                return self::decision('review', 'crm_card_already_linked');
            }
            // Keep CRM active status and all existing data, even for an inactive card.
            return self::decision('link_existing', 'unique_verified_phone', (string) $person['id']);
        }
        if (empty($profile['surname']) || empty($profile['first_name'])) {
            return self::decision('wait', 'structured_name_required');
        }
        if (!is_int($profile['branch_id'] ?? null) || $profile['branch_id'] <= 0) {
            return self::decision('wait', 'trusted_branch_required');
        }
        return self::decision('create_worker', 'no_existing_phone');
    }
}

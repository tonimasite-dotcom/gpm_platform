<?php
namespace App\Services\Gpm;

/** Explicit laboratory policy. This cannot validate a production phone proof. */
final class GpmPreviewWorkerPolicy
{
    public const INSTANCE = 'https://ts.workstaffcrm.ru';
    public const PROTOCOL = 'gpm-preview-workers-v1';

    public static function snapshot(array $value): array
    {
        if (($value['protocol'] ?? '') !== self::PROTOCOL
            || ($value['source_instance'] ?? '') !== self::INSTANCE
            || ($value['environment'] ?? '') !== 'registration-preview'
            || !is_array($value['profiles'] ?? null) || count($value['profiles']) > 100) {
            throw new \RuntimeException('Invalid test worker snapshot');
        }
        $identities = [];
        foreach ($value['profiles'] as $profile) {
            if (!is_array($profile) || !self::valid($profile)
                || isset($identities[$profile['profile_id']])) {
                throw new \RuntimeException('Invalid test worker profile');
            }
            $identities[$profile['profile_id']] = true;
        }
        return $value['profiles'];
    }

    public static function valid(array $profile): bool
    {
        if (!is_string($profile['profile_id'] ?? null)
            || !preg_match('/^preview_[a-f0-9]{32}$/D', $profile['profile_id'])
            || ($profile['environment'] ?? '') !== 'registration-preview'
            || ($profile['verification_method'] ?? '') !== 'test_code'
            || ($profile['phone_verified'] ?? false) !== true
            || !is_string($profile['phone_country'] ?? null)
            || !GpmWorkerMatchPolicy::phone($profile['phone'] ?? null, $profile['phone_country'])
            || !preg_match('/^[a-f0-9]{64}$/D', (string) ($profile['revision'] ?? ''))
            || !is_array($profile['cities'] ?? null) || count($profile['cities']) > 50
            || !is_string($profile['birth_date'] ?? null)
            || !preg_match('/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/D', $profile['birth_date'])
            || !is_numeric($profile['created_at'] ?? null)) return false;
        foreach (['surname','first_name','middle_name'] as $field) {
            $name = $profile[$field] ?? null;
            if (!is_string($name) || mb_strlen($name) > 100
                || ($name === '' && $field !== 'middle_name')
                || ($name !== '' && !preg_match('/^[\p{L}\p{M}]+(?:-[\p{L}\p{M}]+)*$/uD', $name))) return false;
        }
        foreach ($profile['cities'] as $city) {
            if (!is_string($city) || $city === '' || mb_strlen($city) > 150) return false;
        }
        return true;
    }

    private static function result(string $action, string $reason, ?string $id = null): array
    {
        return ['action'=>$action, 'reason'=>$reason, 'crm_worker_id'=>$id];
    }

    public static function resolve(array $profile, array $people, ?array $link,
                                   ?int $branchId, bool $testEnabled, string $target): array
    {
        if (!$testEnabled || rtrim($target, '/') !== self::INSTANCE) {
            throw new \DomainException('Test worker matching is available only in TS');
        }
        if (!self::valid($profile)) return self::result('conflict', 'invalid_preview_profile');
        if ($link && !empty($link['crm_worker_id'])) {
            foreach ($people as $person) {
                if ((string) $person['id'] !== (string) $link['crm_worker_id']) continue;
                if (!empty($person['deleted'])) return self::result('conflict','deleted_crm_card');
                if (($person['roles'] ?? []) !== ['loader']) return self::result('conflict','staff_role_collision');
                return self::result('link', 'stable_identity', (string) $person['id']);
            }
            return self::result('conflict', 'deleted_crm_card');
        }
        $phone = GpmWorkerMatchPolicy::phone($profile['phone'], $profile['phone_country']);
        $matches = [];
        foreach ($people as $person) {
            $candidate = GpmWorkerMatchPolicy::phone($person['phone'] ?? null);
            if (!$candidate) $candidate = GpmWorkerMatchPolicy::phone($person['phone'] ?? null, 'INT');
            if ($candidate === $phone) $matches[] = $person;
        }
        if (count($matches) > 1) return self::result('conflict','duplicate_crm_phone');
        if ($matches) {
            $person = $matches[0];
            if (!empty($person['deleted'])) return self::result('conflict','deleted_crm_card');
            if (($person['roles'] ?? []) !== ['loader']) return self::result('conflict','staff_role_collision');
            if (!empty($person['preview_profile_id']) && $person['preview_profile_id'] !== $profile['profile_id']) {
                return self::result('conflict','crm_card_already_linked');
            }
            return self::result('link','unique_test_phone',(string) $person['id']);
        }
        if (!$branchId || $branchId <= 0) return self::result('deferred','trusted_branch_required');
        return self::result('create','new_test_worker');
    }
}

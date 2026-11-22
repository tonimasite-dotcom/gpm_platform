<?php
namespace App\Services\Order;

use Illuminate\Auth\Access\AuthorizationException;
use Illuminate\Support\Facades\Http;
use Illuminate\Validation\ValidationException;

/** Saved routing preference only; never creates accounts or company IDs. */
class GpmAppProfileId
{
    public const FIELD = 'gpm_app_crm_id';

    public static function allowedRole($role): bool
    {
        return in_array($role, ['logist', 'admin'], true);
    }

    private static function invalid(string $message): void
    {
        throw ValidationException::withMessages([self::FIELD => $message]);
    }

    public static function normalize($value): ?int
    {
        if ($value === null || (is_string($value) && trim($value) === '')) {
            return null;
        }
        if ((!is_string($value) && !is_int($value))
            || !preg_match('/^#?[1-9][0-9]{0,8}$/D', trim((string) $value))) {
            self::invalid('РЈРєР°Р¶РёС‚Рµ ID РІ РїСЂРёР»РѕР¶РµРЅРёРё, РЅР°РїСЂРёРјРµСЂ #1');
        }
        return (int) ltrim(trim((string) $value), '#');
    }

    private static function authorizeEditor($editor, $target, bool $creating): void
    {
        if ($editor && $editor->hasRole('admin')) {
            return;
        }
        if ($editor && $target && (string) $editor->id === (string) $target->id
            && $editor->hasAnyRole(['logist', 'admin'])) {
            return;
        }
        if ($editor && $editor->can($creating ? 'create_users' : 'update_users')) {
            return;
        }
        throw new AuthorizationException('РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ РґР»СЏ РёР·РјРµРЅРµРЅРёСЏ ID РІ РїСЂРёР»РѕР¶РµРЅРёРё');
    }

    private static function verify(int $id): void
    {
        $base = rtrim((string) env('GPM_APP_API_URL', ''), '/');
        $token = (string) env('GPM_APP_API_TOKEN', '');
        if ($base !== 'https://app-api.gpmbot.ru' || $token === '') {
            self::invalid('РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ ID РІ РїСЂРёР»РѕР¶РµРЅРёРё. РџРѕРІС‚РѕСЂРёС‚Рµ РїРѕР·Р¶Рµ');
        }
        try {
            $response = Http::timeout(8)->acceptJson()->withHeaders(['X-GPM-App-Token' => $token])
                ->get($base . '/app-api/integration/crm-logists/' . $id);
        } catch (\Throwable $error) {
            self::invalid('РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ ID РІ РїСЂРёР»РѕР¶РµРЅРёРё. РџРѕРІС‚РѕСЂРёС‚Рµ РїРѕР·Р¶Рµ');
        }
        if ($response->status() === 404) {
            self::invalid('ID РЅРµ РЅР°Р№РґРµРЅ СЃСЂРµРґРё Р°РєС‚РёРІРЅС‹С… Р»РѕРіРёСЃС‚РѕРІ Р”Р¶Рё РџРё Р­Рј');
        }
        if (!$response->successful() || (int) $response->json('crm_logist_id') !== $id
            || !is_string($response->json('account_id')) || $response->json('account_id') === '') {
            self::invalid('РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ ID РІ РїСЂРёР»РѕР¶РµРЅРёРё. РџРѕРІС‚РѕСЂРёС‚Рµ РїРѕР·Р¶Рµ');
        }
    }

    public static function prepare(array $data, $role, $current, $editor, $target = null, bool $creating = false): array
    {
        $present = array_key_exists(self::FIELD, $data);
        if (!$present && self::allowedRole($role)) {
            return $data;
        }
        $desired = $present ? self::normalize($data[self::FIELD]) : null;
        if (!self::allowedRole($role) && $desired !== null) {
            self::invalid('ID РІ РїСЂРёР»РѕР¶РµРЅРёРё РґРѕСЃС‚СѓРїРµРЅ С‚РѕР»СЊРєРѕ Р»РѕРіРёСЃС‚Сѓ Рё Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ');
        }
        $existing = self::normalize($current);
        if (!$present && $existing === null) {
            return $data;
        }
        if ($desired !== $existing) {
            self::authorizeEditor($editor, $target, $creating);
            if ($desired !== null) {
                self::verify($desired);
            }
        }
        $data[self::FIELD] = $desired;
        return $data;
    }
}

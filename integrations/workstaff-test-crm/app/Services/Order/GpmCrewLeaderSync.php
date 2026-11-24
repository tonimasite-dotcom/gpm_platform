<?php
namespace App\Services\Order;

use App\Models\Order;
use App\Models\User;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/** Headless handoff through the existing linked-order job; no CRM UI/cache/DB writes. */
class GpmCrewLeaderSync
{
    public function sync(Order $order): bool
    {
        if (rtrim((string) config('app.url'), '/') !== GpmAppOrderSync::INSTANCE
            || !filter_var(env('GPM_APP_CREW_LEADER_SYNC_ENABLED', false), FILTER_VALIDATE_BOOLEAN)) {
            return false;
        }
        try {
            // Read saved relationships and profile every time. Never trust browser input.
            $current = Order::find($order->id);
            if (!$current || in_array((int) $current->status_id, [
                Order::STATUS_COMPLETED, Order::STATUS_RETURNED, Order::STATUS_DELETE
            ], true)) return true;
            $owner = User::find($current->logist_id);
            if (!$owner || !$owner->hasAnyRole(['logist', 'admin'])
                || !preg_match('/^[1-9][0-9]{0,8}$/D', (string) $owner->gpm_app_crm_id)) {
                throw new \RuntimeException('Missing saved GPM owner ID');
            }
            $base = rtrim((string) env('GPM_APP_API_URL', ''), '/');
            $token = (string) env('GPM_APP_API_TOKEN', '');
            if ($base !== 'https://app-api.gpmbot.ru' || $token === '') {
                throw new \RuntimeException('Invalid GPM endpoint');
            }
            $current->load('users');
            $leaders = $current->users->filter(function ($worker) {
                return !empty($worker->pivot->brigadier);
            })->values();
            $chosen = $leaders->count() === 1 ? $leaders->first() : null;
            if ($leaders->count() === 0 && $current->users->count() === 1) {
                $chosen = $current->users->first();
            }
            $leader = $chosen && (int) $chosen->active === 1 && $chosen->hasRole('loader')
                ? ['crm_worker_id' => (string) $chosen->id, 'phone' => (string) $chosen->phone]
                : null;
            $response = Http::timeout(8)->withOptions(['allow_redirects' => false])
                ->acceptJson()->asJson()->withHeaders(['X-GPM-App-Token' => $token])
                ->post($base . '/app-api/integration/crew-attendance/' . rawurlencode((string) $current->order_number), [
                    'operation' => 'leader', 'source_instance' => GpmAppOrderSync::INSTANCE,
                    'sender_crm_id' => '#' . $owner->gpm_app_crm_id, 'leader' => $leader,
                ]);
            if (!$response->successful() || $response->json('success') !== true) {
                throw new \RuntimeException('GPM leader handoff deferred', $response->status());
            }
            return true;
        } catch (\Throwable $error) {
            Log::warning('GPM brigadier handoff deferred', [
                'order_id' => $order->id, 'error_type' => get_class($error),
                'error_code' => (int) $error->getCode(),
            ]);
            return false;
        }
    }
}

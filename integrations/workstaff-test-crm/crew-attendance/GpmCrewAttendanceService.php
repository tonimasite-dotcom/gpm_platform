<?php
namespace App\Services\Order;

use App\Models\Order;
use App\Models\User;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class GpmCrewAttendanceService
{
    public function enabled(): bool
    {
        return rtrim((string) config('app.url'), '/') === GpmCrewBridgePolicy::INSTANCE
            && filter_var(env('GPM_APP_CREW_ATTENDANCE_ENABLED', false), FILTER_VALIDATE_BOOLEAN);
    }

    private function number(Order $order): string
    {
        $number = app(GpmAppOrderSync::class)->crewOrderNumber($order);
        if (!$number) {
            throw new \DomainException('Сначала отправьте эту заявку в GPM', 409);
        }
        return $number;
    }

    private function call(Order $order, User $actor, string $operation, array $payload = []): array
    {
        if (!$this->enabled()) {
            throw new \DomainException('Обмен онлайн-табелем пока выключен', 503);
        }
        // Reload the saved profile on every request; never trust browser IDs/phones.
        $savedActor = User::findOrFail($actor->id);
        $crmId = GpmCrewBridgePolicy::profileId($savedActor->gpm_app_crm_id ?? null);
        $base = rtrim((string) env('GPM_APP_API_URL', ''), '/');
        $token = (string) env('GPM_APP_API_TOKEN', '');
        if ($base !== 'https://app-api.gpmbot.ru' || $token === '') {
            throw new \RuntimeException('Сервер обмена не настроен');
        }
        $number = $this->number($order);
        $body = array_merge($payload, [
            'operation' => $operation, 'source_instance' => GpmCrewBridgePolicy::INSTANCE,
            'sender_crm_id' => $crmId,
        ]);
        $response = Http::timeout(10)->withOptions(['allow_redirects' => false])
            ->acceptJson()->asJson()->withHeaders(['X-GPM-App-Token' => $token])
            ->post($base . '/app-api/integration/crew-attendance/' . rawurlencode($number), $body);
        if (!$response->successful()) {
            $status = $response->status();
            $detail = $response->json('detail');
            $message = is_string($detail) && mb_strlen($detail) <= 500
                ? $detail : 'Не удалось выполнить действие онлайн-табеля';
            throw new \DomainException($message, in_array($status, [403,404,409,422,503], true) ? $status : 503);
        }
        $result = $response->json();
        if (!is_array($result)) {
            throw new \RuntimeException('Некорректный ответ сервера табеля');
        }
        return $result;
    }

    private function directory(): string
    {
        $directory = storage_path('app/gpm-crew-attendance');
        if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) {
            throw new \RuntimeException('Cannot create attendance cache');
        }
        return $directory;
    }

    private function cache(Order $order, array $document): array
    {
        $number = $this->number($order);
        $path = $this->directory() . '/' . (int) $order->id . '.json';
        $lock = fopen($path . '.lock', 'c');
        if (!$lock) throw new \RuntimeException('Cannot lock attendance cache');
        $temporary = null;
        try {
            chmod($path . '.lock', 0600);
            if (!flock($lock, LOCK_EX)) throw new \RuntimeException('Cannot lock attendance cache');
            $previous = is_file($path) ? json_decode(file_get_contents($path), true) : null;
            $document = GpmCrewBridgePolicy::newer(is_array($previous) ? $previous : null, $document, $number);
            $temporary = tempnam($this->directory(), '.pending-');
            chmod($temporary, 0600);
            $encoded = json_encode($document, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
            if (file_put_contents($temporary, $encoded) === false || !rename($temporary, $path)) {
                throw new \RuntimeException('Cannot save attendance cache');
            }
            return $document;
        } finally {
            if ($temporary && is_file($temporary)) unlink($temporary);
            flock($lock, LOCK_UN);
            fclose($lock);
        }
    }

    public function state(Order $order, User $actor): array
    {
        if (!$this->enabled() || !app(GpmAppOrderSync::class)->linked($order)) {
            return ['enabled' => false];
        }
        $document = $this->cache($order, $this->call($order, $actor, 'export'));
        $order->load('users');
        $document['crm_workers'] = $order->users->map(function ($worker) {
            return ['id' => (string) $worker->id, 'name' => $worker->full_name,
                'is_leader' => !empty($worker->pivot->brigadier)];
        })->values()->all();
        return $document;
    }

    public function link(Order $order, User $actor, array $input): array
    {
        $order->load('users');
        $worker = $order->users->firstWhere('id', (int) ($input['crm_worker_id'] ?? 0));
        if (!$worker || !$worker->hasRole('loader') || (int) $worker->active !== 1) {
            throw new \DomainException('Выберите активного рабочего этой заявки CRM', 422);
        }
        $account = trim((string) ($input['worker_account_id'] ?? ''));
        if ($account === '' || strlen($account) > 120) {
            throw new \DomainException('Выберите профиль GPM', 422);
        }
        return $this->call($order, $actor, 'link', [
            'crm_worker_id' => (string) $worker->id, 'worker_account_id' => $account,
        ]);
    }

    public function roster(Order $order, User $actor, bool $apply = false, string $expected = ''): array
    {
        $order->load('users');
        $ids = $order->users->map(function ($worker) { return (string) $worker->id; })->values()->all();
        $brigadier = $order->users->first(function ($worker) { return !empty($worker->pivot->brigadier); });
        return $this->call($order, $actor, 'roster', [
            'crm_worker_ids' => $ids, 'crm_leader_id' => $brigadier ? (string) $brigadier->id : null,
            'apply_roster' => $apply, 'expected_roster' => $expected,
        ]);
    }

    public function enableOrder(Order $order, User $actor): array
    {
        $this->roster($order, $actor);
        return $this->call($order, $actor, 'enable');
    }

    public function review(Order $order, User $actor, array $input): array
    {
        $decision = $input['decision'] ?? '';
        $reason = trim((string) ($input['reason'] ?? ''));
        if (!in_array($decision, ['approve','reject'], true) || mb_strlen($reason) < 3 || mb_strlen($reason) > 1000) {
            throw new \DomainException('Выберите решение и укажите причину от 3 до 1000 символов', 422);
        }
        return $this->call($order, $actor, 'review', [
            'evidence_id' => (string) ($input['evidence_id'] ?? ''),
            'decision' => $decision, 'reason' => $reason,
        ]);
    }

    public function refreshQuietly(Order $order): void
    {
        if (!$this->enabled() || !app(GpmAppOrderSync::class)->linked($order)) return;
        try {
            $owner = User::find($order->logist_id);
            if ($owner) $this->state($order, $owner);
        } catch (\Throwable $error) {
            Log::warning('GPM attendance refresh deferred', [
                'order_id' => $order->id, 'error_type' => get_class($error),
                'error_code' => (int) $error->getCode(),
            ]);
        }
    }

    public function syncLeaderQuietly(Order $order, ?User $actor): void
    {
        if (!$actor || !$this->enabled()) return;
        try {
            $this->roster($order, $actor);
        } catch (\Throwable $error) {
            Log::warning('GPM attendance roster deferred', [
                'order_id' => $order->id, 'error_type' => get_class($error),
                'error_code' => (int) $error->getCode(),
            ]);
        }
    }
}

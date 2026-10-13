<?php

namespace App\Services\Order;

use App\Models\Order;
use App\Models\Reference\MetroStation;
use Carbon\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/** Runs only in the ts.workstaffcrm.ru installation; never scans unlinked orders. */
class GpmAppOrderSync
{
    public const INSTANCE = 'https://ts.workstaffcrm.ru';
    public const PROTOCOL = 'gpm-crm-sync-v1';

    public function enabled(): bool
    {
        return rtrim((string) config('app.url'), '/') === self::INSTANCE
            && filter_var(env('GPM_APP_ORDER_SYNC_ENABLED', false), FILTER_VALIDATE_BOOLEAN);
    }

    private function directory(): string
    {
        $directory = storage_path('app/gpm-app-sync');
        if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) {
            throw new \RuntimeException('Cannot create GPM sync directory');
        }
        return $directory;
    }

    private function statePath(int $orderId): string
    {
        return $this->directory() . '/' . $orderId . '.json';
    }

    private function locked(int $orderId, callable $callback)
    {
        $handle = fopen($this->directory() . '/' . $orderId . '.lock', 'c');
        if (!$handle) {
            throw new \RuntimeException('Cannot open GPM sync lock');
        }
        try {
            chmod($this->directory() . '/' . $orderId . '.lock', 0600);
            if (!flock($handle, LOCK_EX)) {
                throw new \RuntimeException('Cannot acquire GPM sync lock');
            }
            return $callback();
        } finally {
            flock($handle, LOCK_UN);
            fclose($handle);
        }
    }

    private function writeState(int $orderId, array $state): void
    {
        $temporary = tempnam($this->directory(), '.pending-');
        try {
            chmod($temporary, 0600);
            $encoded = json_encode($state, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
            if (file_put_contents($temporary, $encoded) === false || !rename($temporary, $this->statePath($orderId))) {
                throw new \RuntimeException('Cannot save GPM sync state');
            }
        } finally {
            if (is_file($temporary)) {
                unlink($temporary);
            }
        }
    }

    public function linked(Order $order): bool
    {
        return is_file($this->statePath((int) $order->id));
    }

    public function rememberPublication(Order $order, string $phone, array $appOrder, array $publishedCrm): void
    {
        // Older API versions ignore source_instance; do not silently bind them.
        if (($appOrder['source_instance'] ?? '') !== self::INSTANCE) {
            return;
        }
        $this->locked((int) $order->id, function () use ($order, $phone, $appOrder, $publishedCrm) {
            $this->writeState((int) $order->id, [
                'order_id' => (int) $order->id,
                'order_number' => (string) $order->order_number,
                'base_crm' => $publishedCrm,
                // On first linkage, existing app edits must win over the CRM
                // snapshot used to publish. The first sync reconciles them.
                'base_app' => $publishedCrm,
                'last_synced_at' => now()->toIso8601String(),
            ]);
        });
    }

    private function request()
    {
        $baseUrl = rtrim((string) env('GPM_APP_API_URL', ''), '/');
        $token = (string) env('GPM_APP_API_TOKEN', '');
        if ($baseUrl !== 'https://app-api.gpmbot.ru' || $token === '') {
            throw new \RuntimeException('GPM sync server configuration is missing or unsupported');
        }
        return Http::timeout(8)->acceptJson()->asJson()->withHeaders(['X-GPM-App-Token' => $token]);
    }

    private function endpoint(string $orderNumber): string
    {
        return rtrim((string) env('GPM_APP_API_URL'), '/')
            . '/app-api/integration/order-sync/' . rawurlencode($orderNumber);
    }

    private function snapshot($response, string $orderNumber): array
    {
        if (!$response->successful()) {
            // Never put tokens, response bodies, phone numbers or credentials in logs.
            throw new \RuntimeException('GPM sync HTTP failure', $response->status());
        }
        $snapshot = $response->json();
        if (!is_array($snapshot) || ($snapshot['protocol'] ?? '') !== self::PROTOCOL
            || ($snapshot['source_instance'] ?? '') !== self::INSTANCE
            || ($snapshot['order_id'] ?? '') !== $orderNumber
            || !is_array($snapshot['fields'] ?? null)
            || !preg_match('/^[a-f0-9]{64}$/D', $snapshot['revision'] ?? '')) {
            throw new \RuntimeException('Invalid GPM sync response');
        }
        return $snapshot;
    }

    public function syncOrder(Order $order): bool
    {
        try {
            if (!$this->enabled() || !$this->linked($order)) {
                return false;
            }
            return $this->locked((int) $order->id, function () use ($order) {
                $state = json_decode(file_get_contents($this->statePath((int) $order->id)), true, 512, JSON_THROW_ON_ERROR);
                $next = DB::transaction(function () use ($order, $state) {
                    $current = Order::whereKey($order->id)->lockForUpdate()->firstOrFail();
                    $number = (string) $current->order_number;
                    if ($number !== $state['order_number']) {
                        throw new \RuntimeException('Linked CRM order number changed');
                    }
                    $snapshot = $this->snapshot($this->request()->get($this->endpoint($number)), $number);
                    if (in_array($snapshot['status'], ['CONVERTED', 'JUNK'], true)
                        || in_array((int) $current->status_id, [Order::STATUS_COMPLETED, Order::STATUS_RETURNED, Order::STATUS_DELETE], true)) {
                        return null;
                    }
                    $crm = $this->crmFields($current);
                    $app = $this->comparableFields($snapshot['fields']);
                    $plan = GpmOrderSyncPlan::make($state['base_crm'], $state['base_app'], $crm, $app);
                    if ($plan['to_app']) {
                        $snapshot = $this->snapshot($this->request()->patch($this->endpoint($number), [
                            'source_instance' => self::INSTANCE,
                            'revision' => $snapshot['revision'],
                            'fields' => $plan['to_app'],
                        ]), $number);
                        $app = $this->comparableFields($snapshot['fields']);
                    }
                    $toCrm = array_intersect_key($plan['to_crm'], array_flip([
                        'city', 'address', 'description', 'workers_count', 'hours', 'min_time',
                        'price_per_hour', 'address_street', 'address_number', 'scheduled_at',
                        'address_lat', 'address_lon', 'additional_info', 'metro',
                    ]));
                    if ($toCrm) {
                        $this->applyAppFields($current, $toCrm);
                        $current->save();
                        $current->unsetRelation('metroStation');
                        Log::info('GPM app fields applied to CRM order', [
                            'order_id' => $current->id, 'fields' => array_keys($toCrm),
                        ]);
                    }
                    // An interrupted write is retried from the old baseline and
                    // converges because app values win conflicting changes.
                    return ['state' => array_merge($state, [
                        'base_crm' => $this->crmFields($current),
                        'base_app' => $app,
                        'last_synced_at' => now()->toIso8601String(),
                    ]), 'conflicts' => $plan['conflicts']];
                });
                // Save the baseline AFTER the CRM transaction commits. If this
                // filesystem write fails, the old baseline safely retries.
                if ($next !== null) {
                    $this->writeState((int) $order->id, $next['state']);
                    if ($next['conflicts']) {
                        Log::info('GPM sync conflicts resolved using app values', [
                            'order_id' => $order->id, 'fields' => $next['conflicts'],
                        ]);
                    }
                }
                return true;
            });
        } catch (\Throwable $exception) {
            Log::warning('GPM order sync deferred', [
                'order_id' => $order->id,
                // The exception class is safe; HTTP exceptions can contain URLs/headers.
                'error_type' => get_class($exception),
                'error_code' => (int) $exception->getCode(),
            ]);
            return false;
        }
    }

    public function syncLinkedOrders(): array
    {
        $result = ['synced' => 0, 'deferred' => 0];
        foreach (glob($this->directory() . '/*.json') ?: [] as $path) {
            $id = basename($path, '.json');
            if (!ctype_digit($id)) {
                continue;
            }
            $order = Order::find((int) $id);
            if (!$order) {
                continue;
            }
            $result[$this->syncOrder($order) ? 'synced' : 'deferred']++;
        }
        return $result;
    }

    private function comparableFields(array $fields): array
    {
        $result = [];
        foreach (['city', 'address', 'description', 'metro', 'additional_info', 'address_street', 'address_number'] as $field) {
            $result[$field] = (string) ($fields[$field] ?? '');
        }
        foreach (['workers_count', 'hours', 'min_time', 'price_per_hour', 'price_regular', 'price_state', 'individual_price', 'legal_price'] as $field) {
            $result[$field] = isset($fields[$field]) ? (int) $fields[$field] : null;
        }
        foreach (['address_lat', 'address_lon'] as $field) {
            $result[$field] = (float) ($fields[$field] ?? 0);
        }
        $result['scheduled_at'] = Carbon::parse($fields['scheduled_at'])->utc()->toIso8601String();
        return $result;
    }

    public function crmFields(Order $order): array
    {
        $order->loadMissing('metroStation');
        $coords = $order->coords;
        if (is_string($coords)) {
            $coords = json_decode($coords, true) ?: preg_split('/[,; ]+/', $coords);
        }
        $additional = [];
        if (!empty($order->additional)) {
            $additional[] = is_array($order->additional)
                ? json_encode($order->additional, JSON_UNESCAPED_UNICODE) : (string) $order->additional;
        }
        if (!empty($order->info)) {
            $additional[] = (string) $order->info;
        }
        return $this->comparableFields([
            'city' => $order->city, 'address' => $order->address ?: trim($order->city . ', ' . $order->street . ', ' . $order->house),
            'description' => $order->note ?? $order->info ?? '',
            'metro' => optional($order->metroStation)->name,
            'additional_info' => trim(implode("\n", $additional)),
            'address_street' => $order->street ?: $order->address,
            'address_number' => $order->house ?: '0',
            'address_lat' => $coords[0] ?? 0, 'address_lon' => $coords[1] ?? 0,
            'scheduled_at' => $order->completion_date->toIso8601String(),
            'workers_count' => $order->loader_count,
            'hours' => $order->duration ?? $order->min_time ?? 4,
            'min_time' => $order->min_time ?? $order->duration ?? 4,
            'price_per_hour' => $order->workers_cost,
            'price_regular' => $order->workers_cost,
            'price_state' => $order->workers_cost,
            'individual_price' => $order->customer_cost,
            'legal_price' => $order->customer_cost,
        ]);
    }

    private function applyAppFields(Order $order, array $fields): void
    {
        foreach (['city' => 'city', 'address' => 'address', 'description' => 'note',
            'workers_count' => 'loader_count', 'hours' => 'duration', 'min_time' => 'min_time',
            'price_per_hour' => 'workers_cost', 'address_street' => 'street', 'address_number' => 'house'] as $field => $column) {
            if (array_key_exists($field, $fields)) {
                $order->$column = $fields[$field];
            }
        }
        if (isset($fields['scheduled_at'])) {
            $order->completion_date = Carbon::parse($fields['scheduled_at'])->utc();
        }
        if (array_key_exists('address_lat', $fields) || array_key_exists('address_lon', $fields)) {
            $current = $this->crmFields($order);
            $order->coords = json_encode([
                $fields['address_lat'] ?? $current['address_lat'],
                $fields['address_lon'] ?? $current['address_lon'],
            ]);
        }
        if (array_key_exists('additional_info', $fields)) {
            // Do not overwrite structured CRM options; put free-form text into info.
            $structured = !empty($order->additional) ? json_encode($order->additional, JSON_UNESCAPED_UNICODE) : '';
            $text = (string) $fields['additional_info'];
            if ($structured !== '' && strpos($text, $structured) === 0) {
                $text = ltrim(substr($text, strlen($structured)), "\n");
            }
            $order->info = $text;
        }
        if (array_key_exists('metro', $fields)) {
            if ($fields['metro'] === '') {
                $order->metro_id = null;
            } else {
                $matches = MetroStation::where('name', $fields['metro'])->limit(2)->get();
                if ($matches->count() !== 1) {
                    throw new \RuntimeException('App metro is not unique in CRM reference');
                }
                $order->metro_id = $matches->first()->id;
            }
        }
        // Separate app staff/contract rates and app-only title/nationality/work
        // mode remain owned by GPM. CRM has one worker rate and no such columns.
    }
}

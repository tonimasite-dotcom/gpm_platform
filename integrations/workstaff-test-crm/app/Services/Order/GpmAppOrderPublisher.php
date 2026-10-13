<?php

namespace App\Services\Order;

use App\Models\Order;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class GpmAppOrderPublisher
{
    public function publish(Order $order, string $logistPhone = ''): bool
    {
        if (rtrim((string) config('app.url'), '/') !== GpmAppOrderSync::INSTANCE) {
            return false;
        }
        $baseUrl = rtrim((string) env('GPM_APP_API_URL', ''), '/');
        $token = (string) env('GPM_APP_API_TOKEN', '');

        if ($baseUrl === '') {
            return false;
        }

        $sync = new GpmAppOrderSync();
        if ($sync->enabled() && $sync->linked($order)) {
            return $sync->syncOrder($order);
        }

        try {
            $order->loadMissing(['metroStation', 'contactPerson']);
            $publishedCrm = $sync->crmFields($order);

            $payload = [
                'source_system' => 'workstaff',
                'source_instance' => GpmAppOrderSync::INSTANCE,
                'preserve_existing_content' => $sync->enabled(),
                'telegram_username' => optional($order->logistModel)->username ?? '',
                'logist_phone' => $logistPhone,
                'client_phone' => $order->contact_phone ?? '',
                'client_email' => $order->contact_email ?? '',
                'city' => $order->city ?? '',
                'order_data' => [
                    'order_number' => (string) $order->order_number,
                    'completion_date' => [
                        'date' => optional($order->completion_date)->toIso8601String(),
                    ],
                    'timezone' => config('app.default_timezone', 'Europe/Moscow'),
                    'loaders' => [
                        'loader_count' => (int) ($order->loader_count ?? 0),
                    ],
                    'info' => [
                        'address' => $order->address ?: trim(($order->city ?? '') . ', ' . ($order->street ?? '') . ', ' . ($order->house ?? '')),
                        'address_street' => $order->street ?? '',
                        'address_number' => $order->house ?? '',
                        'address_lat' => $this->coord($order->coords, 0),
                        'address_lon' => $this->coord($order->coords, 1),
                        'metro_station' => optional($order->metroStation)->name,
                        'additional' => $this->additionalText($order),
                    ],
                    'note' => $order->note ?? $order->info ?? '',
                    'min_time' => (int) ($order->min_time ?? $order->duration ?? 4),
                    'hours' => (int) ($order->duration ?? $order->min_time ?? 4),
                    'worker_category' => 'loader',
                    'work_mode' => 'rate',
                    'price_per_hour' => $order->workers_cost,
                    'price_regular' => $order->workers_cost,
                    'price_state' => $order->workers_cost,
                    'individual_price' => $order->customer_cost,
                    'legal_price' => $order->customer_cost,
                ],
            ];

            $request = Http::timeout(5)->acceptJson()->asJson();

            if ($token !== '') {
                $request = $request->withHeaders(['X-GPM-App-Token' => $token]);
            }

            $response = $request->post($baseUrl . '/app-api/orders', $payload);

            if ($response->successful() && is_array($response->json('order'))) {
                $sync->rememberPublication($order, $logistPhone, $response->json('order'), $publishedCrm);
            }

            if (!$response->successful()) {
                Log::warning('GPM app order publish failed', [
                    'order_id' => $order->id,
                    'order_number' => $order->order_number,
                    'status' => $response->status(),
                    'body' => $response->body(),
                ]);
            }

            return $response->successful();
        } catch (\Throwable $e) {
            Log::warning('GPM app order publish exception', [
                'order_id' => $order->id ?? null,
                'order_number' => $order->order_number ?? null,
                'error' => $e->getMessage(),
            ]);

            return false;
        }
    }

    private function coord($coords, int $index)
    {
        if (is_array($coords)) {
            return $coords[$index] ?? 0;
        }

        if (is_string($coords) && $coords !== '') {
            $decoded = json_decode($coords, true);
            if (is_array($decoded)) {
                return $decoded[$index] ?? 0;
            }

            $parts = preg_split('/[,; ]+/', $coords);
            return isset($parts[$index]) ? (float) $parts[$index] : 0;
        }

        return 0;
    }

    private function additionalText(Order $order): string
    {
        $parts = [];

        if (!empty($order->additional)) {
            $parts[] = is_array($order->additional)
                ? json_encode($order->additional, JSON_UNESCAPED_UNICODE)
                : (string) $order->additional;
        }

        if (!empty($order->info)) {
            $parts[] = (string) $order->info;
        }

        return trim(implode("\n", $parts));
    }
}

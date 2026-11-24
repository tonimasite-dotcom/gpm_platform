<?php

namespace App\Services\Order;

use App\Models\Order;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class GpmAppOrderPublisher
{
    private $errorMessage = 'Не удалось отправить заявку в GPM';
    private $errorStatus = 502;

    public function errorMessage(): string { return $this->errorMessage; }
    public function errorStatus(): int { return $this->errorStatus; }

    private function fail(string $message, int $status = 422): bool
    {
        $this->errorMessage = $message;
        $this->errorStatus = $status;
        return false;
    }

    private function requestModeration(string $baseUrl, string $token, string $number, int $code, string $recipient): bool
    {
        $requestId = bin2hex(random_bytes(16));
        $response = Http::timeout(8)->acceptJson()->asJson()
            ->withHeaders(['X-GPM-App-Token' => $token])
            ->post($baseUrl . '/app-api/integration/order-resubmission/' . rawurlencode($number), [
                'source_instance' => GpmAppOrderSync::INSTANCE,
                'logist_crm_id' => $code,
                'request_id' => $requestId,
            ]);
        if (!$response->successful()) {
            if ($response->status() === 409) {
                return $this->fail('Повторная модерация доступна только до начала работ', 409);
            }
            return $this->fail('Не удалось передать заявку на модерацию в GPM. Повторите отправку позже', 502);
        }
        $result = $response->json();
        if (!is_array($result) || ($result['success'] ?? false) !== true
            || ($result['request_id'] ?? '') !== $requestId
            || ($result['logist_account_id'] ?? '') !== $recipient
            || (($result['status'] ?? '') !== 'NEW' && ($result['already_applied'] ?? false) !== true)) {
            return $this->fail('GPM не подтвердил повторную модерацию заявки', 502);
        }
        return true;
    }

    private function profileCrmId(string $requested, string $phone): ?int
    {
        $sender = auth()->user();
        $sender = $sender ? $sender->fresh() : null;
        if (!$sender || !$sender->hasAnyRole(['logist', 'admin'])) {
            $this->fail('Отправка доступна логисту или администратору с ID в профиле', 403);
            return null;
        }
        $saved = $sender->gpm_app_crm_id;
        if ((!is_int($saved) && !is_string($saved))
            || !preg_match('/^[1-9][0-9]{0,8}$/D', (string) $saved)) {
            $this->fail('Сначала добавьте ID в приложении в настройках профиля');
            return null;
        }
        if (trim($phone) !== '') {
            $this->fail('Отправка доступна только по ID из настроек профиля');
            return null;
        }
        $requested = trim($requested);
        if ($requested !== '' && (!preg_match('/^#?[1-9][0-9]{0,8}$/D', $requested)
            || (int) ltrim($requested, '#') !== (int) $saved)) {
            $this->fail('ID изменился. Обновите профиль и повторите отправку');
            return null;
        }
        return (int) $saved;
    }

    public function publish(Order $order, string $logistPhone = '', string $logistCrmId = ''): bool
    {
        if (rtrim((string) config('app.url'), '/') !== GpmAppOrderSync::INSTANCE) {
            return false;
        }
        $baseUrl = rtrim((string) env('GPM_APP_API_URL', ''), '/');
        $token = (string) env('GPM_APP_API_TOKEN', '');

        if ($baseUrl !== 'https://app-api.gpmbot.ru' || $token === '') {
            return false;
        }

        $sync = new GpmAppOrderSync();
        try {
            $code = $this->profileCrmId($logistCrmId, $logistPhone);
            if ($code === null) {
                return false;
            }
            $logistPhone = '';
            $lookup = Http::timeout(8)->acceptJson()->withHeaders(['X-GPM-App-Token' => $token])
                ->get($baseUrl . '/app-api/integration/crm-logists/' . $code);
            if ($lookup->status() === 404) {
                return $this->fail('ID не найден среди активных логистов Джи Пи Эм');
            }
            if (!$lookup->successful() || (int) $lookup->json('crm_logist_id') !== $code
                || !is_string($lookup->json('account_id')) || $lookup->json('account_id') === '') {
                return $this->fail('Не удалось проверить ID в GPM. Повторите отправку позже', 502);
            }
            $recipient = $lookup->json('account_id');
            if ($sync->enabled() && $sync->linked($order)) {
                if ($recipient !== null) {
                    $linked = Http::timeout(8)->acceptJson()->withHeaders(['X-GPM-App-Token' => $token])
                        ->get($baseUrl . '/app-api/integration/order-sync/' . rawurlencode((string) $order->order_number));
                    if (!$linked->successful()) {
                        return $this->fail('Связь заявки с GPM недоступна. Сообщите администратору', 409);
                    }
                    if ($linked->json('logist_account_id') !== $recipient) {
                        return $this->fail('Заявка уже закреплена за другим логистом', 409);
                    }
                }
                if (!in_array($linked->json('status'), ['NEW', 'PROCESSED'], true)) {
                    return $this->fail('Повторная модерация доступна только до начала работ', 409);
                }
                $success = $sync->syncOrder($order);
                if (!$success) {
                    return $this->fail('Не удалось синхронизировать заявку с GPM', 502);
                }
                return $this->requestModeration($baseUrl, $token, (string) $order->order_number, $code, $recipient);
            }
            if (!is_numeric($order->workers_cost) || (float) $order->workers_cost <= 0) {
                return $this->fail('Укажите положительную ставку рабочим перед отправкой');
            }
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

            if ($code !== null) {
                $payload['logist_crm_id'] = $code;
            }
            $request = Http::timeout(8)->acceptJson()->asJson();

            if ($token !== '') {
                $request = $request->withHeaders(['X-GPM-App-Token' => $token]);
            }

            $response = $request->post($baseUrl . '/app-api/orders', $payload);

            if ($response->successful()) {
                $appOrder = $response->json('order');
                if (!is_array($appOrder) || ($recipient !== null && ($appOrder['logist_account_id'] ?? '') !== $recipient)) {
                    return $this->fail('GPM вернул неполный результат отправки. Сообщите администратору', 502);
                }
                $sync->rememberPublication($order, $logistPhone, $appOrder, $publishedCrm);
                if (($appOrder['status'] ?? 'NEW') !== 'NEW') {
                    return $this->requestModeration($baseUrl, $token, (string) $order->order_number, $code, $recipient);
                }
            }

            if (!$response->successful()) {
                Log::warning('GPM app order publish failed', [
                    'order_id' => $order->id,
                    'order_number' => $order->order_number,
                    'status' => $response->status(),
                    'error_type' => 'GpmApiRejection',
                ]);
            }

            if (!$response->successful()) {
                $detail = $response->json('detail');
                $messages = [
                    'ID не найден среди активных логистов Джи Пи Эм',
                    'Укажите ID логиста в приложении, например #1',
                    'Заявка уже закреплена за другим логистом',
                    'Укажите положительную ставку исполнителя за час или смену',
                ];
                if (is_string($detail) && in_array($detail, $messages, true)) {
                    return $this->fail($detail, $response->status() === 409 ? 409 : 422);
                }
                if (is_string($detail) && strpos($detail, 'logist_phone') !== false) {
                    return $this->fail('Телефон не соответствует активному логисту GPM. Проверьте его или используйте ID');
                }
                return $this->fail('GPM отклонил заявку. Проверьте ставку и заполнение полей', 422);
            }
            return true;
        } catch (\Throwable $e) {
            Log::warning('GPM app order publish exception', [
                'order_id' => $order->id ?? null,
                'order_number' => $order->order_number ?? null,
                'error_type' => get_class($e),
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

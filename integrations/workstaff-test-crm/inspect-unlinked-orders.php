<?php
// Read-only metadata inspection. Never links an order by matching a number.
$root = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
try {
    if (realpath($root) !== $root) { throw new RuntimeException('Unexpected CRM path'); }
    require $root . '/vendor/autoload.php';
    $app = require $root . '/bootstrap/app.php';
    $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    $url = rtrim((string) env('GPM_APP_API_URL', ''), '/');
    if (rtrim(config('app.url'), '/') !== 'https://ts.workstaffcrm.ru' || $url !== 'https://app-api.gpmbot.ru') {
        throw new RuntimeException('Unexpected instance');
    }
    $response = Illuminate\Support\Facades\Http::timeout(10)->acceptJson()
        ->withHeaders(['X-GPM-App-Token' => (string) env('GPM_APP_API_TOKEN', '')])
        ->get($url . '/app-api/orders');
    if (!$response->successful() || !is_array($response->json('orders'))) {
        throw new RuntimeException('App order list unavailable');
    }
    $candidates = [];
    $linked = 0;
    foreach ($response->json('orders') as $order) {
        if (($order['source_system'] ?? '') !== 'workstaff'
            || !in_array($order['source'] ?? '', ['external', 'crm'], true)
            || in_array($order['status'] ?? '', ['CONVERTED', 'JUNK'], true)) {
            continue;
        }
        $instance = (string) ($order['source_instance'] ?? '');
        if ($instance === 'https://ts.workstaffcrm.ru') { $linked++; continue; }
        if ($instance !== '') { continue; }
        $number = (string) ($order['external_order_id'] ?? $order['id'] ?? '');
        $matches = App\Models\Order::where('order_number', $number)->get(['id', 'order_number', 'status_id']);
        $candidates[] = [
            'app_order_number' => $number, 'app_status' => $order['status'] ?? '',
            'matching_test_crm_ids' => $matches->pluck('id')->all(),
            'requires_explicit_test_crm_republication' => true,
        ];
    }
    echo json_encode(['tagged_active_test_orders' => $linked, 'unbound_active_candidates' => $candidates,
        'changed_orders' => 0], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . PHP_EOL;
} catch (Throwable $error) {
    fwrite(STDERR, 'Unlinked-order inspection stopped (' . get_class($error) . "); no credentials printed.\n");
    exit(1);
}

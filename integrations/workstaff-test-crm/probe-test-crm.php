<?php
// Safe runtime/API checks. Does not publish orders or print tokens/responses.
$root = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
try {
    if (realpath($root) !== $root) { throw new RuntimeException('Unexpected CRM scope'); }
    require $root . '/vendor/autoload.php';
    $app = require $root . '/bootstrap/app.php';
    $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    $url = rtrim((string) env('GPM_APP_API_URL', ''), '/');
    $token = (string) env('GPM_APP_API_TOKEN', '');
    if (rtrim(config('app.url'), '/') !== 'https://ts.workstaffcrm.ru'
        || $url !== 'https://app-api.gpmbot.ru' || $token === '') {
        throw new RuntimeException('Unexpected CRM/API configuration');
    }
    $spec = Illuminate\Support\Facades\Http::timeout(10)->acceptJson()->get($url . '/openapi.json');
    $document = $spec->json();
    $path = is_array($document) ? ($document['paths']['/app-api/integration/order-sync/{order_id}'] ?? null) : null;
    $protocol = $spec->successful() && is_array($path) && isset($path['get'], $path['patch']);
    $probe = Illuminate\Support\Facades\Http::timeout(10)->acceptJson()
        ->withHeaders(['X-GPM-App-Token' => $token])
        ->get($url . '/app-api/integration/order-sync/__gpm_release_probe_never_create__');
    $auth = $probe->status() === 404 && $probe->json('detail') === 'order not found';
    $result = [
        'test_crm_only' => true, 'new_api_protocol_present' => $protocol,
        'integration_auth_valid' => $auth,
        'sync_enabled' => filter_var(env('GPM_APP_ORDER_SYNC_ENABLED', false), FILTER_VALIDATE_BOOLEAN),
        'configuration_cached' => $app->configurationIsCached(),
    ];
    echo json_encode($result) . PHP_EOL;
    exit($protocol && $auth ? 0 : 3);
} catch (Throwable $error) {
    fwrite(STDERR, 'Test CRM probe failed (' . get_class($error) . "); credentials not printed.\n");
    exit(2);
}

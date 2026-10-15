<?php
// Explicit legacy linkage only. Matching numbers alone never authorize --apply.
$root = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
try {
    $options = getopt('', ['crm-id:', 'order-number:', 'apply', 'confirmed-test-origin']);
    $number = (string) ($options['order-number'] ?? '');
    $id = (int) ($options['crm-id'] ?? 0);
    $apply = array_key_exists('apply', $options);
    if ($id <= 0 || !preg_match('/^[A-Za-z0-9_\/#-]{1,100}$/', $number)
        || ($apply && !array_key_exists('confirmed-test-origin', $options)) || realpath($root) !== $root) {
        throw new RuntimeException('Explicit order and test-origin confirmation required');
    }
    require $root . '/vendor/autoload.php';
    $app = require $root . '/bootstrap/app.php';
    $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    if (rtrim(config('app.url'), '/') !== 'https://ts.workstaffcrm.ru'
        || rtrim((string) env('GPM_APP_API_URL'), '/') !== 'https://app-api.gpmbot.ru') {
        throw new RuntimeException('Unexpected CRM/API scope');
    }
    $sync = new App\Services\Order\GpmAppOrderSync();
    if (!$sync->enabled()) { throw new RuntimeException('Sync must already pass runtime checks'); }
    $request = Illuminate\Support\Facades\Http::timeout(10)->acceptJson()
        ->withHeaders(['X-GPM-App-Token' => (string) env('GPM_APP_API_TOKEN', '')]);
    $url = 'https://app-api.gpmbot.ru';
    $readOrder = function () use ($request, $url, $number) {
        $response = $request->get($url . '/app-api/orders');
        if (!$response->successful()) { throw new RuntimeException('App orders unavailable'); }
        $matches = array_values(array_filter($response->json('orders') ?? [], function ($row) use ($number) {
            return (string) ($row['external_order_id'] ?? $row['id'] ?? '') === $number;
        }));
        if (count($matches) !== 1) { throw new RuntimeException('Order identity is not unique'); }
        return $matches[0];
    };
    $before = $readOrder();
    if (($before['source_system'] ?? '') !== 'workstaff'
        || !in_array($before['source'] ?? '', ['external', 'crm'], true)
        || !in_array($before['source_instance'] ?? '', ['', 'https://ts.workstaffcrm.ru'], true)
        || in_array($before['status'] ?? '', ['CONVERTED', 'JUNK'], true)) {
        throw new RuntimeException('Order belongs to another source or is closed');
    }
    $order = App\Models\Order::findOrFail($id);
    if ((string) $order->order_number !== $number
        || in_array((int) $order->status_id, [App\Models\Order::STATUS_COMPLETED, App\Models\Order::STATUS_RETURNED, App\Models\Order::STATUS_DELETE], true)) {
        throw new RuntimeException('Test CRM order is closed or has another identity');
    }
    $phone = (string) ($before['logist_phone'] ?? '');
    if ($phone === '') { throw new RuntimeException('Existing app owner identity missing'); }
    $crmBefore = $sync->crmFields($order);
    echo json_encode(['crm_id' => $id, 'order_number' => $number, 'app_status' => $before['status'],
        'crm_status_id' => $order->status_id, 'apply' => $apply, 'preserve_existing_app_content' => true]) . PHP_EOL;
    if (!$apply) { exit(0); }
    if (!(new App\Services\Order\GpmAppOrderPublisher())->publish($order, $phone)) {
        throw new RuntimeException('Explicit test publication did not succeed');
    }
    $afterLink = $readOrder();
    if (($afterLink['source_instance'] ?? '') !== 'https://ts.workstaffcrm.ru') {
        throw new RuntimeException('App did not confirm test binding');
    }
    $workflow = ['status', 'assigned_worker_ids', 'applications', 'worker_hours', 'worker_reviews',
                 'logist_account_id', 'created_at', 'created_by', 'created_by_role'];
    $preserved = true;
    foreach ($workflow as $field) {
        if (($before[$field] ?? null) != ($afterLink[$field] ?? null)) { $preserved = false; }
    }
    if (!$sync->syncOrder($order)) { throw new RuntimeException('Initial linked sync was deferred'); }
    $order = App\Models\Order::findOrFail($id);
    $crmAfter = $sync->crmFields($order);
    $changed = [];
    foreach ($crmAfter as $field => $value) {
        if (($crmBefore[$field] ?? null) != $value) { $changed[] = $field; }
    }
    echo json_encode(['linked' => true, 'synced' => true, 'workflow_preserved_at_link' => $preserved,
        'test_crm_changed_fields' => $changed, 'other_crm_touched' => false]) . PHP_EOL;
} catch (Throwable $error) {
    fwrite(STDERR, 'Explicit test-order linkage stopped (' . get_class($error) . "); private contents not printed.\n");
    exit(1);
}

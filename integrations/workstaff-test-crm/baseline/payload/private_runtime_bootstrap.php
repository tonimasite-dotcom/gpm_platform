<?php
// No application bootstrap is allowed until the private identity is checked.
$root = '/root/gpm-ts-update/20261106-baseline-01/candidate';
if (PHP_SAPI !== 'cli' || realpath($root) !== $root || getenv('GPM_TS_REHEARSAL') !== '1'
    || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')
    || !is_file($root . '/storage/framework/down')) {
    throw new RuntimeException('PRIVATE_RUNTIME_CONTEXT_REQUIRED');
}
require $root . '/vendor/autoload.php';
$private = Dotenv\Dotenv::parse(file_get_contents($root . '/.env'));
foreach (['DB_CONNECTION' => 'mysql', 'DB_SOCKET' => '/root/gpm-ts-update/20261106-baseline-01/rehearsal-mysql/mysql.sock',
    'DB_DATABASE' => 'gpm_ts_rehearsal_20261106', 'DB_USERNAME' => 'gpm_ts_rehearsal',
    'APP_URL' => 'https://ts.workstaffcrm.ru', 'GPM_APP_ORDER_SYNC_ENABLED' => 'false',
    'GPM_APP_API_URL' => 'https://invalid.invalid', 'GPM_APP_API_TOKEN' => '',
    'MAIL_MAILER' => 'log', 'MAIL_DRIVER' => 'log', 'CACHE_DRIVER' => 'array'] as $key => $expected) {
    if (($private[$key] ?? null) !== $expected || (getenv($key) !== false && getenv($key) !== $expected)) {
        throw new RuntimeException('PRIVATE_RUNTIME_CONFIGURATION_REQUIRED');
    }
}
$app = require $root . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
App\Services\Release\GpmTsRehearsal::assertContext();
if (config('cache.default') !== 'array' || config('session.driver') !== 'array'
    || config('gpm_app_order_sync.enabled') === true) {
    throw new RuntimeException('PRIVATE_RUNTIME_SERVICES_REQUIRED');
}
return $app;

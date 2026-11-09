<?php
$root = '/root/gpm-ts-update/20261109-switch-01/runtime';
$work = dirname($root);
$marker = $root . '/.gpm-switch-version';
if (PHP_SAPI !== 'cli' || getenv('GPM_TS_SWITCH') !== '1' || getenv('GPM_TS_REHEARSAL') !== '1'
    || realpath($root) !== $root || realpath($marker) !== $marker || !is_file($marker)
    || !is_file($root . '/storage/framework/down')
    || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')) {
    throw new RuntimeException('PRIVATE_SWITCH_PREFLIGHT_REQUIRED');
}
$version = trim(file_get_contents($marker));
if (!in_array($version, ['old', 'new'], true)) throw new RuntimeException('PRIVATE_SWITCH_VERSION_REQUIRED');
$generation = $root . '/.gpm-switch-generation';
$final = false;
if ($version === 'new' && file_exists($generation)) {
    if (realpath($generation) !== $generation || !is_file($generation) || trim(file_get_contents($generation)) !== 'final') {
        throw new RuntimeException('PRIVATE_SWITCH_GENERATION_REQUIRED');
    }
    $final = true;
}
require $root . '/vendor/autoload.php';
$private = Dotenv\Dotenv::parse(file_get_contents($root . '/.env'));
foreach (['DB_CONNECTION' => 'mysql', 'DB_HOST' => 'localhost',
    'DB_SOCKET' => $work . '/mysql-' . $version . '/mysql.sock',
    'DB_DATABASE' => $version === 'old' ? 'gpm_ts_backup_20261109' : ($final ? 'gpm_ts_switch_final' : 'gpm_ts_switch_new'),
    'DB_USERNAME' => $version === 'old' ? 'gpm_ts_switch_old' : ($final ? 'gpm_ts_switch_final' : 'gpm_ts_switch_new'), 'APP_ENV' => 'testing',
    'GPM_APP_ORDER_SYNC_ENABLED' => 'false', 'GPM_APP_API_URL' => 'https://invalid.invalid',
    'GPM_APP_API_TOKEN' => '', 'MAIL_MAILER' => 'log', 'MAIL_DRIVER' => 'log',
    'CACHE_DRIVER' => 'array', 'SESSION_DRIVER' => 'array'] as $key => $expected) {
    if (($private[$key] ?? null) !== $expected || (getenv($key) !== false && getenv($key) !== $expected)) {
        throw new RuntimeException('PRIVATE_SWITCH_CONFIGURATION_REQUIRED');
    }
}
$app = require $root . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
App\Services\Release\GpmTsSwitchContext::assertRuntime();
return $app;

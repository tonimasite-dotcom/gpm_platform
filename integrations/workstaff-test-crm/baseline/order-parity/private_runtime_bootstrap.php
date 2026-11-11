<?php
// Test harness only. No production apply mode and no shared MySQL fallback.
$work = getenv('GPM_TS_PRIVATE_ROOT');
if (PHP_SAPI !== 'cli' || !is_string($work)
    || !preg_match('#^/root/gpm-ts-update/order-parity-[0-9-]+$#D', $work)
    || realpath($work) !== $work || getenv('GPM_TS_REHEARSAL') !== '1'
    || getenv('GPM_TS_DEMO_REHEARSAL') !== '1'
    || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')) {
    throw new RuntimeException('PRIVATE_NETWORK_CONTEXT_REQUIRED');
}
$candidateRoot = $work . '/candidate';
if (realpath($candidateRoot) !== $candidateRoot || !is_file($candidateRoot . '/storage/framework/down')) {
    throw new RuntimeException('PRIVATE_RUNTIME_PATH_REQUIRED');
}
$migration = json_decode(file_get_contents($work . '/candidate-migration-verification.json'), true, 512, JSON_THROW_ON_ERROR);
if (($migration['success'] ?? false) !== true || ($migration['live_changed'] ?? null) !== false
    || ($migration['all_original_rows_unchanged'] ?? false) !== true
    || ($migration['pending_migrations'] ?? null) !== 0) {
    throw new RuntimeException('SUCCESSFUL_PRIVATE_MIGRATION_REQUIRED');
}
require $candidateRoot . '/vendor/autoload.php';
$private = Dotenv\Dotenv::parse(file_get_contents($candidateRoot . '/.env'));
$identity = json_decode(file_get_contents($work . '/rehearsal-mysql/identity.json'), true, 512, JSON_THROW_ON_ERROR);
if ($identity['socket'] !== $work . '/rehearsal-mysql/mysql.sock'
    || $identity['datadir'] !== $work . '/rehearsal-mysql/data'
    || $identity['database'] !== 'gpm_order_parity_20261110'
    || $identity['username'] !== 'gpm_order_parity'
    || realpath($identity['datadir']) !== $identity['datadir']
    || is_link($identity['socket']) || filetype($identity['socket']) !== 'socket') {
    throw new RuntimeException('PRIVATE_SAVED_IDENTITY_REQUIRED');
}
$pid = trim(file_get_contents($work . '/rehearsal-mysql/mysql.pid'));
if (!ctype_digit($pid) || (int) $pid < 1) throw new RuntimeException('PRIVATE_MYSQL_PID_REQUIRED');
$command = file_get_contents('/proc/' . $pid . '/cmdline');
if (strpos($command, '--datadir=' . $identity['datadir'] . "\0") === false
    || strpos($command, '--socket=' . $identity['socket'] . "\0") === false
    || readlink('/proc/' . $pid . '/ns/net') === readlink('/proc/1/ns/net')) {
    throw new RuntimeException('PRIVATE_MYSQL_PROCESS_REQUIRED_BEFORE_BOOTSTRAP');
}
foreach (['DB_CONNECTION' => 'mysql', 'DB_SOCKET' => $identity['socket'],
    'DB_DATABASE' => $identity['database'], 'DB_USERNAME' => $identity['username'],
    'DB_PASSWORD' => $identity['password'], 'APP_URL' => 'https://ts.workstaffcrm.ru',
    'GPM_APP_API_URL' => 'https://invalid.invalid', 'GPM_APP_API_TOKEN' => '',
    'CACHE_DRIVER' => 'array', 'SESSION_DRIVER' => 'array', 'QUEUE_CONNECTION' => 'sync'] as $key => $expected) {
    if (($private[$key] ?? null) !== $expected
        || (getenv($key) !== false && getenv($key) !== $expected)) {
        throw new RuntimeException('PRIVATE_CONFIGURATION_REQUIRED_BEFORE_BOOTSTRAP');
    }
}
$app = require $candidateRoot . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
App\Services\Release\GpmTsRehearsal::assertContext();
App\Services\Release\GpmTsDemoPolicy::assertContext();
if (config('cache.default') !== 'array' || config('session.driver') !== 'array') {
    throw new RuntimeException('PRIVATE_ARRAY_STORES_REQUIRED');
}
// Process-only test double. Production sync code/configuration is not modified.
$app['config']->set('gpm_app_order_sync.enabled', false);
// The existing sync service reads env() directly, not this config key. Clamp
// every Laravel env adapter in this process too; never write the .env file.
$_ENV['GPM_APP_ORDER_SYNC_ENABLED'] = 'false';
$_SERVER['GPM_APP_ORDER_SYNC_ENABLED'] = 'false';
putenv('GPM_APP_ORDER_SYNC_ENABLED=false');
if (!class_exists(App\Services\Order\GpmAppOrderSync::class)
    || (new App\Services\Order\GpmAppOrderSync())->enabled()) {
    throw new RuntimeException('PRIVATE_SYNC_MUST_BE_DISABLED');
}
return $app;

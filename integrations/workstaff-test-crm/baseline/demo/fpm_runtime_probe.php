<?php
// Operator-only read of effective guarded TS runtime; never a public route.
if (PHP_SAPI !== 'fpm-fcgi' || ($_SERVER['SERVER_NAME'] ?? '') !== 'ts.workstaffcrm.ru'
    || !hash_equals((string) getenv('GPM_TS_PRIVATE_PROBE_TOKEN'), trim(file_get_contents(__DIR__ . '/token')))) {
    http_response_code(403); exit;
}
$root = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
try {
    if (realpath($root) !== $root || realpath($root . '/.env') !== $root . '/.env') { throw new RuntimeException(); }
    require $root . '/vendor/autoload.php';
    $environment = Dotenv\Dotenv::parse(file_get_contents($root . '/.env'));
    if (rtrim($environment['APP_URL'] ?? '', '/') !== 'https://ts.workstaffcrm.ru'
        || ($environment['DB_DATABASE'] ?? '') !== 'ts_workstaff') { throw new RuntimeException(); }
    $app = require $root . '/bootstrap/app.php';
    $app->make(Illuminate\Contracts\Http\Kernel::class)->bootstrap();
    App\Services\Release\GpmTsDemoPolicy::assertContext();
    $pass = App\Services\Release\GpmTsDemoPolicy::VERSION === 'ts-demo-20261110-05'
        && config('mail.default') === 'gpm_ts_demo' && config('mail.driver') === 'gpm_ts_demo'
        && config('broadcasting.default') === 'null' && config('auth.login_email_code_enabled') === true
        && config('database.connections.mysql.database') === $environment['DB_DATABASE']
        && Illuminate\Support\Facades\Mail::getSwiftMailer()->getTransport() instanceof App\Services\Release\GpmTsDemoTransport
        && (new App\Services\Order\GpmAppOrderSync())->enabled();
    $report = ['passed' => $pass, 'php_sapi' => PHP_SAPI,
        'demo_version' => App\Services\Release\GpmTsDemoPolicy::VERSION,
        'login_code_check_enabled' => config('auth.login_email_code_enabled') === true,
        'existing_gpm_sync_enabled' => (new App\Services\Order\GpmAppOrderSync())->enabled(),
        'mail_transport_is_null' => config('mail.default') === 'gpm_ts_demo',
        'broadcast_transport_is_null' => config('broadcasting.default') === 'null',
        'explicit_sql_or_sync_executed' => false,
        'opened_database_connections' => count($app['db']->getConnections()), 'main_crm_accessed' => false];
    header('Content-Type: application/json'); echo json_encode($report);
} catch (Throwable $error) {
    http_response_code(500); header('Content-Type: application/json');
    echo json_encode(['passed' => false, 'safe_error' => 'GUARDED_TS_RUNTIME_REJECTED_DETAILS_WITHHELD']);
}

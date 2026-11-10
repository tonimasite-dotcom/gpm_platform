<?php
// Pure container + actual handlers. No Laravel bootstrap, DB, mail or job dispatch.
$live = PHP_SAPI === 'fpm-fcgi';
if ($live) {
    if (($_SERVER['SERVER_NAME'] ?? '') !== 'ts.workstaffcrm.ru'
        || !hash_equals((string) getenv('GPM_TS_PRIVATE_PROBE_TOKEN'), trim(file_get_contents(__DIR__ . '/token')))) {
        http_response_code(403); exit;
    }
    $root = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
    $vendor = $root . '/vendor/autoload.php';
} else {
    if (PHP_SAPI !== 'cli' || getenv('GPM_TS_DEBT_FIXTURE') !== '1'
        || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')) { exit(2); }
    $root = '/root/gpm-ts-update/20261110-debt-off-01/runtime';
    $vendor = '/root/gpm-ts-update/20261106-baseline-01/candidate/vendor/autoload.php';
}
try {
    if (realpath($root) !== $root) { throw new RuntimeException('EXACT_ROOT_REQUIRED'); }
    require $vendor;
    if (!$live) {
        spl_autoload_register(static function ($name) use ($root) {
            if (strpos($name, 'App\\') === 0) {
                $file = $root . '/app/' . str_replace('\\', '/', substr($name, 4)) . '.php';
                if (is_file($file)) { require $file; }
            }
        }, true, true);
    }
    $app = new Illuminate\Foundation\Application($root);
    $app->instance('config', new Illuminate\Config\Repository(['app' => ['url' => 'https://ts.workstaffcrm.ru'],
        'database' => ['default' => 'forbidden']]));
    Illuminate\Support\Facades\Facade::clearResolvedInstances();
    Illuminate\Support\Facades\Facade::setFacadeApplication($app);
    $attempts = [];
    foreach (['db', 'mail.manager', 'mailer', 'filesystem'] as $service) {
        $app->bind($service, static function () use (&$attempts, $service) {
            $attempts[] = $service; throw new RuntimeException('DEBT_BODY_SERVICE_TRAP');
        });
    }
    $checks = [];
    foreach ([['App\\Console\\Commands\\CheckDebit', 'handle', [], 0],
              ['App\\Console\\Commands\\CheckDebit', 'sendMail', array_fill(0, 6, null), null],
              ['App\\Console\\Commands\\CheckCustomerDebit', 'handle', [], 0],
              ['App\\Services\\WebKlexMailClient', 'sendDebitMessage', array_fill(0, 5, null), null]] as $case) {
        [$class, $method, $args, $expected] = $case;
        $reflection = new ReflectionClass($class);
        $object = $reflection->newInstanceWithoutConstructor();
        $call = $reflection->getMethod($method); $call->setAccessible(true);
        if ($call->invokeArgs($object, $args) !== $expected) { throw new RuntimeException('DEBT_HANDLER_NOT_DISABLED'); }
        $checks[] = $class . '::' . $method;
    }
    if ($attempts || $app->resolved('db') || $app->resolved('mail.manager')) { throw new RuntimeException('DEBT_SERVICES_TOUCHED'); }
    if ($live) { header('Content-Type: application/json'); }
    echo json_encode(['passed' => true, 'checks' => $checks, 'sapi' => PHP_SAPI,
        'database_accessed' => false, 'mail_transport_accessed' => false, 'laravel_bootstrapped' => false,
        'actual_job_dispatched' => false, 'main_crm_accessed' => false]);
} catch (Throwable $error) {
    if ($live) { http_response_code(500); header('Content-Type: application/json'); }
    echo json_encode(['passed' => false, 'safe_error' => 'DEBT_GUARD_PROBE_FAILED_DETAILS_WITHHELD']);
    if (!$live) { exit(1); }
}

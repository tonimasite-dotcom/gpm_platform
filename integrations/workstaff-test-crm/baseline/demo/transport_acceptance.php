<?php
// Run only with unshare --net. No .env, Laravel bootstrap, SQL or real sync.
use App\Services\Release\GpmTsDemoPolicy;
use App\Services\Release\GpmTsDemoTransport;
use Illuminate\Config\Repository;
use Illuminate\Events\Dispatcher;
use Illuminate\Foundation\Application;
use Illuminate\Mail\Events\MessageSending;
use Illuminate\Mail\Mailable;
use Illuminate\Mail\SendQueuedMailable;
use Illuminate\Support\Facades\Facade;
use Illuminate\Support\Facades\Mail;
use Symfony\Component\HttpKernel\Exception\HttpException;

$root = '/root/gpm-ts-update/20261110-demo-05/runtime';
if (PHP_SAPI !== 'cli' || getenv('GPM_TS_DEMO_REHEARSAL') !== '1'
    || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')
    || realpath($root) !== $root || !is_file($root . '/PRIVATE_DEMO_NO_DATABASE') || is_file($root . '/.env')) {
    throw new RuntimeException('ISOLATED_DEMO_ACCEPTANCE_REQUIRED');
}
require '/root/gpm-ts-update/20261106-baseline-01/candidate/vendor/autoload.php';
spl_autoload_register(static function ($name) use ($root) {
    if (strpos($name, 'App\\') === 0) {
        $file = $root . '/app/' . str_replace('\\', '/', substr($name, 4)) . '.php';
        if (is_file($file)) { require $file; }
    }
}, true, true);

$app = new Application($root);
$app->instance('env', 'production');
$app->instance('config', new Repository([
    'app' => ['url' => 'https://ts.workstaffcrm.ru', 'env' => 'production'],
    // Intentionally unsafe settings: policy must win without an env switch.
    'mail' => ['default' => 'smtp', 'from' => ['address' => 'fixture@example.invalid'],
        'mailers' => ['smtp' => ['transport' => 'smtp', 'host' => '127.0.0.1', 'port' => 9]]],
    'view' => ['paths' => [$root . '/resources/views'], 'compiled' => $root . '/bootstrap/cache'],
    'session' => ['driver' => 'array'],
    'database' => ['default' => 'forbidden'],
]));
$app->instance('events', new Dispatcher($app));
$logger = new class {
    public $rows = [];
    public function info($name, array $context = []) { $this->rows[] = [$name, $context]; }
};
$app->instance('log', $logger);
$fixtureKey = str_repeat('f', 32);
$privateFixtureEnvironment = dirname($root) . '/private-auth-environment.json';
if (is_file($privateFixtureEnvironment)) {
    $fixtureEnvironment = json_decode(file_get_contents($privateFixtureEnvironment), true, 512, JSON_THROW_ON_ERROR);
    $fixtureKey = base64_decode(substr($fixtureEnvironment['APP_KEY'], 7), true);
    if (!is_string($fixtureKey) || strlen($fixtureKey) !== 32) { throw new RuntimeException('PRIVATE_FIXTURE_KEY_REQUIRED'); }
}
$app->instance('encrypter', new Illuminate\Encryption\Encrypter($fixtureKey, 'AES-256-CBC'));
if (!is_dir($root . '/storage/app')) { mkdir($root . '/storage/app', 0700, true); }
$fixtureActor = (new ReflectionClass(App\Models\User::class))->newInstanceWithoutConstructor();
$fixtureActor->setRawAttributes(['id' => 424242, 'email' => 'fixture@example.invalid',
    'remember_token' => 'synthetic-fixture-code', 'active' => true]);
$fixtureActor->exists = true;
$fixtureAuth = new class($fixtureActor) {
    public $actor;
    public function __construct($actor) { $this->actor = $actor; }
    public function user() { return $this->actor; }
};
$app->instance('auth', $fixtureAuth);
Facade::clearResolvedInstances();
Facade::setFacadeApplication($app);
$app->register(Illuminate\Filesystem\FilesystemServiceProvider::class);
$app->register(Illuminate\View\ViewServiceProvider::class);
$app->register(Illuminate\Mail\MailServiceProvider::class);

$checks = [];
function verifyDemo($name, $condition) {
    global $checks;
    if (!$condition) { throw new RuntimeException('DEMO_ASSERTION:' . $name); }
    $checks[] = $name;
}
function expectContextRejection($name, callable $action) {
    try { $action(); }
    catch (RuntimeException $e) {
        verifyDemo($name, strpos($e->getMessage(), 'GPM_TS_DEMO_') === 0);
        return;
    }
    throw new RuntimeException('CONTEXT_ACCEPTED:' . $name);
}

GpmTsDemoPolicy::assertContext();
$app['config']->set('app.url', 'https://workstaffcrm.ru');
expectContextRejection('main_url_rejected', static function () { GpmTsDemoPolicy::suppress('mail'); });
$app['config']->set('app.url', 'https://ts.workstaffcrm.ru');
$app->setBasePath('/var/www/gruzpiter/data/www/workstaffcrm.ru');
expectContextRejection('main_path_rejected', static function () { GpmTsDemoPolicy::suppress('mail'); });
$app->setBasePath($root);
putenv('GPM_TS_DEMO_REHEARSAL=0');
expectContextRejection('unverified_private_path_rejected', static function () { GpmTsDemoPolicy::suppress('mail'); });
putenv('GPM_TS_DEMO_REHEARSAL=1');
// No recognized setting enables outgoing deliveries.
putenv('GPM_TS_DEMO_ENABLED=false');
putenv('GPM_TS_REAL_SEND_ENABLED=true');
(new App\Providers\AppServiceProvider($app))->boot();
verifyDemo('smtp_default_replaced', $app['config']->get('mail.default') === 'gpm_ts_demo');
verifyDemo('legacy_smtp_driver_replaced', $app['config']->get('mail.driver') === 'gpm_ts_demo');
verifyDemo('broadcast_transport_disabled', $app['config']->get('broadcasting.default') === 'null');
$httpRequest = Illuminate\Http\Request::create('/api/private-fixture');
$httpResponse = new Symfony\Component\HttpFoundation\Response('', 401);
$app['events']->dispatch(new Illuminate\Foundation\Http\Events\RequestHandled($httpRequest, $httpResponse));
verifyDemo('http_demo_marker_preserves_unauthorized_status', $httpResponse->getStatusCode() === 401
    && $httpResponse->headers->get('X-GPM-TS-Demo') === GpmTsDemoPolicy::VERSION);
verifyDemo('smtp_settings_preserved', $app['config']->get('mail.mailers.smtp.host') === '127.0.0.1');
$events = 0;
$app['events']->listen(MessageSending::class, static function () use (&$events) { ++$events; });
Mail::raw('private fixture; never print bodies', static function ($message) {
    $message->to('fixture@example.invalid')->subject('fixture');
});
// The policy listener returns false before subsequent listeners or transport.
verifyDemo('laravel_mail_cancelled', $events === 0);
verifyDemo('default_transport_has_no_network', Mail::getSwiftMailer()->getTransport() instanceof GpmTsDemoTransport);
$before = count($logger->rows);
Mail::mailer('smtp')->raw('private named mailer fixture', static function ($message) {
    $message->to('fixture@example.invalid')->subject('fixture');
});
verifyDemo('explicit_smtp_mailer_cancelled', count($logger->rows) > $before && $events === 0);

$mailable = new class extends Mailable {
    public function build() { return $this->from('fixture@example.invalid')->to('fixture@example.invalid')->html('private fixture'); }
};
$job = new SendQueuedMailable($mailable);
$before = count($logger->rows);
$job->handle($app['mail.manager']);
verifyDemo('queued_mailable_cancelled', count($logger->rows) > $before && $events === 0);
$failed = [];
$message = (new Swift_Message('fixture'))->setFrom('fixture@example.invalid')->setTo('fixture@example.invalid')->setBody('private fixture');
verifyDemo('direct_swift_reports_zero_deliveries', Mail::getSwiftMailer()->send($message, $failed) === 0);

$manifest = json_decode(file_get_contents(dirname($root) . '/manifest.json'), true, 512, JSON_THROW_ON_ERROR);
$invoked = [];
$typeOnly = [];
foreach ($manifest['guards'] as $file => $methods) {
    if ($file === 'app/Providers/AppServiceProvider.php') { continue; }
    $text = file_get_contents($root . '/' . $file);
    preg_match('/^\s*namespace\s+([^;]+);/m', $text, $ns);
    preg_match('/^\s*(?:(?:final|abstract)\s+)?(?:class|trait)\s+(\w+)/m', $text, $class);
    $name = trim($ns[1]) . '\\' . $class[1];
    // A trait has no instance: exercise the real trait in a minimal caller.
    if (strpos($file, 'Traits/') !== false) {
        $name = 'DemoTraitCaller' . count($invoked);
        eval('class ' . $name . ' { use \\' . trim($ns[1]) . '\\' . $class[1] . '; }');
    }
    $reflection = new ReflectionClass($name);
    if ($reflection->isAbstract()) {
        eval('class DemoDadataCaller extends \\App\\Services\\Dadata\\ClientBase {}');
        $reflection = new ReflectionClass('DemoDadataCaller');
    }
    $object = $reflection->newInstanceWithoutConstructor();
    foreach ($methods as $method => $insertion) {
        $call = $reflection->getMethod($method);
        $call->setAccessible(true);
        $args = [];
        $unresolvable = false;
        foreach ($call->getParameters() as $param) {
            if ($file === 'app/Services/WebKlexMailClient.php' && $method === 'sendVerifyMessage') {
                $args[] = $fixtureActor;
                continue;
            }
            if ($param->isDefaultValueAvailable()) { $args[] = $param->getDefaultValue(); continue; }
            $type = $param->getType();
            if (!$type || $type->allowsNull()) { $args[] = null; continue; }
            if ($type->isBuiltin()) {
                $defaults = ['array' => [], 'string' => 'fixture', 'int' => 0, 'float' => 0.0, 'bool' => false];
                $args[] = $defaults[$type->getName()] ?? null;
            } elseif (class_exists($type->getName())) {
                $argument = new ReflectionClass($type->getName());
                if ($argument->isInstantiable()) { $args[] = $argument->newInstanceWithoutConstructor(); }
                else { $unresolvable = true; }
            } else { $unresolvable = true; }
        }
        $label = $file . ':' . $method;
        if ($unresolvable) {
            // Dead legacy aliases must fail PHP type checks before network code.
            try { $call->invokeArgs($object, array_fill(0, $call->getNumberOfRequiredParameters(), null)); }
            catch (TypeError $e) { $typeOnly[] = $label; continue; }
            throw new RuntimeException('UNRESOLVED_TYPE_DID_NOT_FAIL_CLOSED');
        }
        $before = count($logger->rows);
        try {
            $result = $call->invokeArgs($object, $args);
            if (strpos($insertion, '::deny(') !== false) { throw new RuntimeException('EXPECTED_DEMO_REJECTION:' . $label); }
            if ($method === 'setSmtpConfig') {
                verifyDemo('null_smtp:' . $file, $result === true && Mail::getSwiftMailer()->getTransport() instanceof GpmTsDemoTransport);
            } else {
                verifyDemo('suppressed:' . $label, count($logger->rows) > $before);
            }
        } catch (HttpException $e) {
            verifyDemo('denied:' . $label, $e->getStatusCode() === 409 && count($logger->rows) > $before);
        }
        $invoked[] = $label;
    }
}

$metadataOnly = true;
foreach ($logger->rows as [$name, $row]) {
    $metadataOnly = $metadataOnly && $name === 'GPM_TS_DEMO_SUPPRESSED'
        && array_keys($row) === ['channel', 'delivered'] && $row['delivered'] === false;
}
verifyDemo('all_log_records_metadata_only', $metadataOnly);
$captured = $root . '/storage/app/gpm-ts-demo-login/424242.enc';
$cipher = file_get_contents($captured);
verifyDemo('login_code_never_stored_as_plaintext', strpos($cipher, 'synthetic-fixture-code') === false
    && strpos($cipher, 'fixture@example.invalid') === false);
$payload = json_decode(Illuminate\Support\Facades\Crypt::decryptString($cipher), true);
verifyDemo('encrypted_login_capture_matches_authenticated_user', $payload['user_id'] === 424242
    && $payload['code'] === 'synthetic-fixture-code');
verifyDemo('login_inbox_private_file_permissions', (fileperms($captured) & 0077) === 0
    && (fileperms(dirname($captured)) & 0077) === 0);
require __DIR__ . '/read_login_inbox.php';
$visible = gpmPrivateLoginRecords(dirname($captured), $app['encrypter']);
verifyDemo('private_reader_returns_fresh_challenge', count($visible) === 1 && $visible[0]['code'] === 'synthetic-fixture-code');
verifyDemo('private_reader_hides_old_challenge', gpmPrivateLoginRecords(dirname($captured), $app['encrypter'], time() + 601) === []);
$fixtureAuth->actor = null;
try {
    App\Services\Release\GpmTsDemoLoginInbox::capture($fixtureActor);
    throw new LogicException('UNAUTHENTICATED_CAPTURE_ACCEPTED');
} catch (RuntimeException $e) {
    verifyDemo('unauthenticated_login_capture_rejected', $e->getMessage() === 'VERIFIED_LOGIN_CHALLENGE_REQUIRED');
}
$fixtureAuth->actor = $fixtureActor;
App\Services\Release\GpmTsDemoLoginInbox::consume($fixtureActor);
$consumed = json_decode(Illuminate\Support\Facades\Crypt::decryptString(file_get_contents($captured)), true);
verifyDemo('successful_verify_removes_captured_code', $consumed['code'] === null);
verifyDemo('private_reader_hides_consumed_challenge', gpmPrivateLoginRecords(dirname($captured), $app['encrypter']) === []);
verifyDemo('database_service_never_resolved', !$app->resolved('db'));
verifyDemo('gpm_sync_service_never_resolved', !$app->resolved(App\Services\Order\GpmAppOrderSync::class));
foreach (['app/Services/Order/GpmAppOrderSync.php', 'app/Services/Order/GpmAppOrderPublisher.php',
          'app/Services/Order/GpmLogistOrderGuard.php', 'app/Services/Order/GpmWorkerRateRules.php',
          'app/Http/Controllers/Order/GpmWorkerRateController.php', 'config/auth.php',
          'app/Console/Kernel.php', 'routes/api.php'] as $file) {
    verifyDemo('preserved:' . $file, hash_file('sha256', $root . '/' . $file)
        === hash_file('sha256', '/root/gpm-ts-update/20261106-baseline-01/source-ts/' . $file));
}
echo json_encode(['passed' => true, 'checks' => $checks, 'guarded_methods_invoked' => $invoked,
    'legacy_type_errors_before_transport' => $typeOnly, 'laravel_bootstrapped' => false,
    'database_accessed' => false, 'live_sync_executed' => false, 'external_network_namespace' => false,
    'live_files_changed' => false], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";

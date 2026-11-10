<?php
// Actual login/verify + JWT against the saved 72-table PRIVATE recovery only.
use App\Models\User;
use App\Services\Release\GpmTsDemoLoginInbox;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;

$root = '/root/gpm-ts-update/20261110-demo-05/runtime';
$database = '/root/gpm-ts-update/20261106-baseline-01/sql-recovery-20261109/rehearsal-mysql';
$app = null; $checks = []; $current = 'preflight'; $before = null;
function authAssert($value): void { if (!$value) { throw new RuntimeException('PRIVATE_AUTH_ASSERTION_FAILED'); } }
function authCheck($name, callable $action): void {
    global $checks, $current;
    $current = $name; $action(); $checks[] = $name;
}
function authRequest(array $data): Request {
    global $app;
    $request = Request::create('/api/private-login-fixture', 'POST', $data, [], [], ['HTTP_ACCEPT' => 'application/json']);
    $request->setLaravelSession($app['session']->driver());
    $app->instance('request', $request); $app['auth']->forgetGuards();
    return $request;
}
function authRejected(callable $action): void {
    try { $action(); }
    catch (Illuminate\Validation\ValidationException $e) { return; }
    throw new RuntimeException('EXPECTED_AUTH_REJECTION_MISSING');
}
function privateRows(): array {
    $pdo = DB::connection()->getPdo(); $result = [];
    foreach ($pdo->query('SHOW TABLES')->fetchAll(PDO::FETCH_COLUMN) as $table) {
        if (!preg_match('/^[a-zA-Z0-9_]+$/', $table)) { throw new RuntimeException('UNEXPECTED_TABLE_NAME'); }
        $hashes = [];
        $statement = $pdo->query('SELECT * FROM `' . $table . '`');
        while ($row = $statement->fetch(PDO::FETCH_ASSOC)) { $hashes[] = hash('sha256', serialize($row)); }
        sort($hashes, SORT_STRING);
        $result[$table] = ['rows' => count($hashes), 'sha256' => hash('sha256', implode('', $hashes))];
    }
    ksort($result); return $result;
}

try {
    authAssert(PHP_SAPI === 'cli' && getenv('GPM_TS_DEMO_REHEARSAL') === '1'
        && readlink('/proc/self/ns/net') !== readlink('/proc/1/ns/net') && realpath($root) === $root
        && !is_file($root . '/.env') && !is_file($root . '/bootstrap/cache/config.php'));
    $identity = json_decode(file_get_contents($database . '/identity.json'), true, 512, JSON_THROW_ON_ERROR);
    authAssert($identity['datadir'] === $database . '/data' && $identity['socket'] === $database . '/mysql.sock'
        && $identity['database'] === 'gpm_ts_backup_20261109' && $identity['username'] === 'gpm_ts_backup_recovery');
    foreach (['DB_SOCKET' => $identity['socket'], 'DB_DATABASE' => $identity['database'],
              'DB_USERNAME' => $identity['username'], 'DB_PASSWORD' => $identity['password'],
              'DB_CONNECTION' => 'mysql', 'DB_HOST' => 'localhost', 'APP_URL' => 'https://ts.workstaffcrm.ru',
              'APP_ENV' => 'testing', 'CACHE_DRIVER' => 'array', 'SESSION_DRIVER' => 'array',
              'GPM_APP_ORDER_SYNC_ENABLED' => 'false', 'GPM_APP_API_URL' => 'https://invalid.invalid',
              'GPM_APP_API_TOKEN' => '', 'LOGIN_EMAIL_CODE_ENABLED' => 'true'] as $key => $expected) {
        authAssert(getenv($key) === $expected);
    }
    // Verify server identity with a direct pinned socket before app bootstrap.
    $pdo = new PDO('mysql:unix_socket=' . $identity['socket'] . ';dbname=' . $identity['database'],
        $identity['username'], $identity['password'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $server = $pdo->query('SELECT DATABASE() AS db,CURRENT_USER() AS account,@@datadir AS datadir,@@skip_networking AS isolated')->fetch(PDO::FETCH_ASSOC);
    authAssert($server['db'] === $identity['database'] && $server['account'] === $identity['username'] . '@localhost'
        && realpath($server['datadir']) === $identity['datadir'] && (int) $server['isolated'] === 1);
    $pdo = null;
    require '/root/gpm-ts-update/20261106-baseline-01/candidate/vendor/autoload.php';
    spl_autoload_register(static function ($name) use ($root) {
        if (strpos($name, 'App\\') === 0) {
            $file = $root . '/app/' . str_replace('\\', '/', substr($name, 4)) . '.php';
            if (is_file($file)) { require $file; }
        }
    }, true, true);
    $app = require $root . '/bootstrap/app.php';
    $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    App\Services\Release\GpmTsDemoPolicy::assertContext();
    authAssert(config('database.connections.mysql.unix_socket') === $identity['socket']
        && config('database.connections.mysql.database') === $identity['database']
        && config('database.connections.mysql.username') === $identity['username']
        && config('cache.default') === 'array' && config('session.driver') === 'array'
        && config('auth.login_email_code_enabled') === true);
    authAssert(Illuminate\Support\Facades\Mail::getSwiftMailer()->getTransport() instanceof App\Services\Release\GpmTsDemoTransport);
    // Captcha is an isolated process double, never a live bypass/flag/config edit.
    $app['validator']->extend('captcha', static function ($attribute, $value) { return $value === 'private-demo-captcha'; });
    $before = privateRows(); authAssert(count($before) === 72);
    $attempt = getenv('GPM_TS_AUTH_ATTEMPT');
    authAssert(is_string($attempt) && preg_match('/^[0-9]{2}$/', $attempt));
    $snapshot = dirname($root) . '/auth-rows-' . $attempt . '-before.json';
    $snapshotFile = fopen($snapshot, 'x'); fwrite($snapshotFile, json_encode($before)); fclose($snapshotFile);
    DB::beginTransaction();
    $password = bin2hex(random_bytes(20)); $tag = bin2hex(random_bytes(8)); $actors = [];
    foreach (['owner', 'other', 'inactive'] as $kind) {
        $id = DB::table('users')->insertGetId(['surname' => 'Synthetic', 'first_name' => 'DemoLogin',
            'email' => 'private-demo-' . $kind . '-' . $tag . '@example.invalid', 'password' => Hash::make($password),
            'active' => $kind === 'inactive' ? 0 : 1, 'branch_id' => 0, 'created_at' => now(), 'updated_at' => now()]);
        $user = User::findOrFail($id);
        $user->assignRole(Spatie\Permission\Models\Role::findByName('logist', 'api'));
        $actors[$kind] = $user;
    }
    $owner = $actors['owner']; $other = $actors['other'];
    $credentials = ['login' => $owner->email, 'email' => $owner->email, 'password' => $password,
                    'g-recaptcha-response' => 'private-demo-captcha'];
    $login = static function ($data) use ($app) {
        $request = authRequest($data); return $app->make(App\Http\Controllers\Auth\LoginController::class)->login($request);
    };
    $verify = static function ($data) use ($app) {
        $request = authRequest($data); return $app->make(App\Http\Controllers\Auth\LoginController::class)->verify($request);
    };
    authCheck('correct_password_without_remember_creates_private_code_not_jwt', static function () use ($login, $credentials) {
        $body = $login($credentials)->getData(true);
        authAssert(($body['success'] ?? false) === true && !isset($body['token']));
    });
    $capturePath = storage_path('app/gpm-ts-demo-login/' . $owner->id . '.enc');
    $capture = json_decode(Crypt::decryptString(file_get_contents($capturePath)), true);
    $ownCode = DB::table('users')->where('id', $owner->id)->value('remember_token');
    authCheck('captured_code_matches_real_user_challenge', static function () use ($capture, $ownCode, $owner) {
        authAssert($capture['user_id'] === $owner->id && $capture['code'] === $ownCode && $capture['email'] === $owner->email);
    });
    authCheck('wrong_password_creates_no_new_capture', static function () use ($login, $credentials, $capturePath) {
        $before = hash_file('sha256', $capturePath); $bad = $credentials; $bad['password'] = 'private-wrong-password';
        authRejected(static function () use ($login, $bad) { $login($bad); });
        authAssert(hash_file('sha256', $capturePath) === $before);
    });
    authCheck('missing_captcha_rejected', static function () use ($login, $credentials) {
        $bad = $credentials; unset($bad['g-recaptcha-response']);
        authRejected(static function () use ($login, $bad) { $login($bad); });
    });
    authCheck('wrong_captcha_rejected', static function () use ($login, $credentials) {
        $bad = $credentials; $bad['g-recaptcha-response'] = 'invalid-fixture';
        authRejected(static function () use ($login, $bad) { $login($bad); });
    });
    authCheck('inactive_user_rejected', static function () use ($login, $credentials, $actors) {
        $bad = $credentials; $bad['login'] = $bad['email'] = $actors['inactive']->email;
        authRejected(static function () use ($login, $bad) { $login($bad); });
    });
    authCheck('missing_code_rejected', static function () use ($verify, $credentials) {
        authRejected(static function () use ($verify, $credentials) { $verify($credentials); });
    });
    $otherCode = 'private-other-' . bin2hex(random_bytes(8));
    DB::table('users')->where('id', $other->id)->update(['remember_token' => $otherCode]);
    authCheck('other_users_code_rejected_even_with_correct_password', static function () use ($verify, $credentials, $otherCode) {
        authRejected(static function () use ($verify, $credentials, $otherCode) { $verify($credentials + ['code' => $otherCode]); });
    });
    authCheck('own_code_with_wrong_password_rejected', static function () use ($verify, $credentials, $ownCode) {
        $bad = $credentials + ['code' => $ownCode]; $bad['password'] = 'private-wrong-password';
        authRejected(static function () use ($verify, $bad) { $verify($bad); });
    });
    $jwt = null;
    authCheck('own_code_verifies_and_returns_jwt', static function () use ($verify, $credentials, $ownCode, &$jwt) {
        $body = $verify($credentials + ['code' => $ownCode])->getData(true);
        authAssert(!empty($body['token'])); $jwt = $body['token'];
    });
    authCheck('used_code_cannot_be_reused', static function () use ($verify, $credentials, $ownCode) {
        authRejected(static function () use ($verify, $credentials, $ownCode) { $verify($credentials + ['code' => $ownCode]); });
    });
    authCheck('consumed_code_not_retained_in_private_inbox', static function () use ($capturePath) {
        $record = json_decode(Crypt::decryptString(file_get_contents($capturePath)), true);
        authAssert($record['code'] === null);
    });
    authCheck('protected_api_rejects_missing_token', static function () use ($app) {
        $app['auth']->forgetGuards();
        $request = Request::create('https://ts.workstaffcrm.ru/api/user', 'GET', [], [], [], ['HTTP_ACCEPT' => 'application/json']);
        $app->instance('request', $request);
        $app['tymon.jwt']->unsetToken()->setRequest($request);
        $response = $app->make(Illuminate\Contracts\Http\Kernel::class)->handle($request);
        $GLOBALS['auth_last_http_status'] = $response->getStatusCode();
        authAssert($response->getStatusCode() === 401);
    });
    authCheck('verified_jwt_accesses_real_protected_api', static function () use ($app, $jwt) {
        $app['auth']->forgetGuards();
        $request = Request::create('https://ts.workstaffcrm.ru/api/user', 'GET', [], [], [],
            ['HTTP_ACCEPT' => 'application/json', 'HTTP_AUTHORIZATION' => 'Bearer ' . $jwt]);
        $app->instance('request', $request);
        $app['tymon.jwt']->unsetToken()->setRequest($request);
        $response = $app->make(Illuminate\Contracts\Http\Kernel::class)->handle($request);
        $GLOBALS['auth_last_http_status'] = $response->getStatusCode();
        authAssert($response->getStatusCode() === 200);
    });
    while (DB::transactionLevel() > 0) { DB::rollBack(); }
    $after = privateRows();
    $snapshotFile = fopen(dirname($root) . '/auth-rows-' . $attempt . '-after.json', 'x');
    fwrite($snapshotFile, json_encode($after)); fclose($snapshotFile);
    authAssert($before === $after);
    echo json_encode(['passed' => true, 'checks' => $checks, 'private_tables_checked' => count($before),
        'all_private_original_rows_unchanged' => true, 'synthetic_accounts_rolled_back' => true,
        'captcha_process_double' => true, 'real_login_verify_jwt_used' => true,
        'live_database_accessed' => false, 'real_email_sent' => false, 'live_files_changed' => false]) . "\n";
} catch (Throwable $error) {
    if ($app) { try { while (DB::transactionLevel() > 0) { DB::rollBack(); } } catch (Throwable $ignored) {} }
    $safeAttempt = preg_replace('/[^0-9]/', '', (string) getenv('GPM_TS_AUTH_ATTEMPT'));
    file_put_contents(dirname($root) . '/auth-private-error-' . $safeAttempt . '.log', (string) $error);
    echo json_encode(['passed' => false, 'failed_check' => $current, 'checks_passed' => count($checks),
        'exception_type' => get_class($error), 'last_http_status' => $GLOBALS['auth_last_http_status'] ?? null,
        'private_details_withheld' => true, 'live_files_changed' => false]) . "\n";
    exit(1);
}

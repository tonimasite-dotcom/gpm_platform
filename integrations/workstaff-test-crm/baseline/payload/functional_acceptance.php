<?php
use App\Models\Order;
use App\Models\User;
use App\Services\Order\LogistEditAccess;
use App\Services\Order\OrderCalculation;
use Carbon\Carbon;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;

$checks = [];
$current = 'bootstrap';
$app = null;
$started = microtime(true);

function fixtureAssert(bool $condition): void
{
    if (!$condition) throw new RuntimeException('FUNCTIONAL_ASSERTION_FAILED');
}

function fixtureCheck(string $name, callable $action): void
{
    global $checks, $current;
    $current = $name;
    $action();
    fixtureAssert(DB::transactionLevel() >= 1);
    $checks[] = $name;
}

function fixtureRequest(string $method, array $data, ?User $actor = null): Request
{
    global $app;
    $request = Request::create('/api/private-functional-fixture', $method, $data, [], [],
        ['HTTP_ACCEPT' => 'application/json', 'REMOTE_ADDR' => '127.0.0.1']);
    $request->setLaravelSession($app['session']->driver());
    $app->instance('request', $request);
    $app['auth']->forgetGuards();
    if ($actor) $app['auth']->guard()->setUser($actor);
    $request->setUserResolver(static function () use ($actor) { return $actor; });
    return $request;
}

function fixtureRejected(int $status, callable $action): void
{
    try { $action(); }
    catch (Throwable $error) {
        if ($error instanceof Illuminate\Validation\ValidationException) {
            fixtureAssert($status === 422);
        } elseif ($error instanceof Illuminate\Database\Eloquent\ModelNotFoundException) {
            // The HTTP exception handler maps this controller-level failure to 404.
            fixtureAssert($status === 404);
        } else {
            fixtureAssert(method_exists($error, 'getStatusCode') && $error->getStatusCode() === $status);
        }
        return;
    }
    throw new RuntimeException('EXPECTED_REJECTION_NOT_RAISED');
}

function fixtureHttp(string $method, string $uri, array $data, ?User $actor = null)
{
    global $app;
    // Only maintenance is substituted, and only after the private DB/network
    // context is verified. Auth, active/branch, can and finance middleware run.
    $app->bind(App\Http\Middleware\PreventRequestsDuringMaintenance::class, static function () {
        return new class {
            public function handle($request, Closure $next) {
                App\Services\Release\GpmTsRehearsal::assertContext();
                return $next($request);
            }
        };
    });
    $request = Request::create('https://ts.workstaffcrm.ru/' . ltrim($uri, '/'), $method, $data,
        [], [], ['HTTP_ACCEPT' => 'application/json', 'REMOTE_ADDR' => '127.0.0.1']);
    $app->instance('request', $request);
    $app['auth']->forgetGuards();
    $jwt = $app['tymon.jwt'];
    $jwt->unsetToken()->setRequest($request);
    if ($actor) {
        $token = $jwt->fromUser($actor);
        $request->headers->set('Authorization', 'Bearer ' . $token);
        $jwt->unsetToken();
    }
    $response = $app->make(Illuminate\Contracts\Http\Kernel::class)->handle($request);
    $GLOBALS['fixture_last_http_status'] = $response->getStatusCode();
    if ($response->getStatusCode() >= 500) {
        file_put_contents('/root/gpm-ts-update/20261106-baseline-01/functional-http-private-response.json', $response->getContent());
    }
    return $response;
}

try {
    $app = require __DIR__ . '/private_runtime_bootstrap.php';
    fixtureAssert(DB::transactionLevel() === 0);
    // External CAPTCHA verification is an explicit test double in this process.
    // Credential checks, account state, JWT creation and controllers are real.
    $app['validator']->extend('captcha', static function ($attribute, $value) {
        return $value === 'private-synthetic-captcha';
    });
    DB::beginTransaction();
    $tag = bin2hex(random_bytes(8));
    $password = 'PrivateFixture-' . bin2hex(random_bytes(16));
    $actors = [];
    foreach (['logist', 'head', 'loader'] as $role) {
        $id = DB::table('users')->insertGetId(['surname' => 'Synthetic', 'first_name' => 'GpmFixture',
            'email' => 'gpm-' . $role . '-' . $tag . '@example.invalid', 'password' => Hash::make($password),
            'active' => 1, 'branch_id' => 0, 'created_at' => now(), 'updated_at' => now()]);
        $user = User::findOrFail($id);
        $user->assignRole(Spatie\Permission\Models\Role::findByName($role, 'api'));
        $actors[$role] = $user->fresh();
    }
    $logist = $actors['logist'];
    $head = $actors['head'];
    $loader = $actors['loader'];
    $branchId = DB::table('branches')->whereNotNull('city_id')->value('id');
    fixtureAssert($branchId !== null);
    $customerId = DB::table('customers')->insertGetId(['company_name' => 'Synthetic private fixture',
        'branch_id' => $branchId, 'created_at' => now(), 'updated_at' => now()]);
    $contactId = DB::table('contact_persons')->insertGetId(['customer_id' => $customerId,
        'name' => 'Synthetic contact', 'created_at' => now(), 'updated_at' => now()]);
    $orderId = DB::table('orders')->insertGetId(['status_id' => 0, 'work_type_id' => 1,
        'source_id' => array_key_first(Order::SOURCES), 'payment_type_id' => array_key_first(Order::PAYMENTTYPES),
        'workers_cost' => 600, 'customer_cost' => 1000, 'min_cost' => 4000, 'profit' => 1000,
        'branch_id' => $branchId, 'logist_id' => $logist->id, 'manager_id' => $head->id,
        'customer_id' => $customerId, 'contact_person_id' => $contactId,
        'address' => 'Synthetic private fixture', 'order_number' => 'PRIVATE-' . $tag,
        'created_at' => now(), 'updated_at' => now(), 'completion_date' => now()->addDay()]);
    fixtureCheck('new_order_defaults_to_calculation_v2', static function () use ($orderId) {
        fixtureAssert((int)DB::table('orders')->where('id', $orderId)->value('calculation_version') === 2);
    });
    fixtureCheck('standard_logist_and_head_permissions_resolve', static function () use ($logist, $head) {
        fixtureAssert($logist->can('read_logist_orders'));
        fixtureAssert($head->can(LogistEditAccess::PERMISSION));
        fixtureAssert(!$logist->can(LogistEditAccess::PERMISSION));
    });
    $credentials = ['login' => $logist->email, 'email' => $logist->email, 'password' => $password,
        'g-recaptcha-response' => 'private-synthetic-captcha'];
    fixtureCheck('active_synthetic_login_returns_jwt_without_mail_code', static function () use ($app, $credentials) {
        $request = fixtureRequest('POST', $credentials);
        $response = $app->make(App\Http\Controllers\Auth\LoginController::class)->login($request);
        $body = $response->getData(true);
        fixtureAssert($response->getStatusCode() === 200 && !empty($body['token']) && $body['token_type'] === 'bearer');
    });
    fixtureCheck('wrong_password_rejected', static function () use ($app, $credentials) {
        $bad = $credentials; $bad['password'] = 'wrong-synthetic-password';
        $request = fixtureRequest('POST', $bad);
        fixtureRejected(422, static function () use ($app, $request) {
            $app->make(App\Http\Controllers\Auth\LoginController::class)->login($request);
        });
    });
    foreach ([false, true] as $remember) {
        fixtureCheck('login_remember_' . ($remember ? 'true' : 'false') . '_returns_jwt', static function () use ($app, $credentials, $remember) {
            $request = fixtureRequest('POST', $credentials + ['remember' => $remember]);
            $response = $app->make(App\Http\Controllers\Auth\LoginController::class)->login($request);
            fixtureAssert($response->getStatusCode() === 200 && !empty($response->getData(true)['token']));
        });
    }
    fixtureCheck('missing_captcha_rejected', static function () use ($app, $credentials) {
        $bad = $credentials; unset($bad['g-recaptcha-response']);
        $request = fixtureRequest('POST', $bad);
        fixtureRejected(422, static function () use ($app, $request) {
            $app->make(App\Http\Controllers\Auth\LoginController::class)->login($request);
        });
    });
    fixtureCheck('inactive_synthetic_account_rejected', static function () use ($app, $loader, $password) {
        DB::table('users')->where('id', $loader->id)->update(['active' => 0]);
        $request = fixtureRequest('POST', ['login' => $loader->email, 'email' => $loader->email, 'password' => $password,
            'g-recaptcha-response' => 'private-synthetic-captcha']);
        fixtureRejected(422, static function () use ($app, $request) {
            $app->make(App\Http\Controllers\Auth\LoginController::class)->login($request);
        });
        DB::table('users')->where('id', $loader->id)->update(['active' => 1]);
    });
    $rate = static function (array $payload, User $actor) use ($app, $orderId) {
        $request = fixtureRequest('PATCH', $payload, $actor);
        return $app->make(App\Http\Controllers\Order\GpmWorkerRateController::class)->update($request, $orderId);
    };
    fixtureCheck('owned_order_rate_updates_and_records_history', static function () use ($rate, $logist, $orderId) {
        $response = $rate(['workers_cost' => 650, 'expected_workers_cost' => 600], $logist);
        fixtureAssert($response->getStatusCode() === 200);
        fixtureAssert((int)DB::table('orders')->where('id', $orderId)->value('workers_cost') === 650);
        fixtureAssert(Order::findOrFail($orderId)->histories()->exists());
        $history = Order::findOrFail($orderId)->histories()->latest('id')->first();
        fixtureAssert(count($history->properties) === 1);
    });
    fixtureCheck('stale_rate_rejected_409_and_newer_value_preserved', static function () use ($rate, $logist, $orderId) {
        fixtureRejected(409, static function () use ($rate, $logist) {
            $rate(['workers_cost' => 700, 'expected_workers_cost' => 600], $logist);
        });
        fixtureAssert((int)DB::table('orders')->where('id', $orderId)->value('workers_cost') === 650);
    });
    fixtureCheck('repeated_rate_request_does_not_duplicate_history', static function () use ($rate, $logist, $orderId) {
        $before = Order::findOrFail($orderId)->histories()->count();
        fixtureAssert($rate(['workers_cost' => 650, 'expected_workers_cost' => 600], $logist)->getStatusCode() === 200);
        fixtureAssert(Order::findOrFail($orderId)->histories()->count() === $before);
    });
    fixtureCheck('different_city_logist_cannot_edit_order', static function () use ($rate, $logist, $branchId) {
        $cityId = DB::table('branches')->where('id', $branchId)->value('city_id');
        $other = DB::table('branches')->whereNotNull('city_id')->where('city_id', '<>', $cityId)->value('id');
        fixtureAssert($other !== null);
        $restricted = $logist->fresh(); $restricted->branch_id = $other;
        fixtureRejected(404, static function () use ($rate, $restricted) {
            $rate(['workers_cost' => 700, 'expected_workers_cost' => 650], $restricted);
        });
    });
    fixtureCheck('same_city_owned_order_remains_accessible', static function () use ($rate, $logist, $branchId) {
        $restricted = $logist->fresh(); $restricted->branch_id = $branchId;
        fixtureAssert($rate(['workers_cost' => 650, 'expected_workers_cost' => 650], $restricted)->getStatusCode() === 200);
    });
    fixtureCheck('private_context_refuses_missing_rehearsal_marker', static function () use ($rate, $logist) {
        putenv('GPM_TS_REHEARSAL=0');
        try {
            fixtureRejected(404, static function () use ($rate, $logist) {
                $rate(['workers_cost' => 700, 'expected_workers_cost' => 650], $logist);
            });
        } finally { putenv('GPM_TS_REHEARSAL=1'); }
    });
    fixtureCheck('rate_payload_cannot_edit_address', static function () use ($rate, $logist) {
        fixtureRejected(422, static function () use ($rate, $logist) {
            $rate(['workers_cost' => 700, 'expected_workers_cost' => 650, 'address' => 'forbidden'], $logist);
        });
    });
    fixtureCheck('loader_cannot_use_rate_controller', static function () use ($rate, $loader) {
        fixtureRejected(403, static function () use ($rate, $loader) {
            $rate(['workers_cost' => 700, 'expected_workers_cost' => 650], $loader);
        });
    });
    fixtureCheck('foreign_logist_cannot_edit_order', static function () use ($rate, $logist, $orderId) {
        DB::table('orders')->where('id', $orderId)->update(['logist_id' => null]);
        fixtureRejected(404, static function () use ($rate, $logist) {
            $rate(['workers_cost' => 700, 'expected_workers_cost' => 650], $logist);
        });
        DB::table('orders')->where('id', $orderId)->update(['logist_id' => $logist->id]);
    });
    foreach (['address', 'customer_cost', 'min_cost'] as $field) {
        fixtureCheck('model_guard_rejects_logist_' . $field, static function () use ($logist, $orderId, $field) {
            fixtureRequest('PATCH', [], $logist);
            $before = DB::table('orders')->where('id', $orderId)->value($field);
            fixtureRejected(403, static function () use ($orderId, $field) {
                $order = Order::findOrFail($orderId);
                $order->setAttribute($field, $field === 'address' ? 'forbidden' : 9000);
                $order->save();
            });
            fixtureAssert(DB::table('orders')->where('id', $orderId)->value($field) === $before);
        });
    }
    fixtureCheck('head_can_change_open_order_address', static function () use ($head, $orderId) {
        fixtureRequest('PATCH', [], $head);
        $order = Order::findOrFail($orderId); $order->address = 'Synthetic allowed address'; $order->save();
        fixtureAssert(DB::table('orders')->where('id', $orderId)->value('address') === 'Synthetic allowed address');
    });
    foreach ([3, 4, 5] as $status) {
        fixtureCheck('closed_status_' . $status . '_blocks_rate', static function () use ($rate, $logist, $orderId, $status) {
            DB::table('orders')->where('id', $orderId)->update(['status_id' => $status]);
            fixtureRejected(409, static function () use ($rate, $logist) {
                $rate(['workers_cost' => 700, 'expected_workers_cost' => 650], $logist);
            });
        });
    }
    DB::table('orders')->where('id', $orderId)->update(['status_id' => 3]);
    $toggle = static function (User $actor, string $expected) use ($app, $orderId) {
        $request = fixtureRequest('GET', ['expected' => $expected], $actor);
        return $app->make(App\Http\Controllers\Order\LeaderOrderController::class)
            ->logistAccessToggle($request, Order::findOrFail($orderId));
    };
    $now = Carbon::now('UTC')->startOfSecond();
    Carbon::setTestNow($now);
    fixtureCheck('logist_cannot_grant_own_completed_order_access', static function () use ($toggle, $logist) {
        fixtureRejected(403, static function () use ($toggle, $logist) { $toggle($logist, 'closed'); });
    });
    fixtureCheck('head_opens_exactly_24_hours_without_changing_status_or_amounts', static function () use ($toggle, $head, $orderId, $now) {
        $before = DB::table('orders')->where('id', $orderId)->first(['status_id', 'min_cost', 'customer_cost', 'workers_cost']);
        $response = $toggle($head, 'closed'); $body = $response->getData(true);
        fixtureAssert($response->getStatusCode() === 200 && $body['access']['open']);
        fixtureAssert(Carbon::parse($body['access']['until'])->timestamp - $now->timestamp === 86400);
        fixtureAssert($before == DB::table('orders')->where('id', $orderId)->first(['status_id', 'min_cost', 'customer_cost', 'workers_cost']));
    });
    fixtureCheck('stale_access_toggle_returns_409_without_extra_history', static function () use ($toggle, $head, $orderId) {
        $before = Order::findOrFail($orderId)->histories()->count();
        $response = $toggle($head, 'closed');
        fixtureAssert($response->getStatusCode() === 409);
        fixtureAssert(Order::findOrFail($orderId)->histories()->count() === $before);
    });
    fixtureCheck('open_24_hour_window_does_not_unlock_client_price_or_address', static function () use ($logist, $orderId) {
        fixtureRequest('PATCH', [], $logist);
        foreach (['address', 'customer_cost'] as $field) {
            fixtureRejected(403, static function () use ($orderId, $field) {
                $order = Order::findOrFail($orderId);
                $order->setAttribute($field, $field === 'address' ? 'forbidden' : 9000);
                $order->save();
            });
        }
    });
    fixtureCheck('access_expires_at_server_deadline_without_cron', static function () use ($orderId, $now) {
        $order = Order::findOrFail($orderId);
        fixtureAssert(LogistEditAccess::state($order, $now->copy()->addHours(24)->subSecond())['open']);
        $state = LogistEditAccess::state($order, $now->copy()->addHours(24));
        fixtureAssert(!$state['open'] && $state['expired']);
    });
    fixtureCheck('legacy_access_flag_without_deadline_is_closed', static function () {
        $order = new Order(); $order->is_can_logist_edit = true; $order->logist_edit_until = null;
        $state = LogistEditAccess::state($order);
        fixtureAssert(!$state['open'] && $state['legacy']);
    });
    fixtureCheck('head_can_close_access_early', static function () use ($toggle, $head) {
        $response = $toggle($head, 'open'); $body = $response->getData(true);
        fixtureAssert($response->getStatusCode() === 200 && !$body['access']['open'] && $body['access']['until'] === null);
    });
    Carbon::setTestNow();
    $rateUri = 'api/logist_orders/' . $orderId . '/gpm_worker_rate';
    $accessUri = 'api/leader_orders/logist_access_toggle/' . $orderId;
    fixtureCheck('http_rate_route_requires_authentication', static function () use ($rateUri) {
        fixtureAssert(fixtureHttp('PATCH', $rateUri, ['workers_cost' => 700, 'expected_workers_cost' => 650])->getStatusCode() === 401);
    });
    fixtureCheck('http_rate_route_enforces_read_permission', static function () use ($rateUri, $loader) {
        fixtureAssert(fixtureHttp('PATCH', $rateUri, ['workers_cost' => 700, 'expected_workers_cost' => 650], $loader)->getStatusCode() === 403);
    });
    fixtureCheck('http_rate_route_updates_owned_order_through_middleware', static function () use ($rateUri, $logist, $orderId) {
        DB::table('orders')->where('id', $orderId)->update(['status_id' => 0]);
        fixtureAssert(fixtureHttp('PATCH', $rateUri, ['workers_cost' => 700, 'expected_workers_cost' => 650], $logist)->getStatusCode() === 200);
        fixtureAssert((int)DB::table('orders')->where('id', $orderId)->value('workers_cost') === 700);
    });
    fixtureCheck('http_rate_route_preserves_revision_conflict', static function () use ($rateUri, $logist) {
        fixtureAssert(fixtureHttp('PATCH', $rateUri, ['workers_cost' => 750, 'expected_workers_cost' => 650], $logist)->getStatusCode() === 409);
    });
    fixtureCheck('http_logist_cannot_grant_completed_order_access', static function () use ($accessUri, $logist, $orderId) {
        DB::table('orders')->where('id', $orderId)->update(['status_id' => 3]);
        fixtureAssert(fixtureHttp('GET', $accessUri, ['expected' => 'closed'], $logist)->getStatusCode() === 403);
    });
    fixtureCheck('http_head_access_toggle_checks_permission_and_stale_state', static function () use ($accessUri, $head) {
        fixtureAssert(fixtureHttp('GET', $accessUri, ['expected' => 'closed'], $head)->getStatusCode() === 200);
        fixtureAssert(fixtureHttp('GET', $accessUri, ['expected' => 'closed'], $head)->getStatusCode() === 409);
        fixtureAssert(fixtureHttp('GET', $accessUri, ['expected' => 'open'], $head)->getStatusCode() === 200);
    });
    fixtureCheck('v1_does_not_gain_v2_expense_rule', static function () {
        fixtureAssert(!OrderCalculation::pureExpense(1, 0, -200));
        fixtureAssert(OrderCalculation::pureExpense(2, 0, -200));
        fixtureAssert(!OrderCalculation::pureExpense(2, null, -200));
    });
    fixtureCheck('submitted_profit_uses_worker_and_transport_totals', static function () {
        fixtureAssert(OrderCalculation::submittedProfit(1000, [['pay' => 250.55], ['pay' => 100.45]],
            [['amount_to_be_issued' => 100]]) === 549.0);
    });
    fixtureCheck('v2_revenue_change_does_not_rewrite_accrual_rows', static function () use ($orderId, $loader) {
        DB::table('plannings')->insert(['order_id' => $orderId, 'user_id' => $loader->id,
            'day' => now()->toDateString(), 'pay' => '300', 'cost' => 300, 'created_at' => now(), 'updated_at' => now()]);
        $values = OrderCalculation::prepareRevenueChange(Order::findOrFail($orderId), ['min_cost' => 5000]);
        fixtureAssert($values['profit'] === 4700.0);
        fixtureAssert((float)DB::table('plannings')->where('order_id', $orderId)->sum('pay') === 300.0);
        $legacy = Order::findOrFail($orderId); $legacy->calculation_version = 1;
        fixtureAssert(OrderCalculation::prepareRevenueChange($legacy, ['min_cost' => 5000]) === ['min_cost' => 5000]);
    });
    while (DB::transactionLevel() > 0) DB::rollBack();
    fixtureAssert(!DB::table('orders')->where('id', $orderId)->exists());
    foreach ($actors as $actor) fixtureAssert(!DB::table('users')->where('id', $actor->id)->exists());
    $report = ['success' => true, 'scenarios_passed' => count($checks), 'scenarios' => $checks,
        'real_candidate_controllers_and_model_events_used' => true, 'synthetic_fixtures_only' => true,
        'all_fixture_transactions_rolled_back' => true, 'captcha_external_verification_stubbed' => true,
        'http_auth_permission_and_finance_middleware_tested' => true, 'private_maintenance_middleware_substituted' => true,
        'browser_acceptance_completed' => false, 'live_crm_changed' => false,
        'elapsed_seconds' => round(microtime(true) - $started, 3)];
    file_put_contents('/root/gpm-ts-update/20261106-baseline-01/functional-acceptance-20261109.json', json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
} catch (Throwable $error) {
    if (class_exists(Carbon::class, false)) Carbon::setTestNow();
    if ($app) while (DB::transactionLevel() > 0) DB::rollBack();
    file_put_contents('/root/gpm-ts-update/20261106-baseline-01/functional-private-error-20261109.log', (string)$error);
    $report = ['success' => false, 'failed_scenario' => $current, 'scenarios_passed' => count($checks),
        'exception_type' => get_class($error), 'raw_diagnostics_withheld' => true, 'live_crm_changed' => false];
    if ($error instanceof Illuminate\Validation\ValidationException) $report['validation_fields'] = array_keys($error->errors());
    if ($app) $report['auth_driver'] = config('auth.guards.' . config('auth.defaults.guard') . '.driver');
    if (isset($GLOBALS['fixture_last_http_status'])) $report['last_http_status'] = $GLOBALS['fixture_last_http_status'];
    file_put_contents('/root/gpm-ts-update/20261106-baseline-01/functional-acceptance-20261109.json', json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
    exit(1);
}

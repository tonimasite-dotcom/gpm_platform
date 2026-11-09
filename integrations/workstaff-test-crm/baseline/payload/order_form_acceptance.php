<?php
use App\Models\Order;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;

$checks = [];
$current = 'bootstrap';
$app = null;
$started = microtime(true);
$privateRoot = '/root/gpm-ts-update/20261106-baseline-01';
$legacyVariant = getenv('GPM_TS_ACCEPTANCE_VARIANT') === 'legacy-pre-boundary';
$reportName = $legacyVariant ? 'legacy-financial-acceptance-20261109.json' : 'order-form-acceptance-20261109.json';

function orderAssert($condition): void {
    if (!$condition) throw new RuntimeException('ORDER_FORM_ASSERTION_FAILED');
}
function orderCheck(string $name, callable $test): void {
    global $checks, $current;
    $current = $name;
    $test();
    orderAssert(DB::transactionLevel() === 1);
    $checks[] = $name;
}
function orderHttp(string $method, string $uri, array $data, ?User $actor = null) {
    global $app, $privateRoot;
    $request = Request::create('https://ts.workstaffcrm.ru/api/' . $uri, $method, $data,
        [], [], ['HTTP_ACCEPT' => 'application/json', 'REMOTE_ADDR' => '127.0.0.1']);
    $app->instance('request', $request);
    $app['auth']->forgetGuards();
    $jwt = $app['tymon.jwt'];
    $jwt->unsetToken()->setRequest($request);
    if ($actor) {
        $request->headers->set('Authorization', 'Bearer ' . $jwt->fromUser($actor));
        $jwt->unsetToken();
    }
    $response = $app->make(Illuminate\Contracts\Http\Kernel::class)->handle($request);
    $GLOBALS['last_order_http_status'] = $response->getStatusCode();
    unset($GLOBALS['last_order_validation_fields']);
    // Bodies and exception details never leave the private directory.
    file_put_contents($privateRoot . '/order-form-private-response.json', $response->getContent());
    if ($response->getStatusCode() === 422) {
        $body = json_decode($response->getContent(), true);
        $GLOBALS['last_order_validation_fields'] = array_keys($body['errors'] ?? []);
    }
    return $response;
}

try {
    $app = require __DIR__ . '/private_runtime_bootstrap.php';
    orderAssert(DB::transactionLevel() === 0);
    $app->bind(App\Http\Middleware\PreventRequestsDuringMaintenance::class, static function () {
        return new class {
            public function handle($request, Closure $next) {
                App\Services\Release\GpmTsRehearsal::assertContext();
                return $next($request);
            }
        };
    });
    // Explicit process-only geocoder double. No provider keys or external calls.
    YaGeo::swap(new class {
        public function setQuery($query) { return $this; }
        public function load() { return $this; }
        public function getResponse() { return null; }
    });
    DB::beginTransaction();
    $tag = bin2hex(random_bytes(8));
    $actors = [];
    foreach (['head', 'manager', 'logist', 'loader'] as $role) {
        $id = DB::table('users')->insertGetId(['surname' => 'Synthetic', 'first_name' => 'OrderForm',
            'email' => 'private-form-' . $role . '-' . $tag . '@example.invalid',
            'password' => Hash::make(bin2hex(random_bytes(24))), 'active' => 1, 'branch_id' => 0,
            'created_at' => now(), 'updated_at' => now()]);
        $actor = User::findOrFail($id);
        $actor->assignRole(Spatie\Permission\Models\Role::findByName($role, 'api'));
        $actors[$role] = $actor->fresh();
    }
    $branchId = DB::table('branches')->whereNotNull('city_id')->whereNull('deleted_at')->value('id');
    $workTypeId = DB::table('work_types')->value('id');
    orderAssert($branchId && $workTypeId);
    $customerId = DB::table('customers')->insertGetId(['company_name' => 'Synthetic form ' . $tag,
        'branch_id' => $branchId, 'created_at' => now(), 'updated_at' => now()]);
    $contactId = DB::table('contact_persons')->insertGetId(['customer_id' => $customerId,
        'name' => 'Synthetic contact', 'created_at' => now(), 'updated_at' => now()]);
    $foreignCustomerId = DB::table('customers')->insertGetId(['company_name' => 'Synthetic foreign ' . $tag,
        'branch_id' => $branchId, 'created_at' => now(), 'updated_at' => now()]);
    $detail = ['contact_person' => $contactId, 'contact_name' => 'Synthetic contact',
        'contact_phone' => '+70000000000', 'completion_date' => now()->addDays(2)->toDateString(),
        'completion_time' => '12:30', 'work_type' => $workTypeId, 'address' => 'Synthetic private form ' . $tag,
        'loader_count_checkbox' => 1, 'loader_count' => 2, 'max_loader_count' => 2,
        'transport_count_checkbox' => 0, 'customer_cost' => 1000, 'workers_cost' => 600,
        'brigadier_cost' => 600, 'min_cost' => 4000, 'min_time' => 2,
        'logist' => (string)$actors['logist']->id, 'send_sms' => '0'];
    $payload = ['source' => array_key_first(Order::SOURCES), 'status' => 0,
        'payment_type_id' => array_key_first(Order::PAYMENTTYPES), 'branch_id' => $branchId,
        'customer_id' => $customerId, 'details' => [$detail]];
    $baseCount = DB::table('orders')->count();
    if (!$legacyVariant) {
    foreach (['head' => 'leader_orders', 'manager' => 'manager_orders'] as $role => $route) {
        orderCheck($role . '_creation_requires_auth', static function () use ($route, $payload) {
            orderAssert(orderHttp('POST', $route, $payload)->getStatusCode() === 401);
        });
        orderCheck($role . '_creation_rejects_loader_without_existing_permission', static function () use ($route, $payload, $actors) {
            $status = orderHttp('POST', $route, $payload, $actors['loader'])->getStatusCode();
            orderAssert($status === 403);
        });
        foreach (['branch_id', 'contact_person', 'customer_cost', 'foreign_contact'] as $invalid) {
            orderCheck($role . '_validation_' . $invalid, static function () use ($invalid, $route, $payload, $actors, $role, $foreignCustomerId) {
                $bad = $payload;
                if ($invalid === 'branch_id') $bad['branch_id'] = 0;
                elseif ($invalid === 'foreign_contact') $bad['customer_id'] = $foreignCustomerId;
                else unset($bad['details'][0][$invalid]);
                $before = DB::table('orders')->count();
                orderAssert(orderHttp('POST', $route, $bad, $actors[$role])->getStatusCode() === 422);
                orderAssert(DB::table('orders')->count() === $before);
            });
        }
        $id = null;
        orderCheck($role . '_creates_order_via_real_validation_and_controller', static function () use ($route, $payload, $actors, $role, $customerId, &$id) {
            $before = DB::table('orders')->where('customer_id', $customerId)->count();
            orderAssert(orderHttp('POST', $route, $payload, $actors[$role])->getStatusCode() === 200);
            orderAssert(DB::table('orders')->where('customer_id', $customerId)->count() === $before + 1);
            $order = Order::where('customer_id', $customerId)->latest('id')->firstOrFail();
            $id = $order->id;
            orderAssert((int)$order->calculation_version === 2 && (int)$order->manager_id === $actors[$role]->id);
            orderAssert((float)$order->min_cost === 4000.0 && (float)$order->customer_cost === 1000.0);
            orderAssert($order->histories()->count() === 1);
        });
        orderCheck($role . '_edits_open_order_and_records_history', static function () use ($route, $payload, $actors, $role, &$id) {
            $edit = $payload;
            $edit['details'][0]['address'] .= ' edited';
            $edit['details'][0]['min_cost'] = 5000;
            $before = Order::findOrFail($id)->histories()->count();
            orderAssert(orderHttp('PUT', $route . '/' . $id, $edit, $actors[$role])->getStatusCode() === 200);
            $order = Order::findOrFail($id);
            orderAssert($order->address === $edit['details'][0]['address'] && (float)$order->min_cost === 5000.0);
            orderAssert($order->histories()->count() === $before + 1);
        });
        orderCheck($role . '_update_rejects_loader_without_existing_permission', static function () use ($route, $payload, $actors, &$id) {
            $edit = $payload; $edit['details'][0]['address'] .= ' loader probe';
            $before = DB::table('orders')->where('id', $id)->first();
            $status = orderHttp('PUT', $route . '/' . $id, $edit, $actors['loader'])->getStatusCode();
            orderAssert($status === 403);
            orderAssert($before == DB::table('orders')->where('id', $id)->first());
        });
        if ($role === 'head') {
            orderCheck('manager_cannot_use_leader_create_or_update_permissions', static function () use ($route, $payload, $actors, &$id) {
                orderAssert(orderHttp('POST', $route, $payload, $actors['manager'])->getStatusCode() === 403);
                orderAssert(orderHttp('PUT', $route . '/' . $id, $payload, $actors['manager'])->getStatusCode() === 403);
            });
        } else {
            orderCheck('logist_existing_manager_permission_does_not_unlock_client_price', static function () use ($route, $payload, $actors, &$id) {
                $before = DB::table('orders')->where('id', $id)->first();
                $edit = $payload;
                $edit['details'][0]['address'] = $before->address;
                $edit['details'][0]['min_cost'] = 6000;
                orderAssert(orderHttp('PUT', $route . '/' . $id, $edit, $actors['logist'])->getStatusCode() === 403);
                orderAssert($before == DB::table('orders')->where('id', $id)->first());
            });
        }
        orderCheck($role . '_completed_order_rejects_address_and_status_edit', static function () use ($route, $payload, $actors, $role, &$id) {
            DB::table('orders')->where('id', $id)->update(['status_id' => 3]);
            $before = DB::table('orders')->where('id', $id)->first();
            $edit = $payload;
            $edit['details'][0]['address'] = 'Synthetic prohibited completed edit';
            orderAssert(orderHttp('PUT', $route . '/' . $id, $edit, $actors[$role])->getStatusCode() === 422);
            orderAssert($before == DB::table('orders')->where('id', $id)->first());
        });
    }
    orderCheck('multiple_details_create_distinct_order_numbers', static function () use ($payload, $actors, $customerId) {
        $batch = $payload;
        $batch['details'][] = $batch['details'][0];
        $before = DB::table('orders')->where('customer_id', $customerId)->count();
        orderAssert(orderHttp('POST', 'leader_orders', $batch, $actors['head'])->getStatusCode() === 200);
        $orders = DB::table('orders')->where('customer_id', $customerId)->latest('id')->limit(2)->get();
        orderAssert(DB::table('orders')->where('customer_id', $customerId)->count() === $before + 2);
        orderAssert($orders[0]->order_number !== $orders[1]->order_number);
    });
    }
    $legacyId = null;
    if ($legacyVariant) {
        $boundary = App\Services\Order\WorkerCalculationActivation::boundary();
        $gaps = DB::select('SELECT o.id + 1 AS candidate FROM orders o LEFT JOIN orders n ON n.id=o.id+1
            WHERE n.id IS NULL AND o.id+1 <= ? ORDER BY o.id LIMIT 1000', [$boundary]);
        $firstId = (int)DB::table('orders')->min('id');
        $candidateIds = array_fill_keys(array_map(static function ($gap) { return (int)$gap->candidate; }, $gaps), true);
        if ($firstId > 1) foreach (range(1, min(10000, $firstId - 1, $boundary)) as $available) {
            $candidateIds[$available] = true;
        }
        // A removed order may still have orphaned references. Do not reuse such an ID.
        $references = DB::select("SELECT TABLE_NAME AS t FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND COLUMN_NAME='order_id'");
        foreach ($references as $reference) {
            orderAssert(preg_match('/^[a-zA-Z0-9_]+$/D', $reference->t) === 1);
            foreach (array_chunk(array_keys($candidateIds), 1000) as $batch) {
                foreach (DB::table($reference->t)->whereIn('order_id', $batch)->distinct()->pluck('order_id') as $used) {
                    unset($candidateIds[(int)$used]);
                }
            }
        }
        if ($candidateIds) $legacyId = (int)array_key_first($candidateIds);
        orderAssert($legacyId !== null && $legacyId > 0 && $legacyId <= $boundary);
    }
    foreach ($legacyVariant ? [1] : [1, 2] as $version) {
        // Financial fixtures are synthetic; the real completion HTTP route performs all writes.
        $nds = (float)DB::table('branches')->where('id', $branchId)->value('nds');
        $divisor = $nds > 0 ? (100 + $nds) / 100 : 1;
        $fixture = ['status_id' => 2, 'calculation_version' => $version,
            'work_type_id' => $workTypeId, 'source_id' => array_key_first(Order::SOURCES),
            'payment_type_id' => Order::NON_CASH_PAYMENT, 'workers_cost' => 600, 'brigadier_cost' => 600,
            'customer_cost' => 1000, 'min_cost' => 4000, 'min_time' => 2, 'profit' => 2800,
            'customer_cost_nds' => round(1000/$divisor, 2), 'min_cost_nds' => round(4000/$divisor, 2),
            'profit_nds' => round(4000/$divisor, 2) - 1200,
            'branch_id' => $branchId, 'logist_id' => $actors['logist']->id, 'manager_id' => $actors['head']->id,
            'customer_id' => $customerId, 'contact_person_id' => $contactId, 'loader_count' => 1,
            'max_loader_count' => 1, 'address' => 'Synthetic financial form ' . $tag,
            'order_number' => 'PRIVATE-FIN-' . $version . '-' . $tag, 'completion_date' => now(),
            'created_at' => now(), 'updated_at' => now()];
        if ($legacyVariant) $fixture['id'] = $legacyId;
        $id = DB::table('orders')->insertGetId($fixture);
        DB::table('order_user')->insert(['order_id' => $id, 'user_id' => $actors['loader']->id, 'brigadier' => 0]);
        orderAssert((new App\Services\Order\WorkerCalculationState(Order::findOrFail($id)))->enabled() === !$legacyVariant);
        $calculation = static function (int $status, float $pay = 1200) use ($id, $actors) {
            $order = Order::findOrFail($id);
            $state = new App\Services\Order\WorkerCalculationState($order);
            $intent = $state->state($actors['loader']->id);
            $request = ['order_id' => $id, 'expected_status_id' => $status, 'sum' => 4000,
                'min_cost' => 4000, 'profit' => 4000 - $pay, 'min_time' => 2,
                'car_total_hours' => '00:00', 'loader_total_hours' => '02:00', 'coefficient' => 1,
                'total_add_cost' => null, 'items' => [['id' => $actors['loader']->id,
                    'pay' => $pay, 'amount_to_be_issued' => $pay, 'prize' => 0, 'penalty' => 0,
                    'rate' => 600, 'working_time' => ['working_time_from' => '10:00', 'working_time_to' => '12:00'],
                    'calculation' => ['mode' => $pay === 1200.0 ? 'auto' : 'manual',
                        'token' => $intent['token'] ?? null, 'client_minimum' => true]]]];
            if (!$state->enabled()) unset($request['items'][0]['calculation']);
            return $request;
        };
        $route = 'logist_orders/change_status_to_done';
        orderCheck('v' . $version . '_completion_rejects_old_form_without_status', static function () use ($route, $calculation, $actors) {
            $bad = $calculation(2); unset($bad['expected_status_id']);
            orderAssert(orderHttp('POST', $route, $bad, $actors['logist'])->getStatusCode() === 422);
        });
        if (!$legacyVariant) orderCheck('v' . $version . '_completion_rejects_stale_calculation_token', static function () use ($route, $calculation, $actors, $id) {
            $bad = $calculation(2); $bad['items'][0]['calculation']['token'] = str_repeat('0', 64);
            orderAssert(orderHttp('POST', $route, $bad, $actors['logist'])->getStatusCode() === 422);
            orderAssert((int)DB::table('orders')->where('id', $id)->value('status_id') === 2);
        });
        if ($version === 1) {
            orderCheck('v1_completion_rejects_forged_profit', static function () use ($route, $calculation, $actors, $id) {
                $bad = $calculation(2); $bad['profit'] = 999999;
                orderAssert(orderHttp('POST', $route, $bad, $actors['logist'])->getStatusCode() === 422);
                orderAssert(!DB::table('plannings')->where('order_id', $id)->exists());
            });
        }
        orderCheck('v' . $version . '_completion_saves_exact_accrual_profit_and_report', static function () use ($route, $calculation, $actors, $id, $version) {
            $request = $calculation(2);
            if ($version === 2) $request['profit'] = 999999;
            orderAssert(orderHttp('POST', $route, $request, $actors['logist'])->getStatusCode() === 200);
            $order = Order::findOrFail($id);
            orderAssert((int)$order->status_id === 3 && (float)$order->profit === 2800.0);
            $plans = DB::table('plannings')->where('order_id', $id);
            orderAssert($plans->count() === 1 && (float)$plans->sum('pay') === 1200.0);
            orderAssert(DB::table('report_cards')->whereIn('plannings_id', $plans->pluck('id'))->count() === 1);
        });
        orderCheck('v' . $version . '_completion_stale_status_cannot_become_correction', static function () use ($route, $calculation, $actors, $id) {
            $before = DB::table('plannings')->where('order_id', $id)->count();
            orderAssert(orderHttp('POST', $route, $calculation(2), $actors['logist'])->getStatusCode() === 422);
            orderAssert(DB::table('plannings')->where('order_id', $id)->count() === $before);
        });
        orderCheck('v' . $version . '_correction_requires_reason_before_money_changes', static function () use ($route, $calculation, $actors, $id) {
            orderAssert(orderHttp('POST', $route, $calculation(3, 1300), $actors['logist'])->getStatusCode() === 422);
            orderAssert((float)DB::table('plannings')->where('order_id', $id)->sum('pay') === 1200.0);
        });
        orderCheck('v' . $version . '_correction_appends_delta_and_repeat_does_not_duplicate', static function () use ($route, $calculation, $actors, $id) {
            $request = $calculation(3, 1300); $request['comment'] = 'Synthetic correction reason';
            orderAssert(orderHttp('POST', $route, $request, $actors['logist'])->getStatusCode() === 200);
            $plans = DB::table('plannings')->where('order_id', $id);
            orderAssert($plans->count() === 2 && (float)$plans->sum('pay') === 1300.0);
            orderAssert((float)Order::findOrFail($id)->profit === 2700.0);
            $repeat = $calculation(3, 1300); $repeat['comment'] = 'Synthetic unchanged repeat';
            orderAssert(orderHttp('POST', $route, $repeat, $actors['logist'])->getStatusCode() === 200);
            orderAssert(DB::table('plannings')->where('order_id', $id)->count() === 2);
        });
        orderCheck('v' . $version . '_paid_worker_cannot_be_repriced_by_logist', static function () use ($route, $calculation, $actors, $id) {
            $planIds = DB::table('plannings')->where('order_id', $id)->pluck('id');
            DB::table('report_cards')->whereIn('plannings_id', $planIds)->update(['issued' => 1]);
            $request = $calculation(3, 1400); $request['comment'] = 'Synthetic forbidden paid edit';
            orderAssert(orderHttp('POST', $route, $request, $actors['logist'])->getStatusCode() === 422);
            orderAssert((float)DB::table('plannings')->where('order_id', $id)->sum('pay') === 1300.0);
        });
        orderCheck('v' . $version . '_head_correction_preserves_paid_rows_and_appends_delta', static function () use ($calculation, $actors, $id) {
            $before = DB::table('plannings')->where('order_id', $id)->orderBy('id')->get()->all();
            $paid = DB::table('report_cards')->whereIn('plannings_id', array_column($before, 'id'))->orderBy('id')->get()->all();
            $request = $calculation(3, 1400); $request['comment'] = 'Synthetic leader correction';
            orderAssert(orderHttp('POST', 'leader_orders/correct_completed_sums', $request, $actors['head'])->getStatusCode() === 200);
            orderAssert((float)DB::table('plannings')->where('order_id', $id)->sum('pay') === 1400.0);
            orderAssert($before == DB::table('plannings')->whereIn('id', array_column($before, 'id'))->orderBy('id')->get()->all());
            orderAssert($paid == DB::table('report_cards')->whereIn('id', array_column($paid, 'id'))->orderBy('id')->get()->all());
        });
        orderCheck('v' . $version . '_document_blocks_client_total_correction_for_head', static function () use ($calculation, $actors, $id, $customerId, $branchId) {
            $docId = DB::table('document_links')->insertGetId(['name' => 'Synthetic lock document',
                'customer_id' => $customerId, 'branch_id' => $branchId, 'created_at' => now(), 'updated_at' => now()]);
            DB::table('document_link_services')->insert(['document_link_id' => $docId, 'order_id' => $id,
                'name' => 'Synthetic service', 'count' => 1, 'cost' => 4000, 'created_at' => now(), 'updated_at' => now()]);
            $before = DB::table('orders')->where('id', $id)->first();
            $request = $calculation(3, 1400); $request['comment'] = 'Synthetic forbidden document edit';
            $request['min_cost'] = 4500; $request['profit'] = 3100;
            orderAssert(orderHttp('POST', 'leader_orders/correct_completed_sums', $request, $actors['head'])->getStatusCode() === 422);
            orderAssert($before == DB::table('orders')->where('id', $id)->first());
        });
    }
    $permissions = DB::table('permissions')->where('guard_name', 'api')->where(function ($query) {
        $query->where('name', 'like', '%\_leader\_orders')->orWhere('name', 'like', '%\_manager\_orders');
    })->pluck('name')->all();
    $matrix = [];
    foreach ($actors as $role => $actor) foreach ($permissions as $permission) {
        $matrix[$role][$permission] = $actor->can($permission);
    }
    while (DB::transactionLevel() > 0) DB::rollBack();
    orderAssert(DB::table('orders')->count() === $baseCount);
    orderAssert(!DB::table('customers')->whereIn('id', [$customerId, $foreignCustomerId])->exists());
    foreach ($actors as $actor) orderAssert(!DB::table('users')->where('id', $actor->id)->exists());
    $report = ['success' => true, 'harness_completed' => true,
        'checks_completed' => count($checks), 'accepted_scenarios' => count($checks),
        'scenarios' => $checks, 'existing_permission_matrix' => $matrix,
        'order_form_acceptance_passed' => true, 'release_ready' => false,
        'legacy_pre_worker_boundary' => $legacyVariant,
        'real_http_form_validation_and_middleware' => true, 'geocoder_process_double' => true,
        'all_synthetic_transactions_rolled_back' => true, 'live_crm_changed' => false,
        'browser_acceptance_completed' => false, 'elapsed_seconds' => round(microtime(true)-$started, 3)];
    file_put_contents($privateRoot . '/' . $reportName, json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
} catch (Throwable $error) {
    if ($app) while (DB::transactionLevel() > 0) DB::rollBack();
    file_put_contents($privateRoot . '/order-form-private-error.log', (string)$error);
    $report = ['success' => false, 'failed_scenario' => $current, 'scenarios_passed' => count($checks),
        'exception_type' => get_class($error), 'raw_diagnostics_withheld' => true, 'live_crm_changed' => false];
    if (isset($GLOBALS['last_order_http_status'])) $report['last_http_status'] = $GLOBALS['last_order_http_status'];
    if (isset($GLOBALS['last_order_validation_fields'])) $report['validation_fields'] = $GLOBALS['last_order_validation_fields'];
    echo json_encode($report) . PHP_EOL;
    exit(1);
}

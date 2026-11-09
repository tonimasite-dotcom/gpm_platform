<?php
use App\Models\Order;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Http\Request;

$app = null;
$checks = [];
$knownIssues = [];
$current = 'bootstrap';
$work = '/root/gpm-ts-update/20261109-switch-01';
function switchAssert($value): void { if (!$value) throw new RuntimeException('SWITCH_SMOKE_ASSERTION_FAILED'); }
function switchCheck($name, $test): void {
    global $current, $checks;
    $current = $name; $test(); switchAssert(DB::transactionLevel() >= 1); $checks[] = $name;
}
function switchRequest($method, array $data, $actor = null): Request {
    global $app;
    $request = Request::create('/api/private-switch-smoke', $method, $data, [], [], ['HTTP_ACCEPT'=>'application/json']);
    $request->setLaravelSession($app['session']->driver());
    $app->instance('request', $request); $app['auth']->forgetGuards();
    if ($actor) $app['auth']->guard()->setUser($actor);
    $request->setUserResolver(static function () use ($actor) { return $actor; });
    return $request;
}
try {
    $app = require __DIR__ . '/private_runtime_bootstrap.php';
    $version = App\Services\Release\GpmTsSwitchContext::assertRuntime();
    switchAssert($version === getenv('GPM_SWITCH_EXPECT_VERSION'));
    $app['validator']->extend('captcha', static function ($attribute, $value) { return $value === 'private-captcha'; });
    DB::beginTransaction();
    $tag = bin2hex(random_bytes(8)); $password = bin2hex(random_bytes(24));
    $userId = DB::table('users')->insertGetId(['surname'=>'Synthetic', 'first_name'=>'SwitchSmoke',
        'email'=>'switch-'.$tag.'@example.invalid','password'=>Hash::make($password),'active'=>1,
        'branch_id'=>0,'created_at'=>now(),'updated_at'=>now()]);
    $actor = User::findOrFail($userId);
    $actor->assignRole(Spatie\Permission\Models\Role::findByName('logist','api'));
    $branchId = DB::table('branches')->whereNotNull('city_id')->value('id');
    $customerId = DB::table('customers')->insertGetId(['company_name'=>'Synthetic Switch '.$tag,
        'branch_id'=>$branchId,'created_at'=>now(),'updated_at'=>now()]);
    $contactId = DB::table('contact_persons')->insertGetId(['customer_id'=>$customerId,
        'name'=>'Synthetic Contact','created_at'=>now(),'updated_at'=>now()]);
    $id = DB::table('orders')->insertGetId(['status_id'=>0,'work_type_id'=>1,
        'source_id'=>array_key_first(Order::SOURCES),'payment_type_id'=>array_key_first(Order::PAYMENTTYPES),
        'workers_cost'=>600,'customer_cost'=>1000,'min_cost'=>4000,'profit'=>1000,'branch_id'=>$branchId,
        'customer_id'=>$customerId,'contact_person_id'=>$contactId,'logist_id'=>$actor->id,
        'address'=>'Synthetic private switch address','order_number'=>'SWITCH-'.$tag,
        'completion_date'=>now()->addDay(),'created_at'=>now(),'updated_at'=>now()]);
    switchCheck('real_jwt_login_with_remember_returns_token', static function () use ($app,$actor,$password) {
        $request=switchRequest('POST',['login'=>$actor->email,'email'=>$actor->email,'password'=>$password,
            'remember'=>true,'g-recaptcha-response'=>'private-captcha']);
        $response=$app->make(App\Http\Controllers\Auth\LoginController::class)->login($request);
        switchAssert($response->getStatusCode()===200 && !empty($response->getData(true)['token']));
    });
    switchCheck('ts_only_worker_rate_controller_active', static function () use ($app,$actor,$id,$version,&$knownIssues) {
        $request=switchRequest('PATCH',['workers_cost'=>650,'expected_workers_cost'=>600],$actor);
        try { $response=$app->make(App\Http\Controllers\Order\GpmWorkerRateController::class)->update($request,$id); }
        catch (ErrorException $error) {
            switchAssert($version==='old' && strpos($error->getMessage(),'status_id')!==false
                && basename($error->getFile())==='HistoryOrderService.php');
            switchAssert((float)DB::table('orders')->where('id',$id)->value('workers_cost')===600.0);
            $knownIssues[]='SAVED_OLD_RATE_HISTORY_STATUS_ID_ERROR';
            return;
        }
        switchAssert($version==='new');
        switchAssert($response->getStatusCode()===200);
        switchAssert((float)DB::table('orders')->where('id',$id)->value('workers_cost')===650.0);
    });
    switchCheck('stale_rate_preserves_current_value', static function () use ($app,$actor,$id,$version) {
        $request=switchRequest('PATCH',['workers_cost'=>700,'expected_workers_cost'=>$version==='old'?550:600],$actor);
        try { $app->make(App\Http\Controllers\Order\GpmWorkerRateController::class)->update($request,$id); }
        catch (Throwable $error) {
            switchAssert(method_exists($error,'getStatusCode') && $error->getStatusCode()===409);
            switchAssert((float)DB::table('orders')->where('id',$id)->value('workers_cost')===($version==='old'?600.0:650.0));
            return;
        }
        throw new RuntimeException('EXPECTED_STALE_RATE_REJECTION_MISSING');
    });
    switchCheck('ts_only_model_guard_rejects_logist_address', static function () use ($actor,$id) {
        switchRequest('PATCH',[],$actor);
        try { $order=Order::findOrFail($id);$order->address='Synthetic forbidden address';$order->save(); }
        catch (Throwable $error) {
            switchAssert(method_exists($error,'getStatusCode') && $error->getStatusCode()===403);
            switchAssert(DB::table('orders')->where('id',$id)->value('address')==='Synthetic private switch address');
            return;
        }
        throw new RuntimeException('EXPECTED_MODEL_GUARD_REJECTION_MISSING');
    });
    switchCheck('active_schema_matches_version', static function () use ($version) {
        $count=(int)DB::selectOne('SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')->n;
        switchAssert($count===($version==='old'?72:112));
    });
    while (DB::transactionLevel()>0) DB::rollBack();
    switchAssert(!DB::table('orders')->where('id',$id)->exists() && !DB::table('users')->where('id',$userId)->exists());
    echo json_encode(['success'=>true,'version'=>$version,'scenarios_passed'=>count($checks),'scenarios'=>$checks,
        'known_saved_old_issues'=>$knownIssues,'worker_rate_feature_accepted'=>$version==='new',
        'real_ts_only_context_active'=>true,'synthetic_transactions_rolled_back'=>true,'live_crm_changed'=>false]) . PHP_EOL;
} catch (Throwable $error) {
    if ($app) while (DB::transactionLevel()>0) DB::rollBack();
    file_put_contents($work.'/smoke-private-error.log',(string)$error);
    $result=['success'=>false,'failed_scenario'=>$current,'scenarios_passed'=>count($checks),
        'exception_type'=>get_class($error),'raw_details_withheld'=>true,'live_crm_changed'=>false];
    if ($error instanceof Illuminate\Validation\ValidationException) $result['validation_fields']=array_keys($error->errors());
    echo json_encode($result) . PHP_EOL;exit(1);
}

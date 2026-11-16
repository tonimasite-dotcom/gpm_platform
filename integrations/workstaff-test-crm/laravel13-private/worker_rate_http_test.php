<?php
// Actual HTTP kernel, JWT and permission middleware; synthetic records only.
require '/work/crm-private-01/vendor/autoload.php';
$app = require '/work/crm-private-01/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use App\Models\User;
use App\Models\Order;

$checks=[]; $stage='bootstrap'; $failure=null; $newStatePath=null;
function rateHttpAssert(bool $condition, string $label): void {
    if (!$condition) { throw new RuntimeException('HTTP_RATE_ASSERTION:'.$label); }
}
function rateHttp(string $method, string $uri, array $data=[], ?User $actor=null, array $headers=[]): array {
    global $app;
    $request=Illuminate\Http\Request::create('https://ts.workstaffcrm.ru/'.$uri, $method, $data, [], [],
        ['HTTP_ACCEPT'=>'application/json','REMOTE_ADDR'=>'127.0.0.1']);
    $app->instance('request',$request);
    $app['auth']->forgetGuards();
    $jwt=$app['tymon.jwt']; $jwt->unsetToken()->setRequest($request);
    if ($actor) {
        $token=$jwt->fromUser($actor);
        $request->headers->set('Authorization','Bearer '.$token);
        $jwt->unsetToken();
    }
    foreach($headers as $key=>$value) { $request->headers->set($key,$value); }
    $response=$app->make(Illuminate\Contracts\Http\Kernel::class)->handle($request);
    $body=json_decode($response->getContent(),true);
    return [$response->getStatusCode(),$body,$response];
}
function rateHttpStatus(string $name, int $expected, callable $action): array {
    global $checks,$stage;
    $stage=$name; $result=$action();
    if ($result[0]!==$expected) {
        // Error keys only. Never print JWTs, credentials or full response bodies.
        throw new RuntimeException('HTTP_STATUS:'.$name.':'.$result[0].':expected='.$expected
            .':type='.(is_array($result[1])?($result[1]['exception']??'json'):'non_json'));
    }
    rateHttpAssert(DB::transactionLevel()>=1,'outer_transaction_preserved');
    $checks[]=$name; return $result;
}
try {
    rateHttpAssert(App\Services\Release\GpmTsBotContext::matches(),'fixture_context');
    rateHttpAssert(config('database.connections.mysql.database')==='bot_fixture','fixture_database');
    Http::preventStrayRequests(); Http::fake(fn()=>throw new RuntimeException('UNEXPECTED_EXTERNAL_HTTP'));
    DB::beginTransaction();
    $city=DB::table('cities')->insertGetId(['name'=>'Synthetic route']);
    $otherCity=DB::table('cities')->insertGetId(['name'=>'Synthetic other route']);
    $branch=DB::table('branches')->insertGetId(['name'=>'Synthetic','timezone'=>'Europe/Moscow','nds'=>0,'city_id'=>$city]);
    $otherBranch=DB::table('branches')->insertGetId(['name'=>'Synthetic other','timezone'=>'Europe/Moscow','nds'=>0,'city_id'=>$otherCity]);
    $customer=DB::table('customers')->insertGetId(['company_name'=>'Synthetic','branch_id'=>$branch]);
    $contact=DB::table('contact_persons')->insertGetId(['customer_id'=>$customer,'name'=>'Synthetic']);
    $work=DB::table('work_types')->insertGetId(['name'=>'Synthetic']);
    $read=Spatie\Permission\Models\Permission::firstOrCreate(['name'=>'read_logist_orders','guard_name'=>'api']);
    $update=Spatie\Permission\Models\Permission::firstOrCreate(['name'=>'update_logist_orders','guard_name'=>'api']);
    $actors=[];
    foreach(['logist','head','loader','admin'] as $roleName) {
        $role=Spatie\Permission\Models\Role::firstOrCreate(['name'=>$roleName,'guard_name'=>'api']);
        if($roleName!=='loader') { $role->givePermissionTo($read); }
        if($roleName==='head') { $role->givePermissionTo($update); }
        $id=DB::table('users')->insertGetId(['surname'=>'Synthetic','first_name'=>'Route',
            'email'=>'synthetic-route-'.$roleName.'@example.invalid','password'=>password_hash('synthetic-only',PASSWORD_BCRYPT),
            'email_verified_at'=>now(),'active'=>1,'all_branches'=>1,'branch_id'=>$branch,'created_at'=>now(),'updated_at'=>now()]);
        $actor=User::findOrFail($id); $actor->assignRole($role); $actors[$roleName]=$actor->fresh();
    }
    app(Spatie\Permission\PermissionRegistrar::class)->forgetCachedPermissions();
    $actor=$actors['logist'];
    $legacyData=['order_number'=>'SYNTHETIC-HTTP-RATE-16','status_id'=>2,'payment_type_id'=>1,
        'source_id'=>1,'customer_id'=>$customer,'contact_person_id'=>$contact,'branch_id'=>$branch,'work_type_id'=>$work,
        'logist_id'=>$actor->id,'completion_date'=>'2026-11-16 15:00:00','loader_count'=>2,'duration'=>4,'min_time'=>4,
        'workers_cost'=>500,'customer_cost'=>900,'city'=>'Synthetic','address'=>'Synthetic address','street'=>'Synthetic street',
        'house'=>'1','coords'=>'[55.0,37.0]','additional'=>'[]','note'=>'Synthetic note','info'=>''];
    if(Illuminate\Support\Facades\Schema::hasColumn('orders','calculation_version')) { $legacyData['calculation_version']=1; }
    $order=DB::table('orders')->insertGetId($legacyData);
    $uri='api/logist_orders/'.$order.'/gpm_worker_rate';
    $payload=['workers_cost'=>600,'expected_workers_cost'=>500];
    rateHttpStatus('unauthenticated_rejected',401,fn()=>rateHttp('PATCH',$uri,$payload));
    rateHttpStatus('invalid_jwt_rejected',401,fn()=>rateHttp('PATCH',$uri,$payload,null,['Authorization'=>'Bearer synthetic.invalid.token']));
    rateHttpStatus('real_permission_missing_rejected',403,fn()=>rateHttp('PATCH',$uri,$payload,$actors['loader']));
    $result=rateHttpStatus('real_jwt_logist_updates_rate',200,fn()=>rateHttp('PATCH',$uri,$payload,$actor));
    rateHttpAssert(($result[1]['workers_cost']??null)===600,'rate_response');
    rateHttpAssert((int)DB::table('orders')->where('id',$order)->value('workers_cost')===600,'rate_saved');
    rateHttpAssert(Order::findOrFail($order)->histories()->count()===1,'one_history');
    rateHttpStatus('retry_is_idempotent',200,fn()=>rateHttp('PATCH',$uri,$payload,$actor));
    rateHttpAssert(Order::findOrFail($order)->histories()->count()===1,'no_duplicate_history');
    rateHttpStatus('stale_rate_conflict',409,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>700,'expected_workers_cost'=>500],$actor));
    rateHttpStatus('address_injection_rejected',422,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>700,'expected_workers_cost'=>600,'address'=>'Forbidden'],$actor));
    rateHttpStatus('client_price_injection_rejected',422,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>700,'expected_workers_cost'=>600,'customer_cost'=>1],$actor));
    rateHttpStatus('invalid_rate_rejected',422,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>0,'expected_workers_cost'=>600],$actor));
    foreach([3,4,5] as $status) {
        DB::table('orders')->where('id',$order)->update(['status_id'=>$status]);
        rateHttpStatus('closed_'.$status.'_rejected',409,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>700,'expected_workers_cost'=>600],$actor));
    }
    DB::table('orders')->where('id',$order)->update(['status_id'=>2,'logist_id'=>$actors['head']->id]);
    rateHttpStatus('other_owner_hidden',404,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>700,'expected_workers_cost'=>600],$actor));
    DB::table('orders')->where('id',$order)->update(['logist_id'=>$actor->id,'branch_id'=>$otherBranch]);
    rateHttpStatus('other_city_hidden',404,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>700,'expected_workers_cost'=>600],$actor));
    DB::table('orders')->where('id',$order)->update(['branch_id'=>$branch]);
    rateHttpStatus('head_with_actual_update_permission',200,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>700,'expected_workers_cost'=>600],$actors['head']));
    DB::table('users')->where('id',$actor->id)->update(['active'=>0]);
    rateHttpStatus('inactive_account_rejected',401,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>800,'expected_workers_cost'=>700],$actor));
    DB::table('users')->where('id',$actor->id)->update(['active'=>1]);
    rateHttpStatus('nonexistent_branch_header_rejected',401,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>800,'expected_workers_cost'=>700],$actor,['Branches'=>'999999999']));
    rateHttpStatus('valid_branch_header_accepted',200,fn()=>rateHttp('PATCH',$uri,['workers_cost'=>800,'expected_workers_cost'=>700],$actor,['Branches'=>(string)$branch]));
    rateHttpAssert(DB::table('orders')->where('id',$order)->value('address')==='Synthetic address','address_unchanged');
    rateHttpAssert((int)DB::table('orders')->where('id',$order)->value('customer_cost')===900,'client_rate_unchanged');
    rateHttpStatus('order_table_metadata',200,fn()=>rateHttp('GET','api/logist_orders',['table_meta'=>1],$actor));
    rateHttpStatus('order_edit_card',200,fn()=>rateHttp('GET','api/logist_orders/'.$order.'/edit',[],$actor));
    rateHttpStatus('order_datatable',200,fn()=>rateHttp('GET','api/logist_orders',[
        'datatable'=>1,'draw'=>1,'start'=>0,'length'=>10],$actor));
    rateHttpStatus('order_history',200,fn()=>rateHttp('GET','api/manager_orders/get_history/'.$order,[],$actor));
    // CAPTCHA network verification alone is a fixture. Controller, password, code and JWT are real.
    $app['validator']->extend('captcha',static fn($attribute,$value)=>$value==='synthetic-captcha-only');
    $smtpPort=(int)getenv('GPM_PRIVATE_SMTP_PORT');rateHttpAssert($smtpPort>0,'smtp_fixture_required');
    DB::table('branches')->where('id',$branch)->update(['host'=>'127.0.0.1','port'=>$smtpPort,
        'encryption'=>null,'mail'=>'sender@example.invalid','password_mail'=>'synthetic-not-real']);
    $credentials=['login'=>$actor->email,'email'=>$actor->email,'password'=>'synthetic-only',
        'remember'=>false,'g-recaptcha-response'=>'synthetic-captcha-only'];
    $bad=$credentials;$bad['password']='wrong-synthetic';
    rateHttpStatus('actual_login_wrong_password_rejected',422,fn()=>rateHttp('POST','api/login',$bad));
    $login=rateHttpStatus('actual_login_sends_email_code',200,fn()=>rateHttp('POST','api/login',$credentials));
    rateHttpAssert(($login[1]['success']??null)===true && !isset($login[1]['token']),'email_step_before_jwt');
    $code=(string)DB::table('users')->where('id',$actor->id)->value('remember_token');
    rateHttpAssert($code!=='','synthetic_code_generated');
    rateHttpStatus('actual_verify_wrong_code_rejected',422,fn()=>rateHttp('POST','api/verify',array_merge($credentials,['code'=>'wrong-synthetic-code'])));
    $verified=rateHttpStatus('actual_verify_returns_jwt',200,fn()=>rateHttp('POST','api/verify',array_merge($credentials,['code'=>$code])));
    rateHttpAssert(is_string($verified[1]['token']??null) && strlen($verified[1]['token'])>20,'issued_jwt');
    rateHttpStatus('issued_login_jwt_fetches_current_user',200,fn()=>rateHttp('GET','api/user',[],null,['Authorization'=>'Bearer '.$verified[1]['token']]));
    // No production API: intercept the exact publication endpoint in this isolated process.
    $baseUrl=rtrim((string)env('GPM_APP_API_URL'),'/');rateHttpAssert($baseUrl!=='','fixture_api_url');
    Http::swap(new Illuminate\Http\Client\Factory());
    Http::preventStrayRequests();
    Http::fake(static function($request) use($baseUrl) {
        rateHttpAssert($request->method()==='POST' && $request->url()===$baseUrl.'/app-api/orders','publication_target');
        $body=$request->data();
        rateHttpAssert(($body['source_instance']??null)==='https://ts.workstaffcrm.ru','publication_identity');
        rateHttpAssert((int)($body['order_data']['price_per_hour']??0)===800,'publication_rate');
        return Http::response(['order'=>['id'=>'synthetic-gpm-order','source_instance'=>'https://ts.workstaffcrm.ru']],200);
    });
    $statePath=storage_path('app/gpm-app-sync/'.$order.'.json');
    rateHttpAssert(!file_exists($statePath) && !file_exists($statePath.'.lock'),'new_private_sync_state_path');
    $newStatePath=$statePath;
    $published=rateHttpStatus('actual_publication_route_uses_fake_gpm_api',200,
        fn()=>rateHttp('PUT','api/manager_orders/publish_gpm_app/'.$order,['logist_phone'=>'+79990000000'],$actor));
    rateHttpAssert(($published[1]['success']??null)===true && Http::recorded()->count()===1,'one_publication');
    rateHttpAssert(is_file($statePath),'publication_state_saved');
    rateHttpStatus('admin_current_user_preserves_default_permissions',200,fn()=>rateHttp('GET','api/user',[],$actors['admin']));
    $detail=['contact_person'=>$contact,'contact_name'=>'Synthetic contact','contact_phone'=>'+70000000000',
        'completion_date'=>now()->addDays(2)->toDateString(),'completion_time'=>'12:30','work_type'=>$work,
        'address'=>'Synthetic new GPM test order','loader_count_checkbox'=>1,'loader_count'=>2,'max_loader_count'=>2,
        'transport_count_checkbox'=>0,'customer_cost'=>1000,'workers_cost'=>600,'brigadier_cost'=>600,
        'min_cost'=>4000,'min_time'=>2,'logist'=>(string)$actor->id,'send_sms'=>'0'];
    $create=['source'=>array_key_first(Order::SOURCES),'status'=>0,'payment_type_id'=>array_key_first(Order::PAYMENTTYPES),
        'branch_id'=>$branch,'customer_id'=>$customer,'details'=>[$detail]];
    rateHttpStatus('new_order_creation_requires_auth',401,fn()=>rateHttp('POST','api/manager_orders',$create));
    $beforeCreate=DB::table('orders')->count();
    rateHttpStatus('admin_creates_new_test_order_via_real_validation',200,fn()=>rateHttp('POST','api/manager_orders',$create,$actors['admin']));
    rateHttpAssert(DB::table('orders')->count()===$beforeCreate+1,'one_new_order_created');
    $newOrder=Order::where('customer_id',$customer)->where('id','<>',$order)->firstOrFail();
    rateHttpAssert((int)$newOrder->calculation_version===2,'new_order_current_calculation_version');
} catch(Throwable $error) {
    $failure=['stage'=>$stage,'exception'=>get_class($error),'message'=>$error->getMessage()];
} finally {
    while(DB::transactionLevel()>0) { DB::rollBack(); }
    if($newStatePath!==null) {
        foreach([$newStatePath,$newStatePath.'.lock'] as $path) {
            if(is_file($path) && !is_link($path)) { unlink($path); }
        }
    }
}
echo json_encode(['status'=>$failure?'FAILED':'PASS','scenarios'=>count($checks),'checks'=>$checks,
    'failure'=>$failure,'jwt_middleware_real'=>true,'permission_actor_substituted'=>false,
    'production_data_used'=>false,'external_http_used'=>false,'external_captcha_stubbed'=>true]);
exit($failure?1:0);

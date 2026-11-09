<?php
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Http\Request;

$app=null;$checks=[];$current='bootstrap';$otherCodeReturnedToken=false;
$work='/root/gpm-ts-update/20261109-switch-01';
class PrivateSwitchMailFixture {
    public static $calls=0;
    public function __construct($branch) {}
    public function sendVerifyMessage($user) { self::$calls++; return true; }
}
function mailAssert($v): void { if (!$v) throw new RuntimeException('EMAIL_CODE_ASSERTION_FAILED'); }
function mailCheck($name,$test): void { global $current,$checks;$current=$name;$test();$checks[]=$name; }
function mailRequest(array $data): Request {
    global $app;
    $r=Request::create('/api/private-email-code','POST',$data,[],[],['HTTP_ACCEPT'=>'application/json']);
    $r->setLaravelSession($app['session']->driver());$app->instance('request',$r);$app['auth']->forgetGuards();return $r;
}
function mailRejected($test): void {
    try {$test();}
    catch (Illuminate\Validation\ValidationException $e) { return; }
    throw new RuntimeException('EXPECTED_EMAIL_CODE_REJECTION_MISSING');
}
try {
    $app=require __DIR__.'/private_runtime_bootstrap.php';
    App\Services\Release\GpmTsSwitchContext::assertUpgrade();
    mailAssert(!class_exists(App\Services\WebKlexMailClient::class,false));
    mailAssert(class_alias(PrivateSwitchMailFixture::class,App\Services\WebKlexMailClient::class));
    $app['validator']->extend('captcha',static function ($attribute,$value) {return $value==='private-email-captcha';});
    DB::beginTransaction();$password=bin2hex(random_bytes(20));$tag=bin2hex(random_bytes(8));$actors=[];
    foreach (['owner','other'] as $kind) {
        $id=DB::table('users')->insertGetId(['surname'=>'Synthetic','first_name'=>'EmailCode',
            'email'=>'private-email-'.$kind.'-'.$tag.'@example.invalid','password'=>Hash::make($password),
            'active'=>1,'branch_id'=>0,'created_at'=>now(),'updated_at'=>now()]);
        $user=User::findOrFail($id);$user->assignRole(Spatie\Permission\Models\Role::findByName('logist','api'));$actors[$kind]=$user;
    }
    $owner=$actors['owner'];$other=$actors['other'];
    $credentials=['login'=>$owner->email,'email'=>$owner->email,'password'=>$password,'remember'=>true,
        'g-recaptcha-response'=>'private-email-captcha'];
    $login=static function ($data) use ($app) {$request=mailRequest($data);return $app->make(App\Http\Controllers\Auth\LoginController::class)->login($request);};
    $verify=static function ($data) use ($app) {$request=mailRequest($data);return $app->make(App\Http\Controllers\Auth\LoginController::class)->verify($request);};
    mailCheck('missing_setting_defaults_to_email_challenge',static function () use ($login,$credentials) {
        $auth=config('auth');unset($auth['login_email_code_enabled']);config(['auth'=>$auth]);
        $response=$login($credentials);$body=$response->getData(true);
        mailAssert($response->getStatusCode()===200 && ($body['success']??false)===true && !isset($body['token']));
        mailAssert(PrivateSwitchMailFixture::$calls===1);
    });
    mailCheck('enabled_setting_requires_email_code_and_returns_no_jwt',static function () use ($login,$credentials) {
        config(['auth.login_email_code_enabled'=>true]);$body=$login($credentials)->getData(true);
        mailAssert(($body['success']??false)===true && !isset($body['token']) && PrivateSwitchMailFixture::$calls===2);
    });
    $ownCode=DB::table('users')->where('id',$owner->id)->value('remember_token');
    mailAssert(is_string($ownCode) && strlen($ownCode)>0);
    mailCheck('wrong_password_does_not_send_email_or_issue_token',static function () use ($login,$credentials) {
        $bad=$credentials;$bad['password']='private-wrong-password';mailRejected(static function () use ($login,$bad) {$login($bad);});
        mailAssert(PrivateSwitchMailFixture::$calls===2);
    });
    mailCheck('nonexistent_email_code_is_rejected',static function () use ($verify,$credentials) {
        $bad=$credentials;$bad['code']='private-nonexistent-'.bin2hex(random_bytes(8));
        mailRejected(static function () use ($verify,$bad) {$verify($bad);});
    });
    $otherCode='private-other-'.bin2hex(random_bytes(8));DB::table('users')->where('id',$other->id)->update(['remember_token'=>$otherCode]);
    mailCheck('other_users_email_code_is_rejected',static function () use ($verify,$credentials,$otherCode,&$otherCodeReturnedToken) {
        $bad=$credentials;$bad['code']=$otherCode;
        mailRejected(static function () use ($verify,$bad,&$otherCodeReturnedToken) {
            $body=$verify($bad)->getData(true);$otherCodeReturnedToken=!empty($body['token']);
        });
    });
    mailCheck('own_email_code_verifies_and_returns_jwt',static function () use ($verify,$credentials,$ownCode) {
        $body=$verify($credentials+['code'=>$ownCode])->getData(true);mailAssert(!empty($body['token']));
    });
    mailCheck('used_email_code_cannot_be_reused',static function () use ($verify,$credentials,$ownCode) {
        mailRejected(static function () use ($verify,$credentials,$ownCode) {$verify($credentials+['code'=>$ownCode]);});
    });
    mailCheck('explicitly_disabled_setting_keeps_existing_no_code_login',static function () use ($login,$credentials) {
        config(['auth.login_email_code_enabled'=>false]);$body=$login($credentials)->getData(true);
        mailAssert(!empty($body['token']) && PrivateSwitchMailFixture::$calls===2);
    });
    while (DB::transactionLevel()>0) DB::rollBack();
    foreach ($actors as $actor) mailAssert(!DB::table('users')->where('id',$actor->id)->exists());
    echo json_encode(['success'=>true,'scenarios_passed'=>count($checks),'scenarios'=>$checks,
        'email_delivery_process_double'=>true,'real_login_and_verify_used'=>true,'all_synthetic_transactions_rolled_back'=>true,
        'real_email_sent'=>false,'live_crm_changed'=>false]).PHP_EOL;
} catch (Throwable $error) {
    if ($app) while (DB::transactionLevel()>0) DB::rollBack();
    file_put_contents($work.'/email-code-private-error.log',(string)$error);
    echo json_encode(['success'=>false,'failed_scenario'=>$current,'scenarios_passed'=>count($checks),
        'other_user_code_returned_jwt'=>$otherCodeReturnedToken,'exception_type'=>get_class($error),
        'raw_details_withheld'=>true,'live_crm_changed'=>false]).PHP_EOL;exit(1);
}

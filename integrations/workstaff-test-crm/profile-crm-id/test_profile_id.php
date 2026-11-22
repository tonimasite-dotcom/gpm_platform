<?php
namespace Illuminate\Validation {
    class ValidationException extends \RuntimeException {
        public $messages;
        public static function withMessages(array $messages) {$e=new self('validation');$e->messages=$messages;return $e;}
    }
}
namespace Illuminate\Auth\Access {class AuthorizationException extends \RuntimeException {}}
namespace Illuminate\Database\Migrations {class Migration {}}
namespace Illuminate\Support\Facades {
    class Http {
        public static $calls=[];public static $status=200;public static $body=['crm_logist_id'=>1,'account_id'=>'synthetic'];public static $throws=false;
        public static function timeout($seconds){return new Request;}
    }
    class Request {
        private $headers=[];
        public function acceptJson(){return $this;}
        public function withHeaders($headers){$this->headers=$headers;return $this;}
        public function get($url){Http::$calls[]=['url'=>$url,'headers'=>$this->headers];if(Http::$throws){throw new \RuntimeException('synthetic offline');}return new Response;}
    }
    class Response {
        public function status(){return Http::$status;}
        public function successful(){return Http::$status>=200&&Http::$status<300;}
        public function json($key){return Http::$body[$key]??null;}
    }
    class Schema {public static $exists=false;public static function hasColumn($table,$column){return self::$exists;}}
    class DB {public static $statements=[];public static function statement($sql){self::$statements[]=$sql;}}
}
namespace {
    use App\Services\Order\GpmAppProfileId as Id;
    use Illuminate\Support\Facades\Http;
    use Illuminate\Support\Facades\Schema;
    use Illuminate\Support\Facades\DB;
    $environment=['GPM_APP_API_URL'=>'https://app-api.gpmbot.ru','GPM_APP_API_TOKEN'=>'synthetic-token'];$instance='https://ts.workstaffcrm.ru';$checks=0;
    function env($key,$default=null){global $environment;return $environment[$key]??$default;}
    function config($key){global $instance;return $instance;}
    function check($value,$label){global $checks;if(!$value){throw new \RuntimeException('FAIL: '.$label);}++$checks;}
    function fails($class,$callback,$label){try{$callback();}catch(\Throwable $error){check($error instanceof $class,$label);return;}throw new \RuntimeException('Missing failure: '.$label);}
    class Actor {
        public $id;private $roles;private $permissions;
        public function __construct($id,$roles,$permissions=[]){$this->id=$id;$this->roles=$roles;$this->permissions=$permissions;}
        public function hasRole($role){return in_array($role,$this->roles,true);}
        public function hasAnyRole($roles){return count(array_intersect($roles,$this->roles))>0;}
        public function can($permission){return in_array($permission,$this->permissions,true);}
    }
    require __DIR__.'/GpmAppProfileId.php';
    $admin=new Actor(1,['admin']);$logist=new Actor(2,['logist']);$loader=new Actor(3,['loader']);$manager=new Actor(4,['manager'],['create_users','update_users']);
    foreach([1,'1','#1',' #1 '] as $value){check(Id::normalize($value)===1,'valid ID');}
    check(Id::normalize('#999999999')===999999999,'upper bound');
    foreach([null,'','  '] as $value){check(Id::normalize($value)===null,'clear optional ID');}
    foreach([true,false,0,-1,1.0,[],new \stdClass,'#0','#01','01','1e1','1.0','#1000000000'] as $value){fails(\Illuminate\Validation\ValidationException::class,function()use($value){Id::normalize($value);},'reject malformed ID');}
    foreach(['logist','admin'] as $role){check(Id::allowedRole($role),'eligible role');}
    foreach(['loader','manager','client',''] as $role){check(!Id::allowedRole($role),'other role');}
    $input=['email'=>'synthetic@example.invalid','phone'=>'+70000000000','password'=>'unchanged-synthetic','gpm_app_crm_id'=>'#1'];
    $saved=Id::prepare($input,'logist',null,$logist,$logist);check($saved['gpm_app_crm_id']===1,'self save');
    foreach(['email','phone','password'] as $key){check($saved[$key]===$input[$key],'preserve existing field');}
    check(count(Http::$calls)===1&&Http::$calls[0]['url']==='https://app-api.gpmbot.ru/app-api/integration/crm-logists/1','read-only GPM lookup only');
    check(Http::$calls[0]['headers']['X-GPM-App-Token']==='synthetic-token','authorized lookup');
    Http::$calls=[];Http::$throws=true;
    check(Id::prepare($input,'logist',1,$logist,$logist)['gpm_app_crm_id']===1&&!Http::$calls,'unchanged ID saves offline');
    $without=['email'=>'synthetic@example.invalid'];check(Id::prepare($without,'logist',1,$logist,$logist)===$without,'omitted ID untouched');
    check(Id::prepare(['gpm_app_crm_id'=>''],'logist',1,$logist,$logist)['gpm_app_crm_id']===null&&!Http::$calls,'clear offline');
    check(Id::prepare([],'loader',1,$admin,$logist)['gpm_app_crm_id']===null,'clear stale ID on role change');
    fails(\Illuminate\Validation\ValidationException::class,function()use($input,$admin,$loader){Id::prepare($input,'loader',null,$admin,$loader);},'forbidden target role');
    fails(\Illuminate\Auth\Access\AuthorizationException::class,function()use($input,$loader){Id::prepare($input,'logist',null,$loader,$loader);},'forged eligible role denied');
    fails(\Illuminate\Auth\Access\AuthorizationException::class,function()use($input,$logist,$admin){Id::prepare($input,'admin',null,$logist,$admin);},'cannot edit another user');
    fails(\Illuminate\Auth\Access\AuthorizationException::class,function()use($input,$logist){Id::prepare($input,'logist',null,$logist,null,true);},'cannot create staff without permission');
    Http::$throws=false;
    check(Id::prepare($input,'admin',null,$admin,$admin)['gpm_app_crm_id']===1,'admin profile');
    check(Id::prepare($input,'logist',null,$manager,$logist)['gpm_app_crm_id']===1,'existing staff edit permission');
    check(Id::prepare($input,'logist',null,$manager,null,true)['gpm_app_crm_id']===1,'existing staff create permission');
    foreach([404,500] as $status){Http::$status=$status;fails(\Illuminate\Validation\ValidationException::class,function()use($input,$logist){Id::prepare($input,'logist',null,$logist,$logist);},'invalid or unavailable recipient');}
    Http::$status=200;
    foreach([['crm_logist_id'=>2,'account_id'=>'synthetic'],['crm_logist_id'=>1,'account_id'=>''],['crm_logist_id'=>1,'account_id'=>null]] as $body){Http::$body=$body;fails(\Illuminate\Validation\ValidationException::class,function()use($input,$logist){Id::prepare($input,'logist',null,$logist,$logist);},'reject mismatched lookup');}
    $environment['GPM_APP_API_URL']='https://other.example.invalid';Http::$calls=[];fails(\Illuminate\Validation\ValidationException::class,function()use($input,$logist){Id::prepare($input,'logist',null,$logist,$logist);},'fixed server scope');check(!Http::$calls,'no request to other server');
    require __DIR__.'/2026_11_22_210000_add_gpm_app_crm_id_to_users.php';$migration=new \AddGpmAppCrmIdToUsers;$migration->up();
    check(count(DB::$statements)===1&&strpos(DB::$statements[0],'ADD COLUMN gpm_app_crm_id INT UNSIGNED NULL')!==false&&strpos(DB::$statements[0],'LOCK=NONE')!==false,'one nullable column only');
    fails(\RuntimeException::class,function()use($migration){$migration->down();},'code rollback retains field');
    Schema::$exists=true;fails(\RuntimeException::class,function()use($migration){$migration->up();},'existing column requires review');
    Schema::$exists=false;$instance='https://other.example.invalid';fails(\RuntimeException::class,function()use($migration){$migration->up();},'migration restricted to TS');
    echo 'Profile CRM ID tests PASS: '.$checks." checks\n";
}

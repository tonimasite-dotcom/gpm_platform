<?php
// Synthetic model/HTTP fixtures only. No Laravel boot or real network/database.
namespace {
    $GLOBALS['settings']=['GPM_APP_API_URL'=>'https://app-api.gpmbot.ru','GPM_APP_API_TOKEN'=>'synthetic-token','GPM_APP_CREW_LEADER_SYNC_ENABLED'=>true];
    $GLOBALS['url']='https://ts.workstaffcrm.ru';
    function config($key,$default=null) { return $key==='app.url' ? $GLOBALS['url'] : $default; }
    function env($key,$default=null) { return $GLOBALS['settings'][$key] ?? $default; }
    function check($value,$message) { if (!$value) throw new \RuntimeException($message); }
    class Workers {
        private $rows;
        public function __construct($rows) { $this->rows=$rows; }
        public function filter($fn) { return new self(array_values(array_filter($this->rows,$fn))); }
        public function values() { return $this; }
        public function count() { return count($this->rows); }
        public function first() { return $this->rows[0] ?? null; }
    }
}
namespace App\Models {
    class User {
        public $id=101,$phone='89990000001',$active=1,$gpm_app_crm_id=1,$pivot;
        public function __construct($brigadier=false) { $this->pivot=(object)['brigadier'=>$brigadier]; }
        public static function find($id) { return new self; }
        public function hasAnyRole($roles) { return true; }
        public function hasRole($role) { return $role==='loader'; }
    }
    class Order {
        public const STATUS_COMPLETED=3,STATUS_RETURNED=4,STATUS_DELETE=5;
        public $id=1,$order_number='SYNTHETIC/CREW',$status_id=0,$logist_id=1,$users;
        public static $row;
        public static function find($id) { return self::$row; }
        public function load($relation) { return $this; }
    }
}
namespace Illuminate\Support\Facades {
    class Log { public static $rows=[]; public static function warning($text,$context=[]) { self::$rows[]=[$text,$context]; } }
    class Http {
        public static $calls=[],$failure=false;
        public static function timeout($seconds) { return new self; }
        public function withOptions($options) { \check($options['allow_redirects']===false,'No redirect of integration credentials'); return $this; }
        public function acceptJson() { return $this; }
        public function asJson() { return $this; }
        public function withHeaders($headers) { \check($headers['X-GPM-App-Token']==='synthetic-token','Token is server side'); return $this; }
        public function post($url,$body) { self::$calls[]=[$url,$body]; return $this; }
        public function successful() { return !self::$failure; }
        public function status() { return self::$failure?503:200; }
        public function json($key) { return $key==='success' && !self::$failure; }
    }
}
namespace App\Services\Order { class GpmAppOrderSync { public const INSTANCE='https://ts.workstaffcrm.ru'; } }
namespace {
    require __DIR__.'/../app/Services/Order/GpmCrewLeaderSync.php';
    use App\Models\Order;
    use App\Models\User;
    use Illuminate\Support\Facades\Http;
    $service=new \App\Services\Order\GpmCrewLeaderSync;
    Order::$row=new Order;
    Order::$row->users=new Workers([new User(true),new User(false)]);
    check($service->sync(Order::$row),'Saved brigadier can be sent');
    $call=Http::$calls[0];
    check(strpos($call[0],'SYNTHETIC%2FCREW')!==false,'Encode slash order ID');
    check($call[1]===['operation'=>'leader','source_instance'=>'https://ts.workstaffcrm.ru','sender_crm_id'=>'#1','leader'=>['crm_worker_id'=>'101','phone'=>'89990000001']],'Minimal payload preserves CRM phone and saved owner');
    Order::$row->users=new Workers([new User(true),new User(true)]);
    check($service->sync(Order::$row) && end(Http::$calls)[1]['leader']===null,'Multiple brigadiers never guess');
    Order::$row->users=new Workers([new User(false),new User(false)]);
    check($service->sync(Order::$row) && end(Http::$calls)[1]['leader']===null,'Clear removed brigadier');
    Order::$row->users=new Workers([new User(false)]);
    check($service->sync(Order::$row) && end(Http::$calls)[1]['leader']['crm_worker_id']==='101','Solo worker');
    $before=count(Http::$calls);
    $GLOBALS['url']='https://workstaffcrm.ru';
    check(!$service->sync(Order::$row) && count(Http::$calls)===$before,'Main CRM has no calls');
    $GLOBALS['url']='https://ts.workstaffcrm.ru';
    $GLOBALS['settings']['GPM_APP_CREW_LEADER_SYNC_ENABLED']=false;
    check(!$service->sync(Order::$row) && count(Http::$calls)===$before,'Dedicated flag defaults off');
    $GLOBALS['settings']['GPM_APP_CREW_LEADER_SYNC_ENABLED']=true;
    Order::$row->status_id=Order::STATUS_COMPLETED;
    check($service->sync(Order::$row) && count(Http::$calls)===$before,'Terminal TS order preserved');
    Order::$row->status_id=0;
    Http::$failure=true;
    check(!$service->sync(Order::$row),'Transport failure is deferred');
    check(strpos(json_encode(\Illuminate\Support\Facades\Log::$rows),'89990000001')===false,'No phone in failure log');
    echo "Headless brigadier transport: PASS\n";
}

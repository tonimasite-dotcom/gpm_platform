<?php
namespace {
    $GLOBALS['scope'] = 'https://ts.workstaffcrm.ru';
    function config($key, $default = null) { return $key === 'app.url' ? $GLOBALS['scope'] : $default; }
    function env($key, $default = null) { return ['GPM_APP_API_URL'=>'https://app-api.gpmbot.ru','GPM_APP_API_TOKEN'=>'synthetic-token'][$key] ?? $default; }
    class SyntheticSender {
        public $gpm_app_crm_id; private $roles;
        public function __construct($id=1,$roles=['logist']){$this->gpm_app_crm_id=$id;$this->roles=$roles;}
        public function fresh(){return $GLOBALS['freshSender'];}
        public function hasAnyRole($roles){return count(array_intersect($this->roles,$roles))>0;}
    }
    class SyntheticAuth {public function user(){return $GLOBALS['sender'];}}
    function auth(){return new SyntheticAuth;}
    class OptionalValue { private $value; public function __construct($value){$this->value=$value;} public function __get($key){return $this->value->$key??null;} public function __call($key,$args){return $this->value?call_user_func_array([$this->value,$key],$args):null;} }
    function optional($value) { return new OptionalValue($value); }
    function check($value,$message){if(!$value){throw new \RuntimeException($message);}}
}
namespace App\Models {
    class Moment { public function toIso8601String(){return '2026-12-01T10:00:00+03:00';} }
    class Order {
        public const STATUS_JOB=2,STATUS_COMPLETED=3,STATUS_RETURNED=4,STATUS_DELETE=5;
        public $status_id=0;
        public $id=1,$order_number='TEST/26',$workers_cost=500,$customer_cost=1000,$city='Synthetic';
        public $address='Synthetic address',$street='Synthetic',$house='1',$coords=[0,0],$note='Synthetic',$info='',$additional=[];
        public $duration=4,$min_time=4,$loader_count=2,$contact_phone='+70000000000',$contact_email='synthetic@example.test';
        public $completion_date,$metroStation,$logistModel;
        public function __construct(){$this->completion_date=new Moment;$this->metroStation=(object)['name'=>'Test'];$this->logistModel=(object)['username'=>'synthetic'];}
        public function loadMissing($relations){return $this;}
    }
}
namespace App\Services\Order {
    class GpmAppOrderSync {
        public const INSTANCE='https://ts.workstaffcrm.ru';
        public static $linked=false,$syncCalls=0,$remembered=0,$prepared=0;
        public function enabled(){return true;}
        public function linked($order){return self::$linked;}
        public function prepareModeration($order){self::$prepared++;return ['revision'=>str_repeat('a',64),'fields'=>['price_per_hour'=>$order->workers_cost]];}
        public function syncOrder($order){self::$syncCalls++;return true;}
        public function crmFields($order){return ['price_per_hour'=>$order->workers_cost];}
        public function rememberPublication($order,$phone,$app,$fields){self::$remembered++;}
    }
}
namespace Illuminate\Support\Facades {
    class Log {public static $events=[];public static function warning($message,$context=[]){self::$events[]=[$message,$context];}}
    class Http {
        public static $calls=[],$lookupStatus=200,$linkedOwner='company-one',$postStatus=200,$moderationStatus=200,$linkedStatus='PROCESSED';
        public static function timeout($seconds){return new FakeRequest;}
    }
    class FakeResponse {
        private $status,$data;
        public function __construct($status,$data){$this->status=$status;$this->data=$data;}
        public function successful(){return $this->status>=200&&$this->status<300;}
        public function status(){return $this->status;}
        public function json($key=null){return $key===null?$this->data:($this->data[$key]??null);}
    }
    class FakeRequest {
        public function acceptJson(){return $this;}
        public function asJson(){return $this;}
        public function withHeaders($headers){\check($headers['X-GPM-App-Token']==='synthetic-token','Integration token required');return $this;}
        public function get($url){
            Http::$calls[]=['GET',$url];
            if(strpos($url,'/crm-logists/')!==false){return new FakeResponse(Http::$lookupStatus,['crm_logist_id'=>1,'account_id'=>'company-one']);}
            return new FakeResponse(200,['logist_account_id'=>Http::$linkedOwner,'status'=>Http::$linkedStatus]);
        }
        public function post($url,$payload){
            Http::$calls[]=['POST',$url,$payload];
            if(strpos($url,'/order-resubmission/')!==false){
                return new FakeResponse(Http::$moderationStatus,[
                    'success'=>true,'request_id'=>$payload['request_id'],
                    'logist_account_id'=>Http::$linkedOwner,'status'=>'NEW','already_applied'=>false,
                ]);
            }
            return new FakeResponse(Http::$postStatus,['order'=>['source_instance'=>'https://ts.workstaffcrm.ru','logist_account_id'=>'company-one'],'detail'=>'Arbitrary synthetic server details']);
        }
    }
}
namespace {
    require __DIR__.'/../app/Services/Order/GpmAppOrderPublisher.php';
    use App\Services\Order\GpmAppOrderPublisher;
    use App\Services\Order\GpmAppOrderSync;
    use Illuminate\Support\Facades\Http;
    function resetFixture(){Http::$calls=[];Http::$lookupStatus=200;Http::$linkedOwner='company-one';Http::$postStatus=200;Http::$moderationStatus=200;Http::$linkedStatus='PROCESSED';GpmAppOrderSync::$linked=false;GpmAppOrderSync::$syncCalls=0;GpmAppOrderSync::$prepared=0;$GLOBALS['scope']='https://ts.workstaffcrm.ru';$GLOBALS['sender']=new SyntheticSender;$GLOBALS['freshSender']=$GLOBALS['sender'];}
    resetFixture();$order=new App\Models\Order;$publisher=new GpmAppOrderPublisher;
    check($publisher->publish($order,'','#1'),'ID publication');
    $post=Http::$calls[count(Http::$calls)-1][2];
    check($post['logist_crm_id']===1&&$post['logist_phone']==='','Separate ID selector');
    check($post['order_data']['order_number']==='TEST/26'&&$order->order_number==='TEST/26','CRM order number unchanged');
    check($order->contact_phone==='+70000000000','CRM contact unchanged');
    foreach(['#0','bad','1.5','-1'] as $bad){resetFixture();check(!$publisher->publish($order,'',$bad),'Invalid ID blocked');check(count(Http::$calls)===0,'Invalid ID has no HTTP side effects');}
    resetFixture();Http::$lookupStatus=404;check(!$publisher->publish($order,'','#1'),'Unknown company ID');check(count(Http::$calls)===1,'Unknown ID never publishes');
    resetFixture();GpmAppOrderSync::$linked=true;Http::$linkedOwner='other-account';check(!$publisher->publish($order,'','#1'),'Linked owner protected');check($publisher->errorStatus()===409&&GpmAppOrderSync::$syncCalls===0,'No implicit retargeting');
    resetFixture();GpmAppOrderSync::$linked=true;check($publisher->publish($order,'','#1'),'Linked same-owner repeat');check(GpmAppOrderSync::$syncCalls===0&&GpmAppOrderSync::$prepared===1&&count(Http::$calls)===3,'Manual repeat stages a version without changing published data');
    resetFixture();check(!$publisher->publish($order,'+71111111111'),'Phone publication blocked');check(count(Http::$calls)===0,'Phone cannot bypass saved profile ID');
    foreach([null,'',0,true,'#1','bad'] as $missing){
        resetFixture();$GLOBALS['freshSender']=new SyntheticSender($missing);
        check(!$publisher->publish($order,'','#1'),'Request ID cannot replace missing saved profile ID');
        check($publisher->errorStatus()===422&&count(Http::$calls)===0&&GpmAppOrderSync::$syncCalls===0,'Missing saved ID has no integration side effects');
    }
    resetFixture();$GLOBALS['sender']=null;check(!$publisher->publish($order,'','#1')&&$publisher->errorStatus()===403&&count(Http::$calls)===0,'Unauthenticated publication blocked');
    resetFixture();$GLOBALS['freshSender']=null;check(!$publisher->publish($order,'','#1')&&$publisher->errorStatus()===403&&count(Http::$calls)===0,'Deleted sender blocked');
    resetFixture();$GLOBALS['freshSender']=new SyntheticSender(1,['loader']);check(!$publisher->publish($order,'','#1')&&$publisher->errorStatus()===403&&count(Http::$calls)===0,'Fresh role change cannot be bypassed');
    resetFixture();$GLOBALS['freshSender']=new SyntheticSender(2);check(!$publisher->publish($order,'','#1')&&count(Http::$calls)===0,'Stale session ID cannot override current database ID');
    resetFixture();check(!$publisher->publish($order,'','#2')&&count(Http::$calls)===0,'Manual recipient override blocked');
    resetFixture();$GLOBALS['sender']=new SyntheticSender(null);check($publisher->publish($order),'Current saved profile ID selected without a request ID');
    $post=Http::$calls[count(Http::$calls)-1][2];check($post['logist_crm_id']===1&&$post['logist_phone']==='','Server selects only saved profile ID');
    resetFixture();$GLOBALS['freshSender']=new SyntheticSender(1,['admin']);check($publisher->publish($order,'','#1'),'Admin with saved ID allowed');
    resetFixture();GpmAppOrderSync::$linked=true;$GLOBALS['freshSender']=new SyntheticSender(null);check(!$publisher->publish($order,'','#1')&&count(Http::$calls)===0&&GpmAppOrderSync::$syncCalls===0,'Repeat publication also requires saved profile ID');
    resetFixture();$order->workers_cost=0;check(!$publisher->publish($order,'','#1'),'Positive worker rate required');check(count(Http::$calls)===1&&Http::$calls[0][0]==='GET','Invalid rate never publishes');$order->workers_cost=500;
    resetFixture();check(!$publisher->publish($order,'+71111111111','#1')&&count(Http::$calls)===0,'Ambiguous selectors rejected');
    resetFixture();$GLOBALS['scope']='https://other.example';check(!$publisher->publish($order,'','#1')&&count(Http::$calls)===0,'TS-only guard');
    resetFixture();Http::$postStatus=400;check(!$publisher->publish($order,'','#1'),'API failure surfaced');check(strpos($publisher->errorMessage(),'Arbitrary')===false,'Arbitrary response body not exposed');
    check(strpos(json_encode(Illuminate\Support\Facades\Log::$events),'synthetic-token')===false,'Token absent from logs');
    resetFixture();GpmAppOrderSync::$linked=true;
    check($publisher->publish($order,'','#1'),'Manual resubmission accepted');
    $first=Http::$calls[count(Http::$calls)-1];
    check(strpos($first[1],'/order-resubmission/TEST%2F26')!==false,'Dedicated manual endpoint and encoded number');
    check(preg_match('/^[0-9a-f]{32}$/D',$first[2]['request_id'])===1,'Unique operation ID');
    check($first[2]['source_instance']==='https://ts.workstaffcrm.ru'&&$first[2]['logist_crm_id']===1,'Trusted TS and saved ID');
    check($publisher->publish($order,'','#1'),'Second explicit click requests moderation again');
    $second=Http::$calls[count(Http::$calls)-1];
    check($first[2]['request_id']!==$second[2]['request_id'],'Each explicit click is a distinct operation');
    foreach(['IN_PROCESS','DONE_PENDING','CONVERTED','JUNK'] as $status){
        resetFixture();GpmAppOrderSync::$linked=true;Http::$linkedStatus=$status;
        check(!$publisher->publish($order,'','#1')&&$publisher->errorStatus()===409,'Started and closed publication blocked');
        check(GpmAppOrderSync::$syncCalls===0&&count(Http::$calls)===2,'No sync or moderation after started/closed guard');
    }
    resetFixture();GpmAppOrderSync::$linked=true;Http::$moderationStatus=409;
    check(!$publisher->publish($order,'','#1')&&$publisher->errorStatus()===409,'Server progress race is reported');
    resetFixture();GpmAppOrderSync::$linked=true;Http::$moderationStatus=503;
    check(!$publisher->publish($order,'','#1')&&$publisher->errorStatus()===502,'Missing moderation acknowledgement is not success');
    foreach([2,3,4,5] as $status){
        resetFixture();GpmAppOrderSync::$linked=true;$order->status_id=$status;
        check(!$publisher->publish($order,'','#1')&&$publisher->errorStatus()===409,'TS own progress blocks repeated moderation');
        check(GpmAppOrderSync::$prepared===0&&GpmAppOrderSync::$syncCalls===0,'No stage or sync for started TS order');
    }
    $order->status_id=0;
    echo "CRM saved profile ID publication and transport checks PASS\n";
}

<?php
namespace Fixture {
    final class Clock { public static $now=0.0; }
    final class Collection implements \IteratorAggregate {
        private $rows;
        public function __construct(array $rows) { $this->rows=array_values($rows); }
        public function getIterator(): \Traversable { return new \ArrayIterator($this->rows); }
        public function map(callable $f): self { return new self(array_map($f,$this->rows)); }
        public function filter(callable $f): self { return new self(array_filter($this->rows,$f)); }
        public function values(): self { return $this; }
        public function all(): array { return $this->rows; }
        public function count(): int { return count($this->rows); }
        public function first() { return $this->rows[0] ?? null; }
    }
    final class UserQuery {
        private $email;
        private $ids;
        public function with($relation): self { return $this; }
        public function whereIn($column,$ids): self { $this->ids=array_map("strval",$ids);return $this; }
        public function where($column,$value): self {
            if ($column!=='email') throw new \RuntimeException('Unexpected query');
            $this->email=$value; return $this;
        }
        public function get($columns=[]): Collection {
            $rows=array_values(\App\Models\User::$rows);
            if ($this->email!==null) $rows=array_values(array_filter($rows,function($r){return $r->email===$this->email;}));
            if ($this->ids!==null) $rows=array_values(array_filter($rows,function($r){return in_array((string)$r->id,$this->ids,true);}));
            return new Collection($rows);
        }
        public function first() { return $this->get()->first(); }
    }
    final class BranchQuery {
        public function get($columns=[]): Collection { return new Collection(\App\Models\Branch::$rows); }
    }
    final class Response {
        private $value;
        public function __construct(array $value) { $this->value=$value; }
        public function successful(): bool { return true; }
        public function json(): array { return $this->value; }
    }
    final class Request {
        public function withOptions($options): self {
            if (($options['allow_redirects']??null)!==false) throw new \RuntimeException('Redirect enabled');
            return $this;
        }
        public function acceptJson(): self { return $this; }
        public function asJson(): self { return $this; }
        public function withHeaders($headers): self {
            if (($headers['X-GPM-App-Token']??'')!=='synthetic-service-token') throw new \RuntimeException('Missing service auth');
            return $this;
        }
        public function post($url,$input): Response {
            if ($url!=='https://app-api.gpmbot.ru/app-api/integration/registration-preview/workers')
                throw new \RuntimeException('Wrong integration target');
            if ($input['source_instance']!=='https://ts.workstaffcrm.ru') throw new \RuntimeException('Wrong scope');
            \Illuminate\Support\Facades\Http::$calls++;
            \Fixture\Clock::$now += \Illuminate\Support\Facades\Http::$latency;
            if ($input['operation']==='list') {
                $profiles=array_values(array_filter(\Illuminate\Support\Facades\Http::$profiles,function($p){
                    return !isset(\Illuminate\Support\Facades\Http::$acknowledged[$p['profile_id']]);
                }));
                return new Response(['protocol'=>'gpm-preview-workers-v1','source_instance'=>'https://ts.workstaffcrm.ru',
                    'environment'=>'registration-preview','profiles'=>$profiles]);
            }
            if (\Illuminate\Support\Facades\Http::$ackFailures>0) {
                \Illuminate\Support\Facades\Http::$ackFailures--;
                throw new \RuntimeException('Synthetic lost acknowledgement');
            }
            \Illuminate\Support\Facades\Http::$receipts[]=$input;
            if ($input['status']==='linked') \Illuminate\Support\Facades\Http::$acknowledged[$input['profile_id']]=true;
            return new Response(['success'=>true]);
        }
    }
}
namespace App\Services\Gpm {
    function microtime($asFloat=true) { return \Fixture\Clock::$now; }
}
namespace App\Models {
    final class User {
        public static $rows=[],$creates=0,$failRole=false;
        public $id,$phone,$active=true,$deleted_at=null,$email=null,$note=null,$roles=[];
        public function __construct(array $data) { foreach($data as $key=>$value)$this->$key=$value; }
        public static function withTrashed() { return new \Fixture\UserQuery(); }
        public static function create(array $data): self {
            foreach(self::$rows as $r)if($r->email===$data['email'])throw new \RuntimeException('Unique email');
            self::$creates++;
            $id=count(self::$rows)+100;
            $row=new self($data+['id'=>$id]);
            self::$rows[$id]=$row;
            return $row;
        }
        public function assignRole($role): void {
            if (self::$failRole) throw new \RuntimeException('Synthetic role failure');
            $this->roles=[$role];
        }
        public function getRoleNames() { return new \Fixture\Collection($this->roles); }
    }
    final class Branch {
        public static $rows=[];
        public $id,$name,$city;
        public function __construct($id,$name,$city) {
            $this->id=$id;$this->name=$name;$this->city=(object)['name'=>$city];
        }
        public static function with($relation) { return new \Fixture\BranchQuery(); }
    }
}
namespace Illuminate\Support\Facades {
    final class Http {
        public static $profiles=[],$acknowledged=[],$receipts=[],$calls=0,$ackFailures=0,$latency=0.0;
        public static function timeout($seconds) { return new \Fixture\Request(); }
    }
    final class Log { public static function warning($message,$details): void {} }
    final class DB {
        public static function table($name) {
            if ($name!=='users') throw new \RuntimeException('Unexpected table');
            return new \Fixture\UserQuery();
        }
        public static function transaction(callable $action) {
            $before=serialize(\App\Models\User::$rows);
            try{return $action();}catch(\Throwable $e){\App\Models\User::$rows=unserialize($before);throw $e;}
        }
    }
}
namespace {
    require __DIR__.'/GpmWorkerMatchPolicy.php';
    require __DIR__.'/GpmPreviewWorkerPolicy.php';
    require __DIR__.'/GpmPreviewWorkerSync.php';
    use App\Models\User;
    use App\Models\Branch;
    use App\Services\Gpm\GpmPreviewWorkerSync;
    use Illuminate\Support\Facades\Http;
    $environment=[];$location='';$checks=0;$directories=[];
    function env($key,$default=null){global $environment;return $environment[$key]??$default;}
    function config($key){global $environment;return $environment['APP_URL'];}
    function storage_path($relative){global $location;return $location.'/'.$relative;}
    function check($value,$message){global $checks;if(!$value)throw new RuntimeException($message);$checks++;}
    function fixture(): array {
        return ['profile_id'=>'preview_'.str_repeat('a',32),'environment'=>'registration-preview',
            'verification_method'=>'test_code','phone_verified'=>true,'phone_country'=>'RU',
            'phone'=>'+79000000001','revision'=>str_repeat('f',64),'surname'=>'Пример','first_name'=>'Тест',
            'middle_name'=>'','birth_date'=>'1990-01-01','cities'=>['Москва'],'created_at'=>time()];
    }
    function resetFixture(): void {
        global $environment,$location,$directories;
        $location=sys_get_temp_dir().'/gpm-preview-sync-'.bin2hex(random_bytes(8));
        mkdir($location,0700);$directories[]=$location;
        $environment=['APP_URL'=>'https://ts.workstaffcrm.ru','GPM_PREVIEW_WORKER_SYNC_ENABLED'=>'true',
            'GPM_PREVIEW_WORKER_SYNC_SINCE'=>time()-60,'GPM_APP_API_URL'=>'https://app-api.gpmbot.ru',
            'GPM_APP_API_TOKEN'=>'synthetic-service-token'];
        User::$rows=[];User::$creates=0;User::$failRole=false;
        Branch::$rows=[new Branch(1,'Иная компания','Москва'),new Branch(2,'ООО "Джи Пи ЭМ"','Москва')];
        Http::$profiles=[fixture()];Http::$acknowledged=[];Http::$receipts=[];Http::$calls=0;Http::$ackFailures=0;Http::$latency=0.0;\Fixture\Clock::$now=0.0;
    }
    register_shutdown_function(function()use(&$directories){
        foreach($directories as $base){
            if(strpos($base,sys_get_temp_dir().'/gpm-preview-sync-')!==0)continue;
            $iterator=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($base,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);
            foreach($iterator as $item){if($item->isDir())rmdir($item->getPathname());else unlink($item->getPathname());}
            rmdir($base);
        }
    });
    resetFixture();$sync=new GpmPreviewWorkerSync();$result=$sync->run(true);
    check($result['created']===1 && count(User::$rows)===0,'Dry run created a worker');
    check(count(Http::$receipts)===0,'Dry run acknowledged');
    $result=$sync->run();
    check($result['created']===1 && $result['linked']===1,'New worker not linked');
    $worker=array_values(User::$rows)[0];
    check($worker->roles===['loader'] && $worker->password===null,'Credentials/roles wrong');
    check($worker->branch_id===2 && $worker->send_sms_about_hiring===false,'Branch/SMS side effect');
    $sync->run();check(User::$creates===1,'Retry duplicate');

    resetFixture();
    User::$rows[8]=new User(['id'=>8,'phone'=>'8 (900) 000-00-01','roles'=>['loader'],'active'=>false,'note'=>'existing']);
    $before=serialize(User::$rows);$r=(new GpmPreviewWorkerSync())->run();
    check($r['linked']===1 && User::$creates===0,'Existing worker not reused');
    check(serialize(User::$rows)===$before,'Existing worker changed');

    resetFixture();Http::$ackFailures=2;$sync=new GpmPreviewWorkerSync();$sync->run();
    check(User::$creates===1,'First create failed');
    $r=$sync->run();check($r['linked']===1 && User::$creates===1,'Lost response duplicated user');
    $saved=json_decode(file_get_contents(storage_path('app/gpm-preview-worker-links/'.fixture()['profile_id'].'.json')),true);
    check($saved['created_by_sync']===true,'Creation provenance lost');

    resetFixture();$sync=new GpmPreviewWorkerSync();$sync->run();
    unlink(storage_path('app/gpm-preview-worker-links/'.fixture()['profile_id'].'.json'));
    Http::$acknowledged=[];$r=$sync->run();
    check(User::$creates===1 && $r['linked']===1,'Lost receipt duplicated user');

    resetFixture();User::$failRole=true;$sync=new GpmPreviewWorkerSync();$sync->run();
    check(count(User::$rows)===0,'Partial user survived role failure');
    User::$failRole=false;$sync->run();check(count(User::$rows)===1,'Role failure retry failed');

    resetFixture();
    foreach([8,9] as $id)User::$rows[$id]=new User(['id'=>$id,'phone'=>fixture()['phone'],'roles'=>['loader']]);
    $r=(new GpmPreviewWorkerSync())->run();check($r['conflict']===1 && User::$creates===0,'Duplicate phone merged');
    resetFixture();$environment['APP_URL']='https://main.invalid';
    $r=(new GpmPreviewWorkerSync())->run();check(Http::$calls===0 && !$r['enabled'],'Main CRM touched');
    resetFixture();$environment['GPM_PREVIEW_WORKER_SYNC_ENABLED']='false';
    (new GpmPreviewWorkerSync())->run();check(Http::$calls===0,'Disabled sync ran');

    resetFixture();
    $second=fixture();$second['profile_id']='preview_'.str_repeat('b',32);$second['phone']='+79000000002';
    $third=fixture();$third['profile_id']='preview_'.str_repeat('c',32);$third['phone']='+79000000003';
    Http::$profiles=[fixture(),$second,$third];Http::$latency=7.0;
    $sync=new GpmPreviewWorkerSync();$r=$sync->run();
    check($r['created']===1 && $r['deferred']===1,'Slow preview consumed the whole job');
    Http::$latency=0;\Fixture\Clock::$now=0.0;$r=$sync->run();
    check(count(User::$rows)===3 && User::$creates===3,'Budget retry lost profiles or created duplicates');

    echo "Preview worker service: {$checks} checks passed\n";
}

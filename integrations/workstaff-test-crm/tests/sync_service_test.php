<?php
// Standalone failure-injection tests. No Laravel bootstrap, real database,
// credentials or network requests are used.
namespace {
    $GLOBALS['fixture_dir'] = sys_get_temp_dir() . '/gpm-sync-test-' . bin2hex(random_bytes(6));
    $GLOBALS['crm_url'] = 'https://ts.workstaffcrm.ru';
    $GLOBALS['sync_enabled'] = true;
    $GLOBALS['write_failure'] = false;
    function config($name, $default = null) { return $name === 'app.url' ? $GLOBALS['crm_url'] : $default; }
    function env($name, $default = null) {
        return ['GPM_APP_API_URL' => 'https://app-api.gpmbot.ru', 'GPM_APP_API_TOKEN' => 'synthetic-token',
            'GPM_APP_ORDER_SYNC_ENABLED' => $GLOBALS['sync_enabled']][$name] ?? $default;
    }
    function storage_path($suffix) { return $GLOBALS['fixture_dir'] . '/' . $suffix; }
    function optional($value) { return $value ?: (object) ['name' => null]; }
    function now() { return \Carbon\Carbon::parse('2026-10-13T12:00:00+00:00'); }
    function check($value, $message) { if (!$value) { throw new \RuntimeException($message); } }
}
namespace Carbon {
    class Carbon extends \DateTimeImmutable {
        public static function parse($value) { return $value instanceof self ? $value : new self($value); }
        public function utc() { return $this->setTimezone(new \DateTimeZone('UTC')); }
        public function toIso8601String() { return $this->format('c'); }
    }
}
namespace App\Models {
    class Order {
        public const STATUS_COMPLETED = 3, STATUS_RETURNED = 4, STATUS_DELETE = 5;
        public static $rows = [];
        public $id = 1, $order_number = '033/25', $status_id = 2, $city = 'Test city';
        public $address = 'Test address', $street = 'Test street', $house = '3';
        public $note = 'Test note', $info = '', $additional = [], $coords = '[55.7,37.6]';
        public $completion_date, $duration = 6, $min_time = 4, $loader_count = 2;
        public $workers_cost = 500, $customer_cost = 1000, $metro_id = null, $metroStation = null;
        public function __construct() { $this->completion_date = \Carbon\Carbon::parse('2026-10-13T09:00:00+03:00'); }
        public static function find($id) { return isset(self::$rows[$id]) ? clone self::$rows[$id] : null; }
        public static function whereKey($id) { return new OrderQuery($id); }
        public function loadMissing($relations) { return $this; }
        public function unsetRelation($relation) { return $this; }
        public function save() { self::$rows[$this->id] = clone $this; return true; }
    }
    class OrderQuery {
        private $id;
        public function __construct($id) { $this->id = $id; }
        public function lockForUpdate() { return $this; }
        public function firstOrFail() { return Order::find($this->id); }
    }
}
namespace App\Models\Reference {
    class MetroStation {
        public static function where($field, $value) { throw new \RuntimeException('Synthetic invalid metro'); }
    }
}
namespace Illuminate\Support\Facades {
    class Log {
        public static $messages = [];
        public static function warning($message, $context = []) { self::$messages[] = [$message, $context]; }
        public static function info($message, $context = []) { self::$messages[] = [$message, $context]; }
    }
    class DB {
        public static $commitFailure = false;
        public static $failStateAfterCommit = false;
        public static function transaction($callback) {
            $before = \App\Models\Order::$rows;
            try {
                $result = $callback();
                if (self::$commitFailure) { throw new \RuntimeException('Synthetic commit failure'); }
                if (self::$failStateAfterCommit) { $GLOBALS['write_failure'] = true; }
                return $result;
            } catch (\Throwable $error) {
                \App\Models\Order::$rows = $before;
                throw $error;
            }
        }
    }
    class Http {
        public static $app, $calls = [], $getStatus = 200, $revisionRace = false;
        public static function timeout($seconds) { return new FakeRequest; }
        public static function revision() { return hash('sha256', json_encode(self::$app['fields'])); }
        public static function snapshot() { return array_merge(self::$app, ['revision' => self::revision()]); }
    }
    class FakeResponse {
        private $status, $data;
        public function __construct($status, $data) { $this->status = $status; $this->data = $data; }
        public function successful() { return $this->status >= 200 && $this->status < 300; }
        public function status() { return $this->status; }
        public function json($key = null) { return $key === null ? $this->data : ($this->data[$key] ?? null); }
    }
    class FakeRequest {
        public function acceptJson() { return $this; }
        public function asJson() { return $this; }
        public function withHeaders($headers) { \check($headers['X-GPM-App-Token'] === 'synthetic-token', 'Integration token required'); return $this; }
        public function get($url) {
            Http::$calls[] = ['GET', $url];
            return new FakeResponse(Http::$getStatus, Http::snapshot());
        }
        public function patch($url, $body) {
            Http::$calls[] = ['PATCH', $url, $body];
            if (Http::$revisionRace) { Http::$app['fields']['price_per_hour'] = 950; }
            if ($body['revision'] !== Http::revision()) { return new FakeResponse(409, []); }
            \check($body['source_instance'] === 'https://ts.workstaffcrm.ru', 'Wrong CRM instance');
            Http::$app['fields'] = array_merge(Http::$app['fields'], $body['fields']);
            return new FakeResponse(200, Http::snapshot());
        }
    }
}
namespace App\Services\Order {
    function file_put_contents($path, $data) {
        return $GLOBALS['write_failure'] ? false : \file_put_contents($path, $data);
    }
}
namespace {
    require __DIR__ . '/../app/Services/Order/GpmOrderSyncPlan.php';
    require __DIR__ . '/../app/Services/Order/GpmAppOrderSync.php';
    use App\Models\Order;
    use App\Services\Order\GpmAppOrderSync;
    use Illuminate\Support\Facades\DB;
    use Illuminate\Support\Facades\Http;

    $sync = new GpmAppOrderSync;
    $statePath = storage_path('app/gpm-app-sync/1.json');
    function fixture($sync) {
        $GLOBALS['crm_url'] = GpmAppOrderSync::INSTANCE;
        $GLOBALS['sync_enabled'] = true;
        $GLOBALS['write_failure'] = false;
        Http::$getStatus = 200; Http::$revisionRace = false; Http::$calls = [];
        DB::$commitFailure = false; DB::$failStateAfterCommit = false;
        $order = new Order; $order->save();
        $fields = $sync->crmFields($order);
        Http::$app = ['protocol' => GpmAppOrderSync::PROTOCOL, 'source_instance' => GpmAppOrderSync::INSTANCE,
            'order_id' => $order->order_number, 'status' => 'IN_PROCESS', 'fields' => $fields];
        $sync->rememberPublication($order, '+79990000000', array_merge($fields, ['source_instance' => GpmAppOrderSync::INSTANCE]), $fields);
        return $order;
    }
    try {
        $order = fixture($sync);
        check($sync->syncOrder($order), 'Idle sync');
        check(count(Http::$calls) === 1, 'Idle sync only reads');
        check(strpos(Http::$calls[0][1], '033%2F25') !== false, 'Slash order numbers must be encoded');

        $order = fixture($sync);
        Order::$rows[1]->workers_cost = 600;
        check($sync->syncOrder($order), 'CRM rate edit');
        check(Http::$app['fields']['price_per_hour'] === 600, 'CRM rate must reach app');

        $order = fixture($sync);
        Http::$app['fields']['price_per_hour'] = 700;
        check($sync->syncOrder($order) && Order::$rows[1]->workers_cost === 700, 'App rate must reach CRM');
        Http::$calls = [];
        check($sync->syncOrder($order) && count(Http::$calls) === 1, 'No echo writes after app rate edit');

        $order = fixture($sync);
        Http::$app['fields']['price_per_hour'] = 720;
        $sync->rememberPublication($order, '+79990000000', array_merge(Http::$app['fields'],
            ['source_instance' => GpmAppOrderSync::INSTANCE]), $sync->crmFields($order));
        check($sync->syncOrder($order) && Order::$rows[1]->workers_cost === 720, 'First linkage must preserve legacy app edits');

        $order = fixture($sync);
        Order::$rows[1]->workers_cost = 600;
        Http::$app['fields']['price_per_hour'] = 700;
        check($sync->syncOrder($order) && Order::$rows[1]->workers_cost === 700, 'App wins simultaneous rate edit');

        $order = fixture($sync);
        Order::$rows[1]->workers_cost = 600;
        Http::$app['fields']['description'] = 'App note';
        check($sync->syncOrder($order), 'Different fields merge');
        check(Http::$app['fields']['price_per_hour'] === 600 && Order::$rows[1]->note === 'App note', 'Both directions in one merge');

        $order = fixture($sync);
        $before = file_get_contents($statePath);
        Order::$rows[1]->workers_cost = 600;
        Http::$revisionRace = true;
        check(!$sync->syncOrder($order), 'Stale app revision must defer');
        check(file_get_contents($statePath) === $before, 'Stale revision must not advance baseline');
        check(Order::$rows[1]->workers_cost === 600, 'Rejected PATCH must not save CRM');
        Http::$revisionRace = false;
        check($sync->syncOrder($order) && Order::$rows[1]->workers_cost === 950, 'Retry must retain concurrent app edit');

        $order = fixture($sync);
        $before = file_get_contents($statePath);
        Order::$rows[1]->workers_cost = 600;
        Http::$app['fields']['description'] = 'App note';
        DB::$commitFailure = true;
        check(!$sync->syncOrder($order), 'CRM commit failure must defer');
        check(file_get_contents($statePath) === $before && Order::$rows[1]->note === 'Test note', 'Failed commit must not advance baseline');
        DB::$commitFailure = false;
        check($sync->syncOrder($order) && Order::$rows[1]->note === 'App note', 'Commit retry must converge');

        $order = fixture($sync);
        $before = file_get_contents($statePath);
        Http::$app['fields']['price_per_hour'] = 710;
        DB::$failStateAfterCommit = true;
        check(!$sync->syncOrder($order) && Order::$rows[1]->workers_cost === 710, 'Filesystem error occurs after commit');
        check(file_get_contents($statePath) === $before, 'Filesystem error keeps baseline');
        DB::$failStateAfterCommit = false; $GLOBALS['write_failure'] = false;
        check($sync->syncOrder($order), 'Filesystem retry must converge');

        $order = fixture($sync);
        $before = file_get_contents($statePath);
        Http::$getStatus = 503;
        check(!$sync->syncOrder($order) && file_get_contents($statePath) === $before, 'HTTP failure keeps baseline');

        $order = fixture($sync);
        Http::$app['source_instance'] = 'https://workstaffcrm.ru';
        check(!$sync->syncOrder($order), 'Another CRM instance must be rejected');

        $order = fixture($sync);
        $GLOBALS['crm_url'] = 'https://workstaffcrm.ru';
        check(!$sync->syncOrder($order) && !Http::$calls, 'Main CRM must not contact the API');

        $order = fixture($sync);
        Http::$app['status'] = 'CONVERTED';
        Http::$app['fields']['price_per_hour'] = 900;
        check($sync->syncOrder($order) && Order::$rows[1]->workers_cost === 500, 'Closed app order is protected');

        $order = fixture($sync);
        Order::$rows[1]->status_id = Order::STATUS_COMPLETED;
        Http::$app['fields']['price_per_hour'] = 900;
        check($sync->syncOrder($order) && Order::$rows[1]->workers_cost === 500, 'Closed CRM order is protected');

        $order = fixture($sync);
        Http::$app['fields']['metro'] = 'Unknown metro';
        check(!$sync->syncOrder($order) && Order::$rows[1]->metro_id === null, 'Unknown CRM reference must not corrupt order');

        $order = fixture($sync);
        $order->id = 2; $order->save();
        check(!$sync->syncOrder($order) && !Http::$calls, 'Unlinked orders must not synchronize');
        echo "GPM sync service: 16 scenarios passed\n";
    } finally {
        // Only files created by this test, inside its unique fixture directory.
        foreach (glob(storage_path('app/gpm-app-sync/*')) ?: [] as $path) { unlink($path); }
        foreach (['app/gpm-app-sync', 'app', ''] as $path) {
            $directory = $GLOBALS['fixture_dir'] . ($path !== '' ? '/' . $path : '');
            if (is_dir($directory)) { rmdir($directory); }
        }
    }
}

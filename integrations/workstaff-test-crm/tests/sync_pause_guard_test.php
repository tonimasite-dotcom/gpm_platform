<?php
// Pure failure-injection fixture. No Laravel bootstrap, SQL, cron or HTTP.
namespace {
    $GLOBALS['fixture_sync_enabled'] = false;
    $GLOBALS['fixture_sync_url'] = 'https://ts.workstaffcrm.ru';
    function env($key, $default = null) {
        return $key === 'GPM_APP_ORDER_SYNC_ENABLED' ? $GLOBALS['fixture_sync_enabled'] : $default;
    }
    function config($key, $default = null) {
        return $key === 'app.url' ? $GLOBALS['fixture_sync_url'] : $default;
    }
    function pauseAssert($value) {
        if (!$value) throw new \RuntimeException('SYNC_PAUSE_GUARD_ASSERTION_FAILED');
    }
}
namespace Illuminate\Console {
    class Command {
        public function info($message) { /* No job output or configuration values. */ }
    }
}
namespace {
    require __DIR__ . '/../app/Services/Order/GpmAppOrderSync.php';
    require __DIR__ . '/../app/Console/Commands/SyncGpmAppOrders.php';
    class PausedSyncSpy extends \App\Services\Order\GpmAppOrderSync {
        public $calls = 0;
        public $deferred = 0;
        public function syncLinkedOrders(): array {
            $this->calls++;
            return ['synced' => 0, 'deferred' => $this->deferred];
        }
    }
    $sync = new PausedSyncSpy();
    $command = new \App\Console\Commands\SyncGpmAppOrders();
    pauseAssert($command->handle($sync) === 0 && $sync->calls === 0);
    $GLOBALS['fixture_sync_enabled'] = 'false';
    pauseAssert($command->handle($sync) === 0 && $sync->calls === 0);
    $GLOBALS['fixture_sync_enabled'] = '0';
    pauseAssert($command->handle($sync) === 0 && $sync->calls === 0);
    $GLOBALS['fixture_sync_enabled'] = 'true';
    pauseAssert($command->handle($sync) === 0 && $sync->calls === 1);
    $GLOBALS['fixture_sync_url'] = 'https://workstaffcrm.ru';
    pauseAssert($command->handle($sync) === 0 && $sync->calls === 1);
    $GLOBALS['fixture_sync_url'] = 'https://ts.workstaffcrm.ru';
    $sync->deferred = 1;
    pauseAssert($command->handle($sync) === 1 && $sync->calls === 2);
    $GLOBALS['fixture_sync_enabled'] = false;
    pauseAssert($command->handle($sync) === 0 && $sync->calls === 2);
    echo "GPM sync pause guard: 7 scenarios passed\n";
}

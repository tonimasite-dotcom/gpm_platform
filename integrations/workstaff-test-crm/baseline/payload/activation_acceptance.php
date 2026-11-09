<?php
use App\Models\Order;
use App\Services\Order\PlanningDayActivation;
use App\Services\Order\PlanningDayRule;
use App\Services\Order\WorkerCalculationActivation;

$work = '/root/gpm-ts-update/20261106-baseline-01';
$app = null;
$originalStorage = null;
$checks = [];
$current = 'private_bootstrap';

function activationAssert($value): void {
    if (!$value) throw new RuntimeException('ACTIVATION_ASSERTION_FAILED');
}
function activationCheck(string $name, callable $test): void {
    global $checks, $current;
    $current = $name;
    $test();
    $checks[] = $name;
}
function activationRejected(string $expected, callable $test): void {
    try { $test(); }
    catch (RuntimeException $error) {
        activationAssert($error->getMessage() === $expected);
        return;
    }
    throw new RuntimeException('EXPECTED_ACTIVATION_REJECTION_MISSING');
}

try {
    $app = require __DIR__ . '/private_runtime_bootstrap.php';
    $originalStorage = $app->storagePath();
    activationAssert($originalStorage === $work . '/candidate/storage');
    $originalWorkerHash = hash_file('sha256', WorkerCalculationActivation::path());
    $originalPlanningPresent = PlanningDayActivation::exists();
    $originalPlanningHash = $originalPlanningPresent ? hash_file('sha256', PlanningDayActivation::path()) : null;
    $fixtureRoot = $work . '/activation-fixtures-20261109-' . bin2hex(random_bytes(6));
    activationAssert(mkdir($fixtureRoot, 0700));
    $newStorage = static function (string $name) use ($fixtureRoot, $app) {
        activationAssert(preg_match('/^[a-z-]+$/D', $name) === 1);
        $path = $fixtureRoot . '/' . $name;
        activationAssert(mkdir($path . '/app', 0700, true));
        activationAssert(mkdir($path . '/framework', 0700));
        file_put_contents($path . '/framework/down', '{}');
        $app->useStoragePath($path);
        return $path;
    };
    $published = $newStorage('published');
    activationCheck('missing_planning_marker_retains_legacy_rule', static function () {
        activationAssert(PlanningDayActivation::boundary() === null);
    });
    activationCheck('missing_worker_marker_fails_closed', static function () {
        activationRejected('WORKER_ACTIVATION_MISSING_OR_UNSAFE', static function () {
            WorkerCalculationActivation::boundary();
        });
    });
    activationCheck('worker_marker_publishes_and_reads_same_boundary', static function () {
        WorkerCalculationActivation::publish(17);
        activationAssert(WorkerCalculationActivation::boundary() === 17);
    });
    activationCheck('planning_marker_publishes_and_reads_same_boundary', static function () {
        PlanningDayActivation::publish(17, '2026-11-09 00:00:00 UTC');
        activationAssert(PlanningDayActivation::boundary() === 17);
    });
    activationCheck('worker_duplicate_publish_preserves_existing_bytes', static function () {
        $before = hash_file('sha256', WorkerCalculationActivation::path());
        activationRejected('WORKER_ACTIVATION_ALREADY_EXISTS_OR_PATH', static function () {
            WorkerCalculationActivation::publish(18);
        });
        activationAssert(hash_file('sha256', WorkerCalculationActivation::path()) === $before);
    });
    activationCheck('planning_duplicate_publish_preserves_existing_bytes', static function () {
        $before = hash_file('sha256', PlanningDayActivation::path());
        activationRejected('PLANNING_DAY_ACTIVATION_ALREADY_EXISTS_OR_PATH', static function () {
            PlanningDayActivation::publish(18, '2026-11-09 00:00:01 UTC');
        });
        activationAssert(hash_file('sha256', PlanningDayActivation::path()) === $before);
    });
    $timezone = config('app.default_timezone');
    config(['app.default_timezone' => 'Europe/Moscow']);
    activationCheck('at_boundary_order_uses_utc_day', static function () {
        $order = new Order(); $order->id = 17; $order->completion_date = '2026-11-09 22:30:00';
        activationAssert(!PlanningDayRule::usesOrderZone($order));
        activationAssert(PlanningDayRule::dayFor($order) === ['2026-11-09', 1]);
    });
    activationCheck('after_boundary_order_uses_next_local_day', static function () {
        $order = new Order(); $order->id = 18; $order->completion_date = '2026-11-09 22:30:00';
        activationAssert(PlanningDayRule::usesOrderZone($order));
        activationAssert(PlanningDayRule::dayFor($order) === ['2026-11-10', 2]);
    });
    config(['app.default_timezone' => $timezone]);
    $dbKey = 'database.connections.' . config('database.default') . '.database';
    $database = config($dbKey);
    config([$dbKey => 'synthetic_foreign_database_not_connected']);
    try {
        activationCheck('copied_worker_marker_rejects_different_database_identity', static function () {
            activationRejected('WORKER_ACTIVATION_ENVIRONMENT_MISMATCH', static function () {
                WorkerCalculationActivation::boundary();
            });
        });
        activationCheck('copied_planning_marker_rejects_different_database_identity', static function () {
            activationRejected('PLANNING_DAY_ACTIVATION_ENVIRONMENT_MISMATCH', static function () {
                PlanningDayActivation::boundary();
            });
        });
    } finally { config([$dbKey => $database]); }
    // No SQL is executed while the synthetic foreign identity is set.
    $env = config('app.env'); config(['app.env' => 'synthetic-foreign-environment']);
    try {
        activationCheck('worker_marker_rejects_different_environment', static function () {
            activationRejected('WORKER_ACTIVATION_ENVIRONMENT_MISMATCH', static function () {
                WorkerCalculationActivation::boundary();
            });
        });
        activationCheck('planning_marker_rejects_different_environment', static function () {
            activationRejected('PLANNING_DAY_ACTIVATION_ENVIRONMENT_MISMATCH', static function () {
                PlanningDayActivation::boundary();
            });
        });
    } finally { config(['app.env' => $env]); }
    foreach (['worker' => 'worker-calculation-activation.json', 'planning' => 'planning-day-activation.json'] as $kind => $name) {
        $path = $newStorage($kind . '-tampered');
        $doc = json_decode(file_get_contents($published . '/app/' . $name), true);
        $doc['body']['boundary'] = 18; // Retain the original signature: must reject.
        file_put_contents($path . '/app/' . $name, json_encode($doc));
        activationCheck($kind . '_boundary_tamper_fails_signature', static function () use ($kind) {
            if ($kind === 'worker') activationRejected('WORKER_ACTIVATION_CORRUPT', static function () {
                WorkerCalculationActivation::boundary();
            });
            else activationRejected('PLANNING_DAY_ACTIVATION_CORRUPT', static function () {
                PlanningDayActivation::boundary();
            });
        });
    }
    $restored = $newStorage('byte-restored');
    foreach (['worker-calculation-activation.json', 'planning-day-activation.json'] as $name) {
        activationAssert(copy($published . '/app/' . $name, $restored . '/app/' . $name));
    }
    activationCheck('byte_restore_reads_under_original_identity', static function () {
        activationAssert(WorkerCalculationActivation::boundary() === 17 && PlanningDayActivation::boundary() === 17);
    });
    $app->useStoragePath($originalStorage);
    App\Services\Release\GpmTsRehearsal::assertContext();
    activationCheck('real_candidate_markers_unchanged', static function () use ($originalWorkerHash, $originalPlanningPresent, $originalPlanningHash) {
        activationAssert(hash_file('sha256', WorkerCalculationActivation::path()) === $originalWorkerHash);
        activationAssert(PlanningDayActivation::exists() === $originalPlanningPresent);
        if ($originalPlanningPresent) activationAssert(hash_file('sha256', PlanningDayActivation::path()) === $originalPlanningHash);
    });
    $report = ['success' => true, 'scenarios_passed' => count($checks), 'scenarios' => $checks,
        'unmodified_activation_and_day_rule_classes' => true, 'synthetic_storage_only' => true,
        'candidate_activation_markers_unchanged' => true, 'fixture_evidence_preserved' => true,
        'database_writes_performed' => false, 'foreign_identity_sql_connections' => false,
        'full_switch_and_rollback_rehearsed' => false, 'live_crm_changed' => false, 'release_ready' => false];
    file_put_contents($work . '/activation-acceptance-20261109.json', json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
} catch (Throwable $error) {
    if ($app && $originalStorage) $app->useStoragePath($originalStorage);
    file_put_contents($work . '/activation-private-error.log', (string)$error);
    echo json_encode(['success' => false, 'failed_scenario' => $current, 'scenarios_passed' => count($checks),
        'exception_type' => get_class($error), 'raw_details_withheld' => true, 'live_crm_changed' => false]) . PHP_EOL;
    exit(1);
}

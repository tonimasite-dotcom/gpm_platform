<?php
use Illuminate\Support\Facades\DB;
$work='/root/gpm-ts-update/20261109-switch-01';
$started=microtime(true);$current=null;
try {
    $app=require __DIR__.'/private_runtime_bootstrap.php';
    App\Services\Release\GpmTsSwitchContext::assertUpgrade();
    if (getenv('CRM_DOCUMENT_COST_WRITERS_STOPPED')!=='1') throw new RuntimeException('PRIVATE_WRITERS_STOPPED_MARKER_REQUIRED');
    $mode=$argv[1]??'';
    if (!in_array($mode,['fail-after-three','complete'],true)) throw new RuntimeException('EXPLICIT_UPGRADE_MODE_REQUIRED');
    $migrator=$app['migrator'];
    $files=$migrator->getMigrationFiles([base_path('database/migrations')]);
    $ran=$migrator->getRepository()->getRan();
    $planPath=$work.'/upgrade-migration-plan.json';
    if (!is_file($planPath)) {
        if (count($ran)!==180) throw new RuntimeException('EXPECTED_ORIGINAL_MIGRATION_HISTORY_REQUIRED');
        $pending=array_diff_key($files,array_flip($ran));
        if (count($pending)!==37) throw new RuntimeException('EXACT_37_MIGRATION_PLAN_REQUIRED');
        $entries=[];
        foreach ($pending as $name=>$path) $entries[$name]=hash_file('sha256',$path);
        $plan=['original_history'=>$ran,'migrations'=>$entries];
        file_put_contents($planPath,json_encode($plan,JSON_PRETTY_PRINT));
    } else $plan=json_decode(file_get_contents($planPath),true,512,JSON_THROW_ON_ERROR);
    if (array_diff($plan['original_history'],$ran)
        || array_diff($ran,array_merge($plan['original_history'],array_keys($plan['migrations'])))) {
        throw new RuntimeException('UNEXPECTED_MIGRATION_HISTORY');
    }
    foreach ($plan['migrations'] as $name=>$hash) {
        if (!isset($files[$name]) || hash_file('sha256',$files[$name])!==$hash) throw new RuntimeException('PINNED_MIGRATION_FILE_CHANGED');
    }
    $pending=array_diff(array_keys($plan['migrations']),$ran);
    if ($mode==='fail-after-three' && count($pending)!==37) throw new RuntimeException('FAILURE_INJECTION_REQUIRES_PRISTINE_UPGRADE_DB');
    $applied=0;
    foreach ($pending as $name) {
        $current=$name;
        $stepStarted=microtime(true);
        file_put_contents($work.'/upgrade-step-progress.jsonl',json_encode(['event'=>'started','migration'=>$name,
            'started_epoch'=>$stepStarted]).PHP_EOL,FILE_APPEND|LOCK_EX);
        $migrator->run([$files[$name]],['step'=>true]);
        file_put_contents($work.'/upgrade-step-progress.jsonl',json_encode(['event'=>'completed','migration'=>$name,
            'elapsed_seconds'=>round(microtime(true)-$stepStarted,3)]).PHP_EOL,FILE_APPEND|LOCK_EX);
        $applied++;
        if ($mode==='fail-after-three' && $applied===3) {
            $report=['expected_failure_injected'=>true,'applied_before_failure'=>3,
                'migration_history_count'=>DB::table('migrations')->count(),
                'elapsed_seconds'=>round(microtime(true)-$started,3),'live_crm_changed'=>false];
            file_put_contents($work.'/upgrade-injected-failure.json',json_encode($report,JSON_PRETTY_PRINT));
            echo json_encode($report).PHP_EOL;exit(20);
        }
    }
    if (DB::table('migrations')->count()!==217) throw new RuntimeException('FINAL_MIGRATION_HISTORY_MISMATCH');
    $tables=(int)DB::selectOne('SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')->n;
    if ($tables!==112) throw new RuntimeException('FINAL_TABLE_COUNT_MISMATCH');
    if (DB::table('orders')->where('calculation_version','<>',1)->exists()) throw new RuntimeException('OLD_ORDER_VERSION_CHANGED');
    $workerBoundary=App\Services\Order\WorkerCalculationActivation::boundary();
    $stored=DB::table('order_worker_calculations')->where('order_id',0)->where('user_id',0)->first();
    if (!$stored || $stored->mode!=='boundary' || (int)$stored->hourly_rate!==$workerBoundary) throw new RuntimeException('WORKER_BOUNDARY_STATE_MISMATCH');
    if (App\Services\Order\PlanningDayActivation::exists()) throw new RuntimeException('PLANNING_BOUNDARY_ALREADY_EXISTS');
    $kernel=$app->make(Illuminate\Contracts\Console\Kernel::class);
    $code=$kernel->call('orders:planning-day-boundary',['--activate'=>true]);
    file_put_contents($work.'/planning-activation-private-output.log',$kernel->output());
    if ($code!==0 || !is_int(App\Services\Order\PlanningDayActivation::boundary())) throw new RuntimeException('PLANNING_DAY_ACTIVATION_FAILED');
    $report=['success'=>true,'applied_this_pass'=>$applied,'total_planned_migrations'=>37,
        'migration_history_count'=>217,'table_count'=>112,'worker_boundary_matches_database'=>true,
        'planning_day_boundary_locally_activated'=>true,'old_orders_remain_v1'=>true,
        'elapsed_seconds'=>round(microtime(true)-$started,3),'live_crm_changed'=>false];
    file_put_contents($work.'/upgrade-completed.json',json_encode($report,JSON_PRETTY_PRINT));
    echo json_encode($report).PHP_EOL;
} catch (Throwable $error) {
    file_put_contents($work.'/upgrade-private-error.log',(string)$error);
    $safe=$error instanceof RuntimeException && preg_match('/^[A-Z][A-Z0-9_]{3,100}$/D',$error->getMessage())
        ? $error->getMessage():get_class($error);
    echo json_encode(['success'=>false,'failed_migration'=>$current,'safe_code'=>$safe,
        'elapsed_seconds'=>round(microtime(true)-$started,3),'raw_details_withheld'=>true,'live_crm_changed'=>false]).PHP_EOL;
    exit(1);
}

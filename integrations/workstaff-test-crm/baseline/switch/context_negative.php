<?php
$work='/root/gpm-ts-update/20261109-switch-01';$checks=[];$app=null;$current='bootstrap';
function contextAssert($value): void { if (!$value) throw new RuntimeException('SWITCH_CONTEXT_TEST_FAILED'); }
function contextReject($name, $expected, $test): void {
    global $checks,$current;
    $current=$name;
    try { $test(); }
    catch (RuntimeException $error) { contextAssert($error->getMessage()===$expected);$checks[]=$name;return; }
    throw new RuntimeException('EXPECTED_CONTEXT_REJECTION_MISSING');
}
try {
    if (($argv[1]??'')==='prebootstrap-denial') {
        contextReject('outside_network_namespace_rejected_before_bootstrap','PRIVATE_SWITCH_PREFLIGHT_REQUIRED',static function () {
            require __DIR__.'/private_runtime_bootstrap.php';
        });
    } else {
        $app=require __DIR__.'/private_runtime_bootstrap.php';
        foreach (['database'=>'synthetic_foreign_db','username'=>'root','unix_socket'=>'/run/mysqld/mysqld.sock'] as $field=>$bad) {
            $key='database.connections.mysql.'.$field;$original=config($key);config([$key=>$bad]);
            try {
                contextReject('wrong_'.$field.'_rejected_before_connection','PRIVATE_SWITCH_CONFIG_REQUIRED',static function () {
                    App\Services\Release\GpmTsSwitchContext::assertRuntime();
                });
            } finally { config([$key=>$original]); }
        }
        putenv('GPM_TS_SWITCH=0');
        try {
            contextReject('missing_switch_marker_rejected','PRIVATE_SWITCH_RUNTIME_REQUIRED',static function () {
                App\Services\Release\GpmTsSwitchContext::assertRuntime();
            });
        } finally { putenv('GPM_TS_SWITCH=1'); }
        $root=base_path();$app->setBasePath($work.'/not-the-runtime');
        try {
            contextReject('foreign_root_rejected_before_connection','PRIVATE_SWITCH_RUNTIME_REQUIRED',static function () {
                App\Services\Release\GpmTsSwitchContext::assertRuntime();
            });
        } finally { $app->setBasePath($root); }
        // Both instances have real isolated sockets; verify the actual datadir check too.
        $version=App\Services\Release\GpmTsSwitchContext::assertRuntime();
        $other=$version==='old'?'new':'old';
        $old=config('database.connections.mysql');
        $identity=json_decode(file_get_contents($work.'/mysql-'.$other.'/identity.json'),true);
        $foreign=$old;$foreign['unix_socket']=$identity['socket'];$foreign['database']=$identity['database'];
        $foreign['username']=$identity['username'];$foreign['password']=$identity['password'];
        // A separate connection cannot pass the current runtime's fixed config identity.
        config(['database.connections.switch_foreign'=>$foreign]);
        $row=Illuminate\Support\Facades\DB::connection('switch_foreign')->selectOne('SELECT @@datadir AS path');
        contextAssert(realpath($row->path)!==App\Services\Release\GpmTsSwitchContext::expected($version)['datadir']);
        Illuminate\Support\Facades\DB::disconnect('switch_foreign');
        $checks[]='isolated_old_and_new_datadirs_are_distinct';
    }
    echo json_encode(['success'=>true,'scenarios_passed'=>count($checks),'scenarios'=>$checks,'live_crm_changed'=>false]).PHP_EOL;
} catch (Throwable $error) {
    file_put_contents($work.'/context-negative-private-error.log',(string)$error);
    echo json_encode(['success'=>false,'failed_case'=>$current,'exception_type'=>get_class($error),'raw_details_withheld'=>true]).PHP_EOL;exit(1);
}

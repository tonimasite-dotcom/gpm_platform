<?php
try {
    $app = require __DIR__ . '/private_runtime_bootstrap.php';
    $db = Illuminate\Support\Facades\DB::class;
    $report = ['private_bootstrap_passed' => true, 'runtime_context_accepted' =>
        App\Services\Release\GpmTsRuntimeContext::isTsOrPrivateRehearsal(),
        'tables' => [], 'role_names' => [], 'route_paths' => []];
    foreach (['users', 'orders', 'plannings', 'customers', 'contact_persons'] as $table) {
        $columns = $db::select("SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA
            FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? ORDER BY ORDINAL_POSITION", [$table]);
        $required = array_filter($columns, static function ($column) {
            return $column->IS_NULLABLE === 'NO' && $column->COLUMN_DEFAULT === null
                && strpos($column->EXTRA, 'auto_increment') === false;
        });
        $report['tables'][$table] = array_values(array_map(static function ($column) {
            return ['name' => $column->COLUMN_NAME, 'type' => $column->COLUMN_TYPE,
                'required_without_default' => $column->IS_NULLABLE === 'NO'
                    && $column->COLUMN_DEFAULT === null && strpos($column->EXTRA, 'auto_increment') === false];
        }, $required));
    }
    $report['role_names'] = $db::table('roles')->whereIn('name',
        ['admin', 'head', 'manager', 'hr', 'logist', 'loader', 'accountant'])->pluck('name')->all();
    foreach ($app['router']->getRoutes() as $route) {
        $uri = $route->uri();
        if (preg_match('/login|gpm_worker_rate|logist.*access|logist.*edit|toggle.*logist/', $uri)) {
            $report['route_paths'][] = ['uri' => $uri, 'methods' => $route->methods(), 'action' => $route->getActionName()];
        }
    }
    echo json_encode($report, JSON_PRETTY_PRINT) . PHP_EOL;
} catch (Throwable $error) {
    file_put_contents('/root/gpm-ts-update/20261106-baseline-01/runtime-probe-private-error.log', (string)$error);
    echo json_encode(['success' => false, 'error_code' => 'PRIVATE_RUNTIME_PROBE_FAILED', 'exception_type' => get_class($error)]) . PHP_EOL;
    exit(1);
}

<?php
// This file can operate ONLY inside the pre-created private rehearsal context.
// No live apply path, destructive reset, rollback or external network requests.
$root = '/root/gpm-ts-update/20261106-baseline-01/candidate';
$reportPath = '/root/gpm-ts-update/20261106-baseline-01/migration-rehearsal-result.json';
require $root . '/vendor/autoload.php';
$private = Dotenv\Dotenv::parse(file_get_contents($root . '/.env'));
foreach (['DB_SOCKET' => '/root/gpm-ts-update/20261106-baseline-01/rehearsal-mysql/mysql.sock',
    'DB_DATABASE' => 'gpm_ts_rehearsal_20261106', 'DB_USERNAME' => 'gpm_ts_rehearsal',
    'APP_URL' => 'https://ts.workstaffcrm.ru'] as $key => $expected) {
    if (($private[$key] ?? null) !== $expected || (getenv($key) !== false && getenv($key) !== $expected)) {
        throw new RuntimeException('PRIVATE_CONFIGURATION_REQUIRED_BEFORE_BOOTSTRAP');
    }
}
$app = require $root . '/bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$current = null;
$started = microtime(true);

function originalSnapshot(array $before = null): array
{
    $pdo = Illuminate\Support\Facades\DB::connection()->getPdo();
    $tables = $before ? array_keys($before) : $pdo->query('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')->fetchAll(PDO::FETCH_COLUMN);
    $result = [];
    foreach ($tables as $table) {
        if (!preg_match('/^[a-zA-Z0-9_]+$/', $table)) throw new RuntimeException('UNEXPECTED_TABLE_IDENTIFIER');
        $statement = $pdo->prepare('SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? ORDER BY ORDINAL_POSITION');
        $statement->execute([$table]);
        $columns = $before ? $before[$table]['columns'] : $statement->fetchAll(PDO::FETCH_COLUMN);
        $statement->closeCursor();
        $pk = $pdo->prepare("SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION");
        $pk->execute([$table]);$primary = $pk->fetchAll(PDO::FETCH_COLUMN);$pk->closeCursor();
        $boundary = $before[$table]['boundary'] ?? null;
        $additive = in_array($table, ['migrations', 'permissions', 'main_settings'], true);
        if (!$before && $additive && $primary === ['id']) {
            $boundary = (int)$pdo->query('SELECT COALESCE(MAX(id),0) FROM `' . $table . '`')->fetchColumn();
        }
        $projection = array_map(static function ($column) use ($table) {
            return $table === 'document_link_services' && $column === 'cost'
                ? 'CAST(`cost` AS DECIMAL(20,2)) AS `cost`' : '`' . $column . '`';
        }, $columns);
        $sql = 'SELECT ' . implode(',', $projection) . ' FROM `' . $table . '`';
        if ($additive && $boundary !== null) $sql .= ' WHERE id <= ' . (int)$boundary;
        if ($primary) $sql .= ' ORDER BY `' . implode('`,`', $primary) . '`';
        $hash = hash_init('sha256');$count = 0;$unordered = [];
        $pdo->setAttribute(PDO::MYSQL_ATTR_USE_BUFFERED_QUERY, false);
        $rows = $pdo->query($sql);
        while ($row = $rows->fetch(PDO::FETCH_NUM)) {
            $serialized = '';
            foreach ($row as $value) $serialized .= $value === null ? 'N;' : 'S' . strlen((string)$value) . ':' . (string)$value . ';';
            if ($primary) hash_update($hash, hash('sha256', $serialized, true));
            else $unordered[] = hash('sha256', $serialized);
            $count++;
        }
        $rows->closeCursor();$pdo->setAttribute(PDO::MYSQL_ATTR_USE_BUFFERED_QUERY, true);
        if (!$primary) { sort($unordered);foreach ($unordered as $item) hash_update($hash, $item); }
        $result[$table] = ['columns' => $columns, 'boundary' => $boundary, 'rows' => $count, 'sha256' => hash_final($hash)];
    }
    return $result;
}

try {
    $kernel->bootstrap();
    App\Services\Release\GpmTsRehearsal::assertContext();
    $baselinePath = dirname($reportPath) . '/original-data-checks.json';
    if (is_file($baselinePath)) {
        $before = json_decode(file_get_contents($baselinePath), true, 512, JSON_THROW_ON_ERROR);
        if (count($before) !== 72) throw new RuntimeException('ORIGINAL_BASELINE_REQUIRED');
    } else {
        $before = originalSnapshot();
        if (count($before) !== 72) throw new RuntimeException('ORIGINAL_BASELINE_REQUIRED');
        file_put_contents($baselinePath, json_encode($before));
    }
    $app['events']->listen(Illuminate\Database\Events\MigrationStarted::class, function ($event) use (&$current) {
        $current = get_class($event->migration);
    });
    $migrator = $app['migrator'];
    $migrator->run([$root . '/database/migrations'], ['step' => true]);
    $after = originalSnapshot($before);
    $changed = [];
    foreach ($before as $table => $state) {
        if ($state['rows'] !== $after[$table]['rows'] || $state['sha256'] !== $after[$table]['sha256']) $changed[] = $table;
    }
    if ($changed) throw new RuntimeException('ORIGINAL_TABLE_DATA_CHANGED');
    $db = Illuminate\Support\Facades\DB::class;
    $tables = $db::selectOne('SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()');
    if ((int)$tables->n !== 112) throw new RuntimeException('TARGET_TABLE_COUNT_MISMATCH');
    $bad = (int)$db::table('orders')->where('calculation_version', '<>', 1)->count();
    if ($bad) throw new RuntimeException('LEGACY_ORDER_VERSION_CHANGED');
    if ($db::table('users')->whereNotNull('deleted_email')->exists()) throw new RuntimeException('EMAIL_DATA_TRANSFORM_NOT_DEFERRED');
    $report = ['success' => true, 'private_rehearsal_only' => true, 'original_tables_verified' => count($before),
        'original_data_hashes_unchanged' => true, 'table_count_after' => (int)$tables->n,
        'legacy_orders_v1' => true, 'bank_card_data_deferred' => true, 'email_data_deferred' => true,
        'elapsed_seconds' => round(microtime(true) - $started, 2), 'live_changed' => false];
    file_put_contents($reportPath, json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
} catch (Throwable $error) {
    // SQL exception text may include private row values. Keep raw diagnostics
    // only in this root-private workspace, never in tool output or Git.
    file_put_contents(dirname($reportPath) . '/migration-rehearsal-private-error.log', (string)$error);
    $code = $error instanceof RuntimeException && preg_match('/^[A-Z][A-Z0-9_]{3,100}$/', $error->getMessage())
        ? $error->getMessage() : get_class($error);
    $report = ['success' => false, 'migration_class' => $current, 'error_code' => $code,
        'private_rehearsal_only' => true, 'elapsed_seconds' => round(microtime(true) - $started, 2), 'live_changed' => false];
    file_put_contents($reportPath, json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
    exit(1);
}

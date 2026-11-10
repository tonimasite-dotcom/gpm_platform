<?php
// Schema and migration names only. No Laravel bootstrap or business row reads.
if (PHP_SAPI !== 'cli' || count($argv) !== 2 || !in_array($argv[1], [
    '/var/www/gruzpiter/data/www/workstaffcrm.ru',
    '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'
], true) || realpath($argv[1]) !== $argv[1]) { exit(1); }
$pdo = null;
try {
    $root = $argv[1];
    require $root . '/vendor/autoload.php';
    $env = Dotenv\Dotenv::parse(file_get_contents($root . '/.env'));
    if (($env['DB_CONNECTION'] ?? 'mysql') !== 'mysql') { throw new RuntimeException(); }
    $socket = $env['DB_SOCKET'] ?? '';
    $dsn = 'mysql:' . ($socket !== '' ? 'unix_socket=' . $socket : 'host=' . ($env['DB_HOST'] ?? '127.0.0.1') . ';port=' . ($env['DB_PORT'] ?? '3306'))
        . ';dbname=' . $env['DB_DATABASE'] . ';charset=utf8mb4';
    $pdo = new PDO($dsn, $env['DB_USERNAME'], $env['DB_PASSWORD'] ?? '', [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('SET SESSION TRANSACTION READ ONLY');
    $pdo->beginTransaction();
    $columns = $pdo->query('SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name, COLUMN_TYPE AS column_type,
        IS_NULLABLE AS nullable, (COLUMN_DEFAULT IS NOT NULL) AS has_default, EXTRA AS extra
        FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, ORDINAL_POSITION')->fetchAll(PDO::FETCH_ASSOC);
    $migrations = $pdo->query('SELECT migration FROM migrations ORDER BY migration')->fetchAll(PDO::FETCH_COLUMN);
    $pdo->rollBack();
    echo json_encode(['passed' => true, 'columns' => $columns, 'migrations' => $migrations,
        'business_rows_read' => false, 'read_only_transaction' => true, 'laravel_bootstrapped' => false,
        'schema_or_data_changed' => false], JSON_PRETTY_PRINT) . "\n";
} catch (Throwable $error) {
    if ($pdo && $pdo->inTransaction()) { $pdo->rollBack(); }
    echo json_encode(['passed' => false, 'safe_error' => 'READ_ONLY_SCHEMA_INSPECTION_FAILED_DETAILS_WITHHELD']);
    exit(1);
}

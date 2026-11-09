<?php
// Verify the new restored backup with the immutable original checksum algorithm.
$work = '/root/gpm-ts-update/20261106-baseline-01';
$directory = $work . '/sql-recovery-20261109/rehearsal-mysql';
try {
    if (PHP_SAPI !== 'cli' || realpath($directory) !== $directory
        || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')) {
        throw new RuntimeException('PRIVATE_RECOVERY_CONTEXT_REQUIRED');
    }
    $baselinePath = $work . '/original-data-checks.json';
    $checkerPath = $work . '/rehearse_migrations.php';
    if (hash_file('sha256', $baselinePath) !== 'b490e05bab6aec9c520130d66b607aa78ca4d3247c4e71034fb059f2a1cc50ec'
        || hash_file('sha256', $checkerPath) !== '0934ffda332a82cad3c5525945009313580a56aea7da1ad8d22eb8a1914b4259') {
        throw new RuntimeException('IMMUTABLE_ORIGINAL_CHECK_FILES_REQUIRED');
    }
    $identity = json_decode(file_get_contents($directory . '/identity.json'), true, 512, JSON_THROW_ON_ERROR);
    if ($identity['socket'] !== $directory . '/mysql.sock' || $identity['datadir'] !== $directory . '/data'
        || $identity['database'] !== 'gpm_ts_backup_20261109' || $identity['username'] !== 'gpm_ts_backup_recovery') {
        throw new RuntimeException('PRIVATE_RECOVERY_IDENTITY_REQUIRED');
    }
    $pdo = new PDO('mysql:unix_socket=' . $identity['socket'] . ';dbname=' . $identity['database'] . ';charset=utf8mb4',
        $identity['username'], $identity['password'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_STRINGIFY_FETCHES => false, PDO::ATTR_EMULATE_PREPARES => false]);
    $actual = $pdo->query('SELECT DATABASE() AS db,CURRENT_USER() AS account,@@datadir AS datadir,@@skip_networking AS isolated')->fetch(PDO::FETCH_ASSOC);
    if ($actual['db'] !== $identity['database'] || $actual['account'] !== $identity['username'] . '@localhost'
        || realpath($actual['datadir']) !== $identity['datadir'] || (int)$actual['isolated'] !== 1) {
        throw new RuntimeException('PRIVATE_RECOVERY_DATABASE_REQUIRED');
    }
    // Extract only the already-reviewed pure checksum function. Its saved file
    // hash is pinned above; no bootstrap, migrator or report-writing code runs.
    $checker = file_get_contents($checkerPath);
    $start = strpos($checker, 'function originalSnapshot(');
    $end = strpos($checker, "\ntry {", $start);
    if ($start === false || $end === false) throw new RuntimeException('CHECKSUM_FUNCTION_REQUIRED');
    $function = substr($checker, $start, $end - $start);
    $anchor = 'Illuminate\\Support\\Facades\\DB::connection()->getPdo()';
    if (substr_count($function, $anchor) !== 1) throw new RuntimeException('CHECKSUM_PDO_ANCHOR_REQUIRED');
    $GLOBALS['gpm_recovery_pdo'] = $pdo;
    eval(str_replace($anchor, '$GLOBALS[\'gpm_recovery_pdo\']', $function));
    $pdo->exec('SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci');
    $pdo->exec('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY');
    $before = json_decode(file_get_contents($baselinePath), true, 512, JSON_THROW_ON_ERROR);
    if (count($before) !== 72) throw new RuntimeException('ORIGINAL_72_TABLE_BASELINE_REQUIRED');
    $after = originalSnapshot($before);
    $changed = [];
    foreach ($before as $table => $state) {
        if ($state['rows'] !== $after[$table]['rows'] || $state['sha256'] !== $after[$table]['sha256']) $changed[] = $table;
    }
    $pdo->exec('ROLLBACK');
    echo json_encode(['private_recovery_only' => true, 'tables_checked' => count($before),
        'matches_original_november_6_baseline' => !$changed, 'changed_tables' => $changed,
        'original_checksum_algorithm_used' => true, 'original_files_unchanged' =>
            hash_file('sha256', $baselinePath) === 'b490e05bab6aec9c520130d66b607aa78ca4d3247c4e71034fb059f2a1cc50ec',
        'live_database_accessed' => false]) . PHP_EOL;
} catch (Throwable $error) {
    echo json_encode(['success' => false, 'error_code' => 'PRIVATE_BASELINE_VERIFICATION_FAILED']) . PHP_EOL;
    exit(1);
}

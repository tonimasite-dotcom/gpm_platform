<?php
// Read-only diagnosis of the SAVED rehearsal. Never boot Laravel or run migrations.
// Execute with: unshare --net php diagnose_original_data.php
// stdout contains only table names, counts, hashes and schema metadata.
require __DIR__ . '/OriginalDataAcceptance.php';

function diagnoseOriginalData(): array
{
    $work = '/root/gpm-ts-update/20261106-baseline-01';
    $root = $work . '/candidate';
    $socket = $work . '/rehearsal-mysql/mysql.sock';
    $data = $work . '/rehearsal-mysql/data';
    $baseline = $work . '/original-data-checks.json';
    if (PHP_SAPI !== 'cli' || realpath($work) !== $work || realpath($root) !== $root
        || realpath($data) !== $data || realpath($baseline) !== $baseline
        || realpath($socket) !== $socket || is_link($root . '/.env')
        || !is_file($root . '/storage/framework/down')
        || !is_readable('/proc/self/ns/net') || !is_readable('/proc/1/ns/net')
        || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')) {
        throw new RuntimeException('PRIVATE_ISOLATED_REHEARSAL_REQUIRED');
    }
    require $root . '/vendor/autoload.php';
    $env = Dotenv\Dotenv::parse(file_get_contents($root . '/.env'));
    foreach (['DB_CONNECTION' => 'mysql', 'DB_SOCKET' => $socket,
        'DB_DATABASE' => 'gpm_ts_rehearsal_20261106', 'DB_USERNAME' => 'gpm_ts_rehearsal',
        'APP_URL' => 'https://ts.workstaffcrm.ru'] as $key => $expected) {
        if (($env[$key] ?? null) !== $expected) {
            throw new RuntimeException('PRIVATE_CONFIGURATION_REQUIRED');
        }
    }
    $baselineHash = hash_file('sha256', $baseline);
    $before = json_decode(file_get_contents($baseline), true, 512, JSON_THROW_ON_ERROR);
    if (!is_array($before) || count($before) !== 72) {
        throw new RuntimeException('SAVED_72_TABLE_BASELINE_REQUIRED');
    }
    $pdo = new PDO('mysql:unix_socket=' . $socket . ';dbname=gpm_ts_rehearsal_20261106;charset=utf8mb4',
        'gpm_ts_rehearsal', $env['DB_PASSWORD'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_STRINGIFY_FETCHES => false, PDO::ATTR_EMULATE_PREPARES => false]);
    $identity = $pdo->query('SELECT DATABASE() AS db, CURRENT_USER() AS account, @@datadir AS datadir,
        @@skip_networking AS network_disabled, VERSION() AS version')->fetch(PDO::FETCH_ASSOC);
    if ($identity['db'] !== 'gpm_ts_rehearsal_20261106'
        || $identity['account'] !== 'gpm_ts_rehearsal@localhost'
        || realpath($identity['datadir']) !== $data || (int)$identity['network_disabled'] !== 1
        || strpos($identity['version'], '5.7.') !== 0) {
        throw new RuntimeException('PRIVATE_DATABASE_IDENTITY_REQUIRED');
    }
    $pdo->exec('SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci');
    $pdo->exec('SET SESSION lock_wait_timeout=15');
    $pdo->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $pdo->exec('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY');
    try {
        $results = [];
        foreach ($before as $table => $state) {
            if (!preg_match('/^[a-zA-Z0-9_]+$/D', $table) || empty($state['columns'])) {
                throw new RuntimeException('INVALID_BASELINE_TABLE');
            }
            foreach ($state['columns'] as $column) {
                if (!is_string($column) || !preg_match('/^[a-zA-Z0-9_]+$/D', $column)) {
                    throw new RuntimeException('INVALID_BASELINE_COLUMN');
                }
            }
            $statement = $pdo->prepare("SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? AND CONSTRAINT_NAME='PRIMARY'
                ORDER BY ORDINAL_POSITION");
            $statement->execute([$table]);
            $primary = $statement->fetchAll(PDO::FETCH_COLUMN);
            $statement->closeCursor();
            // Preserve the exact projection, boundary, ordering and serialization
            // used by the original checker. Do not normalize any new differences.
            $projection = array_map(static function ($column) use ($table) {
                return $table === 'document_link_services' && $column === 'cost'
                    ? 'CAST(`cost` AS DECIMAL(20,2)) AS `cost`' : '`' . $column . '`';
            }, $state['columns']);
            $sql = 'SELECT ' . implode(',', $projection) . ' FROM `' . $table . '`';
            $boundary = $state['boundary'] ?? null;
            if (in_array($table, ['migrations', 'permissions', 'main_settings'], true) && $boundary !== null) {
                if (!is_int($boundary) || $boundary < 0 || $primary !== ['id']) {
                    throw new RuntimeException('INVALID_SAVED_BOUNDARY');
                }
                $sql .= ' WHERE id <= ' . $boundary;
            }
            if ($primary) $sql .= ' ORDER BY `' . implode('`,`', $primary) . '`';
            $hash = hash_init('sha256');
            $count = 0;
            $unordered = [];
            $pdo->setAttribute(PDO::MYSQL_ATTR_USE_BUFFERED_QUERY, false);
            $rows = $pdo->query($sql);
            while ($row = $rows->fetch(PDO::FETCH_NUM)) {
                $serialized = '';
                foreach ($row as $value) {
                    $serialized .= $value === null ? 'N;' : 'S' . strlen((string)$value) . ':' . (string)$value . ';';
                }
                if ($primary) hash_update($hash, hash('sha256', $serialized, true));
                else $unordered[] = hash('sha256', $serialized);
                $count++;
            }
            $rows->closeCursor();
            $pdo->setAttribute(PDO::MYSQL_ATTR_USE_BUFFERED_QUERY, true);
            if (!$primary) {
                sort($unordered);
                foreach ($unordered as $item) hash_update($hash, $item);
            }
            $actual = hash_final($hash);
            $results[$table] = ['rows_before' => $state['rows'], 'rows_after' => $count,
                'rows_unchanged' => $state['rows'] === $count,
                'hash_unchanged' => $state['sha256'] === $actual];
        }
        $audit = null;
        if (isset($results['activity_log']) && !$results['activity_log']['hash_unchanged']) {
            $state = $before['activity_log'];
            $columns = '`' . implode('`,`', $state['columns']) . '`';
            $limit = (int)$state['rows'];
            $rows = $pdo->query('SELECT ' . $columns . ' FROM activity_log ORDER BY id LIMIT ' . $limit);
            $hash = hash_init('sha256');
            $count = 0;
            while ($row = $rows->fetch(PDO::FETCH_NUM)) {
                $serialized = '';
                foreach ($row as $value) {
                    $serialized .= $value === null ? 'N;' : 'S' . strlen((string)$value) . ':' . (string)$value . ';';
                }
                hash_update($hash, hash('sha256', $serialized, true));
                $count++;
            }
            $rows->closeCursor();
            $auditSourceIds = [];
            $audit = ['original_prefix_rows' => $count,
                'original_prefix_hash_unchanged' => $count === $limit && hash_final($hash) === $state['sha256'],
                'additional_rows' => []];
            $rows = $pdo->query('SELECT * FROM activity_log ORDER BY id LIMIT ' . $limit . ',100');
            while ($row = $rows->fetch(PDO::FETCH_ASSOC)) {
                $properties = json_decode($row['properties'] ?? '{}', true) ?: [];
                $safe = ['causer_present' => isset($row['causer_id']),
                    'subject_present' => isset($row['subject_id']), 'property_sections' => array_keys($properties)];
                foreach (['subject_type', 'causer_type'] as $field) {
                    if (isset($row[$field]) && preg_match('/^App\\\\[A-Za-z\\\\]+$/D', $row[$field])) {
                        $safe[$field] = $row[$field];
                    }
                }
                foreach (['log_name', 'description', 'event'] as $field) {
                    if (isset($row[$field]) && in_array($row[$field], ['default', 'finance', 'created', 'updated', 'deleted', 'cash_source_captured'], true)) {
                        $safe[$field] = $row[$field];
                    }
                }
                foreach (['attributes', 'old'] as $section) {
                    $safe[$section . '_keys'] = isset($properties[$section]) && is_array($properties[$section])
                        ? array_keys($properties[$section]) : [];
                }
                $source = $properties['cash_source'] ?? null;
                $safe['legacy_cash_capture_verified'] = false;
                if ($row['log_name'] === 'finance' && $row['description'] === 'cash_source_captured'
                    && $row['causer_id'] === null && $row['causer_type'] === null
                    && $row['subject_id'] === null && $row['subject_type'] === null
                    && array_keys($properties) === ['cash_source'] && is_array($source)
                    && ($source['legacy'] ?? null) === true && isset($source['planning_id'])) {
                    $query = $pdo->prepare('SELECT * FROM payout_cash_sources WHERE planning_id=?');
                    $query->execute([$source['planning_id']]);
                    $frozen = $query->fetch(PDO::FETCH_ASSOC);
                    $query->closeCursor();
                    $matches = $frozen && (int)$frozen['legacy'] === 1 && $frozen['captured_by'] === null;
                    foreach (['planning_id', 'user_id', 'order_id', 'amount_cents'] as $field) {
                        $matches = $matches && isset($source[$field]) && (string)$source[$field] === (string)$frozen[$field];
                    }
                    $matches = $matches && ($source['day'] ?? null) === ($frozen['day'] ?? null);
                    $safe['legacy_cash_capture_verified'] = (bool)$matches;
                    $auditSourceIds[] = (string)$source['planning_id'];
                }
                $audit['additional_rows'][] = $safe;
            }
            $rows->closeCursor();
            $audit['frozen_cash_source_count'] = (int)$pdo->query('SELECT COUNT(*) FROM payout_cash_sources')->fetchColumn();
            $audit['cash_source_migration_recorded'] = (int)$pdo->query("SELECT COUNT(*) FROM migrations WHERE migration='2026_10_12_230000_create_payout_cash_sources'")->fetchColumn() === 1;
            $audit['one_to_one_source_mapping'] = count($auditSourceIds) === count(array_unique($auditSourceIds))
                && count($auditSourceIds) === $audit['frozen_cash_source_count'];
        }
        $invariants = [
            'table_count_112' => (int)$pdo->query('SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')->fetchColumn() === 112,
            'migration_history_count_217' => (int)$pdo->query('SELECT COUNT(*) FROM migrations')->fetchColumn() === 217,
            'all_legacy_orders_version_1' => (int)$pdo->query('SELECT COUNT(*) FROM orders WHERE calculation_version IS NULL OR calculation_version<>1')->fetchColumn() === 0,
            'new_order_default_version_2' => (string)$pdo->query("SELECT COLUMN_DEFAULT FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='orders' AND COLUMN_NAME='calculation_version'")->fetchColumn() === '2',
            'deleted_email_values_not_populated' => (int)$pdo->query('SELECT COUNT(*) FROM users WHERE deleted_email IS NOT NULL')->fetchColumn() === 0,
            'old_orders_not_opened_for_logist' => (int)$pdo->query('SELECT COUNT(*) FROM orders WHERE logist_edit_until IS NOT NULL')->fetchColumn() === 0,
            'bank_card_data_migration_not_recorded' => (int)$pdo->query("SELECT COUNT(*) FROM migrations WHERE migration='2026_08_05_000000_transfer_banking_card_to_card_number'")->fetchColumn() === 0,
            'email_data_migration_not_recorded' => (int)$pdo->query("SELECT COUNT(*) FROM migrations WHERE migration='2026_10_28_110000_release_deleted_user_emails'")->fetchColumn() === 0,
        ];
        $pdo->exec('ROLLBACK');
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $error;
    }
    if (hash_file('sha256', $baseline) !== $baselineHash) {
        throw new RuntimeException('BASELINE_FILE_CHANGED_DURING_DIAGNOSIS');
    }
    $changed = array_filter($results, static function ($result) {
        return !$result['rows_unchanged'] || !$result['hash_unchanged'];
    });
    $expectedAudit = $audit && $audit['original_prefix_hash_unchanged']
        && $audit['cash_source_migration_recorded'] && $audit['one_to_one_source_mapping']
        && count($audit['additional_rows']) === $results['activity_log']['rows_after'] - $results['activity_log']['rows_before']
        && count($audit['additional_rows']) > 0;
    if ($expectedAudit) {
        foreach ($audit['additional_rows'] as $row) {
            $expectedAudit = $expectedAudit && $row['legacy_cash_capture_verified'];
        }
    }
    $preserved = OriginalDataAcceptance::preserved($results, $audit);
    return ['diagnosis_completed' => true, 'private_rehearsal_only' => true,
        'database_transaction_read_only' => true, 'laravel_bootstrapped' => false,
        'migrations_run' => false, 'baseline_file_sha256' => $baselineHash,
        'baseline_file_unchanged' => true, 'tables_checked' => count($results),
        'original_data_unchanged' => !$changed, 'changed_tables' => $changed,
        'table_checks' => $results, 'audit_log_diagnosis' => $audit,
        'all_original_rows_preserved' => (bool)$preserved,
        'expected_new_cash_audit_verified' => (bool)$expectedAudit,
        'post_migration_invariants' => $invariants,
        'saved_rehearsal_data_acceptance_passed' => $preserved && !in_array(false, $invariants, true),
        'release_ready' => false];
}

try {
    echo json_encode(diagnoseOriginalData(), JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . PHP_EOL;
} catch (Throwable $error) {
    // Raw PDO errors may contain private values. Never echo exception details.
    $code = get_class($error) === RuntimeException::class
        && preg_match('/^[A-Z][A-Z0-9_]{3,100}$/D', $error->getMessage())
        ? $error->getMessage() : 'PRIVATE_DIAGNOSIS_FAILED';
    echo json_encode(['diagnosis_completed' => false, 'error_code' => $code,
        'release_ready' => false]) . PHP_EOL;
    exit(1);
}

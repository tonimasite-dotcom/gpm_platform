<?php
if (PHP_SAPI !== 'fpm-fcgi' || ($_SERVER['SERVER_NAME'] ?? '') !== 'ts.workstaffcrm.ru'
    || !hash_equals((string) getenv('GPM_TS_PRIVATE_PROBE_TOKEN'), trim(file_get_contents(__DIR__ . '/token')))) {
    http_response_code(403); exit;
}
$root = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
$allow = ['app/Console/Commands/CheckDebit.php', 'app/Console/Commands/CheckCustomerDebit.php', 'app/Services/WebKlexMailClient.php'];
$plan = json_decode(file_get_contents(__DIR__ . '/plan.json'), true, 512, JSON_THROW_ON_ERROR);
if (!is_array($plan) || count($plan) !== 3) { throw new RuntimeException('EXACT_DEBT_FILES_REQUIRED'); }
$seen = [];
foreach ($plan as $row) {
    $file = $row['file']; $path = $root . '/' . $file;
    if (!in_array($file, $allow, true) || isset($seen[$file]) || realpath($path) !== $path
        || hash_file('sha256', $path) !== $row['after_sha256']) { throw new RuntimeException('DEBT_FILE_HASH_MISMATCH'); }
    $seen[$file] = true;
}
foreach (array_keys($seen) as $file) {
    $path = $root . '/' . $file; $cached = opcache_is_script_cached($path);
    if (!opcache_invalidate($path, true) && $cached) { throw new RuntimeException('DEBT_OPCACHE_INVALIDATION_FAILED'); }
}
header('Content-Type: application/json');
echo json_encode(['passed' => true, 'ts_files_invalidated' => 3, 'global_cache_reset' => false, 'main_crm_accessed' => false]);

<?php
// Never resets global/shared opcache. Only exact approved files of TS.
if (PHP_SAPI !== 'fpm-fcgi' || ($_SERVER['SERVER_NAME'] ?? '') !== 'ts.workstaffcrm.ru'
    || !hash_equals((string) getenv('GPM_TS_PRIVATE_PROBE_TOKEN'), trim(file_get_contents(__DIR__ . '/token')))) {
    http_response_code(403);
    exit;
}
$root = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
$plan = json_decode(file_get_contents(__DIR__ . '/plan.json'), true, 512, JSON_THROW_ON_ERROR);
if (!function_exists('opcache_invalidate') || !is_array($plan) || count($plan) !== 25) {
    throw new RuntimeException('EXACT_TS_INVALIDATION_PLAN_REQUIRED');
}
$paths = [];
foreach ($plan as $row) {
    $name = $row['file'] ?? '';
    $path = $root . '/' . $name;
    if (strpos($name, 'app/') !== 0 || strpos($name, '..') !== false || substr($name, -4) !== '.php'
        || realpath($path) !== $path || hash_file('sha256', $path) !== ($row['after_sha256'] ?? '')) {
        throw new RuntimeException('TS_INVALIDATION_TARGET_MISMATCH');
    }
    $paths[] = $path;
}
$invalidated = [];
foreach ($paths as $path) {
    $wasCached = opcache_is_script_cached($path);
    $ok = opcache_invalidate($path, true);
    if (!$ok && $wasCached) { throw new RuntimeException('TS_OPCACHE_INVALIDATION_FAILED'); }
    $invalidated[] = ['file' => substr($path, strlen($root) + 1), 'was_cached' => $wasCached,
                      'invalidated_or_not_cached' => $ok || !$wasCached];
}
header('Content-Type: application/json');
echo json_encode(['passed' => true, 'files' => $invalidated, 'global_cache_reset' => false,
    'laravel_bootstrapped' => false, 'database_connected' => false, 'main_crm_accessed' => false]);

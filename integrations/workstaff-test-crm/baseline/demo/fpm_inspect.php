<?php
// Executed by an operator over the TS Unix socket, outside every web root.
if (PHP_SAPI !== 'fpm-fcgi' || ($_SERVER['SERVER_NAME'] ?? '') !== 'ts.workstaffcrm.ru'
    || !hash_equals((string) getenv('GPM_TS_PRIVATE_PROBE_TOKEN'), trim(file_get_contents(__DIR__ . '/token')))) {
    http_response_code(403);
    exit;
}
header('Content-Type: application/json');
$settings = [];
foreach (['opcache.enable', 'opcache.validate_timestamps', 'opcache.revalidate_freq',
          'opcache.revalidate_path', 'opcache.use_cwd', 'opcache.file_cache_only',
          'opcache.restrict_api'] as $key) { $settings[$key] = ini_get($key); }
echo json_encode(['php_version' => PHP_VERSION, 'sapi' => PHP_SAPI, 'settings' => $settings,
    'opcache_invalidate_available' => function_exists('opcache_invalidate'),
    'laravel_bootstrapped' => false, 'database_connected' => false,
    'opcache_invalidated' => false]);

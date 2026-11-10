<?php
// Private pipe to the owner's local viewer. Never run this from a web route.
function gpmPrivateLoginRecords(string $folder, Illuminate\Encryption\Encrypter $encrypter, ?int $now = null): array {
    $now = $now ?? time();
    $rows = [];
    if (is_dir($folder)) {
        if (realpath($folder) !== $folder || (fileperms($folder) & 0077) !== 0) { throw new RuntimeException(); }
        $files = glob($folder . '/*.enc');
        if (count($files) > 1000) { throw new RuntimeException(); }
        foreach ($files as $file) {
            if (is_link($file) || !preg_match('/^[1-9][0-9]*\.enc$/', basename($file)) || (fileperms($file) & 0077) !== 0) {
                throw new RuntimeException();
            }
            $row = json_decode($encrypter->decryptString(file_get_contents($file)), true, 512, JSON_THROW_ON_ERROR);
            if (($row['version'] ?? null) !== 1 || (int) ($row['user_id'] ?? 0) !== (int) basename($file)) { throw new RuntimeException(); }
            $age = $now - (int) ($row['issued_at'] ?? 0);
            if (!is_string($row['code'] ?? null) || $age < 0 || $age > 600) { continue; }
            $rows[] = array_intersect_key($row, array_flip(['user_id', 'email', 'code', 'issued_at']));
        }
    }
    return $rows;
}
// Importing the pure reader for isolated fixtures never reads a live env.
if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') !== __FILE__) { return; }
if (PHP_SAPI !== 'cli' || posix_geteuid() !== 0) { exit(2); }
$root = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
try {
    if (realpath($root) !== $root || realpath($root . '/.env') !== $root . '/.env') { throw new RuntimeException(); }
    require $root . '/vendor/autoload.php';
    $environment = Dotenv\Dotenv::parse(file_get_contents($root . '/.env'));
    if (rtrim($environment['APP_URL'] ?? '', '/') !== 'https://ts.workstaffcrm.ru') { throw new RuntimeException(); }
    $key = $environment['APP_KEY'] ?? '';
    if (strpos($key, 'base64:') === 0) { $key = base64_decode(substr($key, 7), true); }
    $encrypter = new Illuminate\Encryption\Encrypter($key, 'AES-256-CBC');
    // Contains login challenges: only the encrypted SSH pipe/local viewer may read.
    echo json_encode(['rows' => gpmPrivateLoginRecords($root . '/storage/app/gpm-ts-demo-login', $encrypter)], JSON_THROW_ON_ERROR);
} catch (Throwable $error) {
    // Never print exception values, env, email addresses or challenge material.
    fwrite(STDERR, "PRIVATE_LOGIN_INBOX_UNAVAILABLE\n");
    exit(1);
}

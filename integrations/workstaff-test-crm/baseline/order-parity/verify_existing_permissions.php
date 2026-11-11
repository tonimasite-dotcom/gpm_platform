<?php
// The caller supplies the strict private bootstrap; never bootstrap a live CRM.
$root = getenv('GPM_TS_PRIVATE_ROOT');
if (PHP_SAPI !== 'cli' || !is_string($root)
    || !preg_match('#^/root/gpm-ts-update/order-parity-[0-9-]+$#D', $root)
    || realpath($root) !== $root || getenv('GPM_TS_REHEARSAL') !== '1'
    || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')) {
    throw new RuntimeException('STRICT_PRIVATE_ROOT_REQUIRED');
}
$current = 'bootstrap';
try {
    $app = require $root . '/acceptance/private_runtime_bootstrap.php';
    $current = 'existing_account_permission_equivalence';
    $different = [];
    $count = 0;
    $hash = hash_init('sha256');
    \App\Models\User::withTrashed()->with(['roles.permissions', 'permissions'])
        ->chunkById(100, function ($users) use (&$different, &$count, $hash) {
            foreach ($users as $user) {
                // Spatie's existing direct grants plus existing role grants.
                // No role, permission, account or pivot is written by this probe.
                $expected = $user->permissions->merge($user->roles->flatMap(function ($role) {
                    return $role->permissions;
                }))->pluck('id')->unique()->sort()->values()->all();
                $actual = $user->getAllPermissions()->pluck('id')->unique()->sort()->values()->all();
                if ($expected !== $actual) $different[] = (int) $user->id;
                hash_update($hash, json_encode([$user->id, $expected, $actual]) . "\n");
                $count++;
            }
        });
    $report = ['success' => !$different, 'accounts_checked' => $count,
        'accounts_with_changed_effective_permission_sets' => count($different),
        'permission_inventory_sha256' => hash_final($hash),
        'existing_grants_compared' => true, 'database_writes_performed' => false,
        'live_changed' => false, 'release_ready' => false];
    file_put_contents($root . '/permission-differences-private.json', json_encode($different));
    file_put_contents($root . '/existing-permissions-result.json', json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
    exit($different ? 1 : 0);
} catch (Throwable $error) {
    file_put_contents($root . '/existing-permissions-private-error.log', (string) $error);
    echo json_encode(['success' => false, 'stage' => $current,
        'exception_class' => get_class($error), 'raw_details_withheld' => true,
        'live_changed' => false]) . PHP_EOL;
    exit(1);
}

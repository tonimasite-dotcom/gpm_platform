<?php
$workRoot = getenv('GPM_TS_PRIVATE_ROOT');
$mode = getenv('GPM_TS_GATE_PROBE_REPORT');
if (PHP_SAPI !== 'cli' || !is_string($workRoot) || realpath($workRoot) !== $workRoot
    || !preg_match('#^/root/gpm-ts-update/order-parity-[0-9-]+$#D', $workRoot)
    || !in_array($mode, ['new', 'old', 'restored'], true)) {
    throw new RuntimeException('PRIVATE_GATE_PROBE_CONTEXT_REQUIRED');
}
try {
    $app = require $workRoot . '/acceptance/private_runtime_bootstrap.php';
    $abilities = \Spatie\Permission\Models\Permission::where('guard_name', 'api')->orderBy('name')->pluck('name')->all();
    $explicitOnly = ['read_remove_payout_marks', 'read_cancel_worker_fines'];
    foreach ($explicitOnly as $ability) {
        if (!in_array($ability, $abilities, true)) throw new RuntimeException('FINANCIAL_PERMISSION_DEFINITION_REQUIRED');
    }
    $profiles = [];
    $rows = [];
    $accounts = 0;
    $mismatches = 0;
    $rules = app(\App\Services\Settings\AdminPermissionOverrides::class);
    \App\Models\User::withTrashed()->with(['roles.permissions', 'permissions'])
        ->chunkById(100, function ($users) use (&$profiles, &$rows, &$accounts, &$mismatches, $abilities, $explicitOnly, $rules) {
            foreach ($users as $user) {
                $grants = $user->getAllPermissions()->pluck('name')->sort()->values()->all();
                $admin = $user->hasRole('admin');
                $profile = hash('sha256', json_encode([$admin, $grants]));
                $selected = $admin || !isset($profiles[$profile]) ? $abilities : $explicitOnly;
                $profiles[$profile] = true;
                foreach ($selected as $ability) {
                    $expected = !$rules->denied($user, $ability)
                        && (($admin && !in_array($ability, $explicitOnly, true)) || in_array($ability, $grants, true));
                    $actual = $user->can($ability);
                    $rows[] = [$user->id, $ability, $actual, $expected];
                    if ($actual !== $expected) $mismatches++;
                }
                $accounts++;
            }
        });
    $raw = json_encode($rows);
    file_put_contents($workRoot . '/gate-capabilities-' . $mode . '-private.json', $raw);
    $report = ['success' => $mode === 'old' || $mismatches === 0, 'mode' => $mode,
        'accounts_checked' => $accounts, 'permission_profiles_checked' => count($profiles),
        'capability_checks' => count($rows), 'differences_from_upstream_gate_contract' => $mismatches,
        'capability_inventory_sha256' => hash('sha256', $raw),
        'database_writes_performed' => false, 'live_changed' => false, 'release_ready' => false];
    file_put_contents($workRoot . '/financial-gate-' . $mode . '-result.json', json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
    exit($report['success'] ? 0 : 1);
} catch (Throwable $error) {
    file_put_contents($workRoot . '/financial-gate-' . $mode . '-private-error.log', (string) $error);
    echo json_encode(['success' => false, 'exception_class' => get_class($error),
        'raw_details_withheld' => true, 'live_changed' => false]) . PHP_EOL;
    exit(1);
}

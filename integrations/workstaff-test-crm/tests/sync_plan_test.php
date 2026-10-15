<?php

require __DIR__ . '/../app/Services/Order/GpmOrderSyncPlan.php';

use App\Services\Order\GpmOrderSyncPlan;

function check($condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$base = ['price_per_hour' => 500, 'address' => 'Before', 'metro' => 'Before metro'];
$plan = GpmOrderSyncPlan::make($base, $base, $base, $base);
check($plan === ['to_app' => [], 'to_crm' => [], 'conflicts' => []], 'Idle sync must not write');

$crm = array_merge($base, ['price_per_hour' => 600]);
$plan = GpmOrderSyncPlan::make($base, $base, $crm, $base);
check($plan['to_app'] === ['price_per_hour' => 600] && !$plan['to_crm'], 'CRM edit must reach app');

$app = array_merge($base, ['price_per_hour' => 700]);
$plan = GpmOrderSyncPlan::make($base, $base, $base, $app);
check($plan['to_crm'] === ['price_per_hour' => 700] && !$plan['to_app'], 'App edit must reach CRM');

$plan = GpmOrderSyncPlan::make($base, $base, $crm, $app);
check($plan['to_crm'] === ['price_per_hour' => 700] && !$plan['to_app'], 'App must win a same-field conflict');
check($plan['conflicts'] === ['price_per_hour'], 'Conflict fields must be observable');

$app = array_merge($base, ['address' => 'App address']);
$plan = GpmOrderSyncPlan::make($base, $base, $crm, $app);
check($plan['to_crm'] === ['address' => 'App address'], 'Different fields must merge towards CRM');
check($plan['to_app'] === ['price_per_hour' => 600], 'Different fields must merge towards app');

$app = $crm;
$plan = GpmOrderSyncPlan::make($base, $base, $crm, $app);
check(!$plan['to_app'] && !$plan['to_crm'] && !$plan['conflicts'], 'Matching simultaneous changes need no writes');

$app = array_merge($base, ['metro' => '']);
$plan = GpmOrderSyncPlan::make($base, $base, $base, $app);
check(array_key_exists('metro', $plan['to_crm']) && $plan['to_crm']['metro'] === '', 'Clearing text must synchronize');

$app = array_merge($base, ['price_per_hour' => null]);
$plan = GpmOrderSyncPlan::make($base, $base, $base, $app);
check(array_key_exists('price_per_hour', $plan['to_crm']) && $plan['to_crm']['price_per_hour'] === null, 'Clearing a rate must synchronize');

// Recovery after app PATCH succeeds but CRM commit fails: the old baseline
// sees both changes and retains the already accepted app value.
$crm = array_merge($base, ['price_per_hour' => 600]);
$app = array_merge($base, ['price_per_hour' => 600, 'address' => 'App address']);
$plan = GpmOrderSyncPlan::make($base, $base, $crm, $app);
check($plan['to_crm'] === ['address' => 'App address'] && !$plan['to_app'], 'Interrupted merge must converge');

// Linked fields may have distinct CRM/app representations (staff rates).
// Their unchanged differences must never become an infinite echo loop.
$crmBase = ['price_regular' => 500];
$appBase = ['price_regular' => 650];
$plan = GpmOrderSyncPlan::make($crmBase, $appBase, $crmBase, $appBase);
check(!$plan['to_app'] && !$plan['to_crm'], 'Stable distinct representations must not echo');

$plan = GpmOrderSyncPlan::make($base, $base, $base, array_merge($base, ['status' => 'JUNK']));
check(!$plan['to_app'] && !$plan['to_crm'], 'Lifecycle must remain outside content sync');

echo "GPM sync planner: 11 scenarios passed\n";

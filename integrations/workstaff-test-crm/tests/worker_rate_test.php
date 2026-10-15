<?php
require __DIR__ . '/../worker-rate/app/Services/Order/GpmWorkerRateRules.php';
use App\Services\Order\GpmWorkerRateRules as Rules;

$count = 0;
function accepted($payload, $current, $status, $expected) {
    global $count;
    if (Rules::newRate($payload, $current, $status) !== $expected) { throw new RuntimeException('Wrong rate'); }
    $count++;
}
function rejected($payload, $current, $status, $expectedCode) {
    global $count;
    try { Rules::newRate($payload, $current, $status); }
    catch (DomainException $error) {
        if ($error->getCode() !== $expectedCode) { throw new RuntimeException('Wrong rejection'); }
        $count++;
        return;
    }
    throw new RuntimeException('Unexpected rate accepted');
}
$payload = ['workers_cost' => 650, 'expected_workers_cost' => 600];
accepted($payload, '600', 0, 650);
accepted($payload, 600, 2, 650);
accepted($payload, 650, 2, 650); // retry is a no-op even with the old baseline
accepted(['workers_cost' => '650', 'expected_workers_cost' => null], null, 0, 650);
rejected($payload, 700, 0, 409);
foreach ([3, 4, 5] as $status) { rejected($payload, 600, $status, 409); }
foreach (['address', 'customer_cost', 'status_id', 'logist_id'] as $field) {
    rejected($payload + [$field => 1], 600, 0, 422);
}
foreach ([0, -1, 100000001, true, '650.5', 'wrong'] as $rate) {
    rejected(['workers_cost' => $rate, 'expected_workers_cost' => 600], 600, 0, 422);
}
rejected(['workers_cost' => 650], 600, 0, 422);
rejected(['workers_cost' => 650, 'expected_workers_cost' => false], 600, 0, 422);
echo "GPM worker rate: $count scenarios passed\n";

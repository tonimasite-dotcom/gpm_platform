<?php
require __DIR__ . '/GpmCrewBridgePolicy.php';
use App\Services\Order\GpmCrewBridgePolicy as Policy;

function expect($value, $message) { if (!$value) throw new RuntimeException($message); }
function rejects(callable $action) {
    try { $action(); } catch (Throwable $error) { return; }
    throw new RuntimeException('Expected rejection');
}
expect(Policy::profileId(' #12 ') === '#12', 'saved ID normalization');
foreach ([null, '', '0', '#0', 'phone', '1x', '1000000000'] as $bad) {
    rejects(function () use ($bad) { Policy::profileId($bad); });
}
$base = [
    'protocol' => Policy::PROTOCOL, 'source_instance' => Policy::INSTANCE, 'order_id' => 'SYN/26',
    'revision_number' => 2, 'revision' => str_repeat('a',64), 'roster_fingerprint' => str_repeat('b',64),
    'rows' => [], 'proofs' => [],
];
expect(Policy::snapshot($base,'SYN/26') === $base, 'valid source');
rejects(function () use ($base) { Policy::snapshot($base,'OTHER'); });
$foreign = $base; $foreign['source_instance'] = 'https://other.example.test';
rejects(function () use ($foreign) { Policy::snapshot($foreign,'SYN/26'); });
$older = $base; $older['revision_number'] = 1; $older['revision'] = str_repeat('c',64);
expect(Policy::newer($base,$older,'SYN/26') === $base, 'late response cannot overwrite newer attendance');
$newer = $base; $newer['revision_number'] = 3;
expect(Policy::newer($base,$newer,'SYN/26') === $newer, 'newer attendance applies');
expect(Policy::newer($base,$base,'SYN/26') === $base, 'repeat is idempotent');
echo "Crew bridge policy checks passed\n";

<?php
require __DIR__ . '/GpmWorkerMatchPolicy.php';

use App\Services\Gpm\GpmWorkerMatchPolicy;

foreach ([
    '89999999977', '79999999977', '+79999999977',
    '+7 999 999 99 77', '+7 (999) 999-99-77', '8 (999) 999-99-77',
    '9999999977',
] as $raw) {
    if (GpmWorkerMatchPolicy::phone($raw) !== '+79999999977') {
        throw new RuntimeException('CRM phone formats must have one identity');
    }
}
foreach (['999', '+799999999770', '179999999977', '+49999999977', 'abc9999999977'] as $raw) {
    if (GpmWorkerMatchPolicy::phone($raw) !== null) {
        throw new RuntimeException('Invalid CRM phone must not match by suffix');
    }
}
echo "12 CRM phone format checks PASS\n";

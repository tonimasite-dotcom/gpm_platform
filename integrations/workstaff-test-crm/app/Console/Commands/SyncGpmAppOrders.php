<?php

namespace App\Console\Commands;

use App\Services\Order\GpmAppOrderSync;
use Illuminate\Console\Command;

class SyncGpmAppOrders extends Command
{
    protected $signature = 'gpm:sync-orders';
    protected $description = 'Synchronize linked test CRM orders with GPM';

    public function handle(GpmAppOrderSync $sync): int
    {
        if (!$sync->enabled()) {
            $this->info('GPM order synchronization is disabled for this installation.');
            return 0;
        }
        $result = $sync->syncLinkedOrders();
        $this->info('Synced: ' . $result['synced'] . '; deferred: ' . $result['deferred']);
        return $result['deferred'] ? 1 : 0;
    }
}

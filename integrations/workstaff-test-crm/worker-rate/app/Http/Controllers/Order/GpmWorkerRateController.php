<?php

namespace App\Http\Controllers\Order;

use App\Http\Controllers\Controller;
use App\Models\Branch;
use App\Models\Order;
use App\Services\Order\GpmWorkerRateRules;
use App\Services\Order\HistoryOrderService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class GpmWorkerRateController extends Controller
{
    public function __construct()
    {
        $this->middleware('can:read_logist_orders');
    }

    public function update(Request $request, int $order)
    {
        abort_unless(realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'
            && rtrim(config('app.url'), '/') === 'https://ts.workstaffcrm.ru', 404);
        $actor = $request->user();
        abort_unless($actor && $actor->can('read_logist_orders'), 403);
        abort_unless($actor->hasRole('logist') || $actor->can('update_logist_orders'), 403);
        $query = Order::whereKey($order);
        // Match the existing logist order list's ownership and city scope.
        if ((int) $actor->branch_id !== 0) {
            $cityId = optional(optional($actor->branch)->city)->id;
            abort_unless($cityId, 403);
            $query->whereIn('branch_id', Branch::whereHas('city', function ($query) use ($cityId) {
                $query->where('id', $cityId);
            })->pluck('id'));
        }
        if (optional($actor->roles->first())->name === 'logist') {
            $query->where('logist_id', $actor->id);
        }
        return DB::transaction(function () use ($query, $request) {
            $current = $query->lockForUpdate()->firstOrFail();
            try {
                $rate = GpmWorkerRateRules::newRate($request->all(), $current->workers_cost, (int) $current->status_id);
            } catch (\DomainException $error) {
                abort($error->getCode(), $error->getMessage());
            }
            if ($current->workers_cost === null || (int) $current->workers_cost !== $rate) {
                app(HistoryOrderService::class)->addUpdatedHistory($current, [
                    'work_type_id' => $current->work_type_id, 'workers_cost' => $rate,
                ]);
                $current->workers_cost = $rate;
                $current->save();
            }
            return response()->json(['workers_cost' => $rate]);
        });
    }
}

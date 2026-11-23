<?php
namespace App\Http\Controllers\Order;

use App\Http\Controllers\Controller;
use App\Models\Order;
use App\Services\Order\GpmCrewAttendanceService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;

class GpmCrewAttendanceController extends Controller
{
    public function handle(Request $request, string $operation)
    {
        $actor = $request->user();
        abort_unless($actor && $actor->hasAnyRole(['admin','head','logist']), 403);
        $validated = $request->validate(['order_id' => 'required|integer|exists:orders,id']);
        $order = Order::findOrFail($validated['order_id']);
        abort_unless($actor->hasAnyRole(['admin','head']) || (int) $order->logist_id === (int) $actor->id, 403);
        $service = app(GpmCrewAttendanceService::class);
        try {
            if ($operation === 'state') return response()->json($service->state($order, $actor));
            if ($operation === 'link') $service->link($order, $actor, $request->all());
            elseif ($operation === 'roster') {
                $service->roster($order, $actor, $request->input('apply_roster') === true,
                    (string) $request->input('expected_roster', ''));
            } elseif ($operation === 'enable') $service->enableOrder($order, $actor);
            elseif ($operation === 'review') $service->review($order, $actor, $request->all());
            else abort(404);
            return response()->json($service->state($order, $actor));
        } catch (\InvalidArgumentException $error) {
            return response()->json(['message' => $error->getMessage()], 422);
        } catch (\DomainException $error) {
            return response()->json(['message' => $error->getMessage()], (int) $error->getCode() ?: 409);
        } catch (\Throwable $error) {
            Log::warning('GPM attendance action deferred', [
                'order_id' => $order->id, 'operation' => $operation,
                'error_type' => get_class($error), 'error_code' => (int) $error->getCode(),
            ]);
            return response()->json(['message' => 'Нет связи с GPM. Отметки сохраняются на сервере, повторите позже.'], 503);
        }
    }
}

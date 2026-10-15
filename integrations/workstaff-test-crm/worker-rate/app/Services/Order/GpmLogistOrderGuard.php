<?php

namespace App\Services\Order;

/** CRM actor boundary only; background GPM sync has no authenticated CRM user. */
class GpmLogistOrderGuard
{
    public static function forbiddenFields(array $dirtyFields, array $roles): array
    {
        if (!in_array('logist', $roles, true)
            || array_intersect($roles, ['manager', 'admin', 'head'])) {
            return [];
        }
        return array_values(array_intersect($dirtyFields, [
            'address', 'city', 'street', 'house', 'flat', 'coords', 'metro_id',
            'customer_cost', 'customer_cost_nds', 'min_cost', 'min_cost_nds',
        ]));
    }
}

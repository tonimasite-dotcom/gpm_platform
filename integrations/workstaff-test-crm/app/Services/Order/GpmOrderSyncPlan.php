<?php

namespace App\Services\Order;

/** Field-wise three-way merge. App values win simultaneous changes. */
class GpmOrderSyncPlan
{
    public static function make(array $baseCrm, array $baseApp, array $crm, array $app): array
    {
        $toApp = [];
        $toCrm = [];
        $conflicts = [];
        foreach ($crm as $field => $value) {
            if (!array_key_exists($field, $app)) {
                continue;
            }
            $crmChanged = !array_key_exists($field, $baseCrm) || $value !== $baseCrm[$field];
            $appChanged = !array_key_exists($field, $baseApp) || $app[$field] !== $baseApp[$field];
            if ($appChanged) {
                if ($value !== $app[$field]) {
                    $toCrm[$field] = $app[$field];
                    if ($crmChanged) {
                        $conflicts[] = $field;
                    }
                }
            } elseif ($crmChanged && $value !== $app[$field]) {
                $toApp[$field] = $value;
            }
        }
        return ['to_app' => $toApp, 'to_crm' => $toCrm, 'conflicts' => $conflicts];
    }
}

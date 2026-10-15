<?php

namespace App\Services\Order;

/** Only one editable field; a stale form must not overwrite a newer rate. */
class GpmWorkerRateRules
{
    public static function newRate(array $payload, $current, int $status): int
    {
        if (array_diff(array_keys($payload), ['workers_cost', 'expected_workers_cost'])
            || !array_key_exists('workers_cost', $payload)
            || !array_key_exists('expected_workers_cost', $payload)) {
            throw new \DomainException('Only the worker rate can be changed', 422);
        }
        if (in_array($status, [3, 4, 5], true)) {
            throw new \DomainException('Closed CRM orders cannot be changed', 409);
        }
        $options = ['options' => ['min_range' => 1, 'max_range' => 100000000]];
        $rate = filter_var($payload['workers_cost'], FILTER_VALIDATE_INT, $options);
        if (is_bool($payload['workers_cost']) || $rate === false) {
            throw new \DomainException('The worker rate must be a positive integer', 422);
        }
        $expected = $payload['expected_workers_cost'];
        if ($expected !== null) {
            $expected = is_bool($expected) ? false : filter_var($expected, FILTER_VALIDATE_INT,
                ['options' => ['min_range' => 0, 'max_range' => 100000000]]);
            if ($expected === false) {
                throw new \DomainException('Invalid previous worker rate', 422);
            }
        }
        $current = $current === null ? null : (int) $current;
        if ($current !== $rate && $current !== $expected) {
            throw new \DomainException('Worker rate changed; refresh the page', 409);
        }
        return $rate;
    }
}

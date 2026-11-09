<?php

/** Classify the one proven additive audit effect without ignoring old rows. */
final class OriginalDataAcceptance
{
    public static function preserved(array $tables, ?array $audit): bool
    {
        if (count($tables) !== 72) return false;
        $changed = [];
        foreach ($tables as $name => $check) {
            if (($check['rows_unchanged'] ?? null) !== true || ($check['hash_unchanged'] ?? null) !== true) {
                $changed[] = $name;
            }
        }
        if (!$changed) return true;
        if ($changed !== ['activity_log'] || !$audit) return false;
        $check = $tables['activity_log'];
        $additional = $audit['additional_rows'] ?? [];
        if (!is_int($check['rows_before']) || !is_int($check['rows_after'])
            || $check['rows_before'] < 0 || !$additional
            || count($additional) !== $check['rows_after'] - $check['rows_before']
            || ($audit['original_prefix_rows'] ?? null) !== $check['rows_before']
            || ($audit['original_prefix_hash_unchanged'] ?? null) !== true
            || ($audit['cash_source_migration_recorded'] ?? null) !== true
            || ($audit['one_to_one_source_mapping'] ?? null) !== true
            || ($audit['frozen_cash_source_count'] ?? null) !== count($additional)) {
            return false;
        }
        foreach ($additional as $row) {
            if (($row['legacy_cash_capture_verified'] ?? null) !== true
                || ($row['causer_present'] ?? null) !== false
                || ($row['subject_present'] ?? null) !== false
                || ($row['log_name'] ?? null) !== 'finance'
                || ($row['description'] ?? null) !== 'cash_source_captured'
                || ($row['property_sections'] ?? null) !== ['cash_source']) {
                return false;
            }
        }
        return true;
    }
}

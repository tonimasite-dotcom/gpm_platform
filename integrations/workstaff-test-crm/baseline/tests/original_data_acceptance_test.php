<?php
require __DIR__ . '/../payload/OriginalDataAcceptance.php';

$tables = ['activity_log' => ['rows_before' => 10, 'rows_after' => 11,
    'rows_unchanged' => false, 'hash_unchanged' => false]];
for ($i = 0; $i < 71; $i++) {
    $tables['old_table_' . $i] = ['rows_before' => 3, 'rows_after' => 3,
        'rows_unchanged' => true, 'hash_unchanged' => true];
}
$audit = ['original_prefix_rows' => 10, 'original_prefix_hash_unchanged' => true,
    'cash_source_migration_recorded' => true, 'one_to_one_source_mapping' => true,
    'frozen_cash_source_count' => 1, 'additional_rows' => [[
        'legacy_cash_capture_verified' => true, 'causer_present' => false, 'subject_present' => false,
        'log_name' => 'finance', 'description' => 'cash_source_captured', 'property_sections' => ['cash_source']]]];
$cases = [];
$cases['verified_additive_capture'] = [$tables, $audit, true];
$t = $tables; $t['old_table_0']['hash_unchanged'] = false;
$cases['changed_old_business_value'] = [$t, $audit, false];
$t = $tables; $t['old_table_0']['rows_unchanged'] = false;
$cases['changed_old_business_count'] = [$t, $audit, false];
$a = $audit; $a['original_prefix_hash_unchanged'] = false;
$cases['changed_old_audit_value'] = [$tables, $a, false];
$a = $audit; $a['original_prefix_rows'] = 9;
$cases['lost_old_audit_row'] = [$tables, $a, false];
$a = $audit; $a['additional_rows'][0]['description'] = 'unrelated_event';
$cases['unrelated_new_audit_event'] = [$tables, $a, false];
$a = $audit; $a['additional_rows'][0]['legacy_cash_capture_verified'] = false;
$cases['mismatched_source_amount_or_identity'] = [$tables, $a, false];
$a = $audit; $a['additional_rows'][0]['causer_present'] = true;
$cases['unexpected_actor'] = [$tables, $a, false];
$a = $audit; $a['additional_rows'][0]['property_sections'][] = 'other';
$cases['unexpected_extra_properties'] = [$tables, $a, false];
$a = $audit; $a['one_to_one_source_mapping'] = false;
$cases['duplicate_audit_for_source'] = [$tables, $a, false];
$a = $audit; $a['additional_rows'][] = $a['additional_rows'][0];
$cases['unaccounted_audit_count'] = [$tables, $a, false];
$a = $audit; $a['frozen_cash_source_count'] = 2;
$cases['unaccounted_frozen_source'] = [$tables, $a, false];
$a = $audit; $a['cash_source_migration_recorded'] = false;
$cases['missing_provenance_migration'] = [$tables, $a, false];
$t = $tables; unset($t['old_table_0']);
$cases['incomplete_original_table_set'] = [$t, $audit, false];
$cases['missing_audit_evidence'] = [$tables, null, false];
$t = $tables; $t['activity_log']['rows_after'] = 10;
$t['activity_log']['rows_unchanged'] = true; $t['activity_log']['hash_unchanged'] = true;
$cases['all_tables_exactly_unchanged'] = [$t, null, true];
foreach ($cases as $name => $case) {
    if (OriginalDataAcceptance::preserved($case[0], $case[1]) !== $case[2]) {
        fwrite(STDERR, 'FAILED: ' . $name . PHP_EOL);
        exit(1);
    }
}
echo 'Original data acceptance: ' . count($cases) . ' scenarios passed' . PHP_EOL;

<?php
use App\Models\User;
use App\Services\Document\GenerateDocumentService;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;

$app = null;
$work = '/root/gpm-ts-update/20261106-baseline-01';
$current = 'bootstrap';
$originalPublic = null;
$started = microtime(true);

function documentAssert($condition): void {
    if (!$condition) throw new RuntimeException('DOCUMENT_ASSERTION_FAILED');
}

try {
    $app = require __DIR__ . '/private_runtime_bootstrap.php';
    $fixture = getenv('GPM_TS_DOCUMENT_FIXTURE');
    documentAssert(is_string($fixture) && preg_match('#^' . preg_quote($work, '#') . '/document-fixtures-20261109-[a-f0-9]{12}$#D', $fixture)
        && realpath($fixture) === $fixture && is_dir($fixture . '/public')
        && getenv('XDG_CONFIG_HOME') === $fixture . '/config' && getenv('TMPDIR') === $fixture . '/tmp');
    $originalPublic = $app->make('path.public');
    $app->instance('path.public', $fixture . '/public');
    config(['filesystems.default' => 'private_document_fixture',
        'filesystems.disks.private_document_fixture' => ['driver' => 'local', 'root' => $fixture . '/storage/app']]);
    documentAssert(mkdir($fixture . '/storage/app/public/document_templates', 0700, true));
    documentAssert(symlink($fixture . '/storage/app/public', $fixture . '/public/storage'));
    $template = $work . '/file-recovery-20261109/tree/storage/app/public/document_templates/accountant.docx';
    documentAssert(realpath($template) === $template && is_file($template));
    documentAssert(copy($template, $fixture . '/storage/app/public/document_templates/accountant.docx'));
    chdir($fixture . '/public');
    DB::beginTransaction();
    $current = 'synthetic_fixture';
    $tag = bin2hex(random_bytes(8));
    $actorId = DB::table('users')->insertGetId(['surname' => 'Synthetic', 'first_name' => 'Document',
        'email' => 'private-document-' . $tag . '@example.invalid', 'password' => Hash::make(bin2hex(random_bytes(24))),
        'branch_id' => 0, 'active' => 1, 'created_at' => now(), 'updated_at' => now()]);
    $actor = User::findOrFail($actorId);
    $actor->assignRole(Spatie\Permission\Models\Role::findByName('head', 'api'));
    $app['auth']->guard()->setUser($actor);
    // Issuer requisites and template come from the existing private ts copy, read-only.
    // Outputs remain private because they contain these real ts issuer requisites.
    $choices = app(App\Services\Document\DocumentOrganizationService::class)->choices();
    documentAssert(count($choices) > 0);
    $branchId = $choices[0]['id'];
    $customerId = DB::table('customers')->insertGetId(['company_name' => 'PRIVATE SYNTHETIC CUSTOMER ' . $tag,
        'branch_id' => $branchId, 'created_at' => now(), 'updated_at' => now()]);
    $data = ['doc_type' => App\Models\Documents\DocumentLink::ACCOUNT, 'branch_id' => $branchId,
        'customer_id' => $customerId, 'is_img' => 0, 'date' => '2026-11-09', 'doc_number' => 'PRIVATE-' . $tag,
        'services' => [['work_type' => 'PRIVATE SYNTHETIC SERVICE', 'count' => 1, 'unit' => 'hour',
            'cost' => 1234.56, 'total_cost' => 1234.56]]];
    $current = 'real_invoice_generation';
    $result = app(GenerateDocumentService::class)->generate($data);
    $current = 'generated_files';
    $files = [];
    foreach (['word', 'pdf', 'word_noimg', 'pdf_noimg'] as $kind) {
        $field = str_starts_with($kind, 'word') ? 'storage_word' : 'storage_pdf';
        $relative = $result[$kind][$field] ?? null;
        documentAssert(is_string($relative) && !str_contains($relative, '..'));
        $path = $fixture . '/storage/app/' . $relative;
        documentAssert(realpath($path) === $path && is_file($path) && filesize($path) > 100);
        if (str_starts_with($kind, 'pdf')) {
            documentAssert(file_get_contents($path, false, null, 0, 5) === '%PDF-');
        } else {
            $zip = new ZipArchive();
            documentAssert($zip->open($path) === true);
            $xml = $zip->getFromName('word/document.xml');
            $zip->close();
            documentAssert(is_string($xml) && strpos($xml, 'PRIVATE SYNTHETIC SERVICE') !== false);
            documentAssert(strpos($xml, '${') === false);
        }
        $files[$kind] = ['bytes' => filesize($path), 'sha256' => hash_file('sha256', $path)];
    }
    $current = 'document_history_and_code';
    $document = $result['document'];
    documentAssert($document && (int)$document->customer_id === $customerId);
    documentAssert(DB::table('document_payment_codes')->where('document_id', $document->id)->count() === 1);
    $documentId = $document->id;
    while (DB::transactionLevel() > 0) DB::rollBack();
    documentAssert(!DB::table('document_links')->where('id', $documentId)->exists());
    documentAssert(!DB::table('customers')->where('id', $customerId)->exists());
    documentAssert(!DB::table('users')->where('id', $actorId)->exists());
    $report = ['success' => true, 'real_invoice_generator_used' => true, 'real_restored_ts_template_used' => true,
        'local_libreoffice_used' => true, 'existing_ts_issuer_read_only' => true, 'synthetic_customer_and_services' => true,
        'four_document_files_verified' => $files, 'payment_code_reserved_once' => true,
        'all_synthetic_database_transactions_rolled_back' => true,
        'files_contain_private_ts_requisites_and_remain_private' => true, 'mail_or_external_api_called' => false,
        'live_crm_changed' => false, 'browser_acceptance_completed' => false, 'release_ready' => false,
        'elapsed_seconds' => round(microtime(true) - $started, 3)];
    file_put_contents($work . '/document-acceptance-20261109.json', json_encode($report, JSON_PRETTY_PRINT));
    echo json_encode($report) . PHP_EOL;
} catch (Throwable $error) {
    if ($app) while (DB::transactionLevel() > 0) DB::rollBack();
    file_put_contents($work . '/document-private-error.log', (string)$error);
    $report = ['success' => false, 'failed_stage' => $current, 'exception_type' => get_class($error),
        'raw_details_withheld' => true, 'live_crm_changed' => false];
    if ($error instanceof Illuminate\Validation\ValidationException) $report['validation_fields'] = array_keys($error->errors());
    echo json_encode($report) . PHP_EOL;
    exit(1);
} finally {
    if ($app && $originalPublic) $app->instance('path.public', $originalPublic);
}

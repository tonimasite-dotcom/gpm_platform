<?php
// Run only in the synthetic chroot inside a network namespace, without live DB.
require '/work/crm-private-01/vendor/autoload.php';
$app = require '/work/crm-private-01/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
set_exception_handler(static function (Throwable $error): never {
    fwrite(STDERR, get_class($error) . ':' . $error->getMessage() . "\n");
    exit(1);
});

use App\Services\Release\GpmTsDemoPolicy as Policy;
use App\Services\Release\GpmTsDemoTransport;
use Illuminate\Support\Facades\Mail;
use Symfony\Component\Mime\Email;

$checks = [];
$databaseQueries = 0;
Illuminate\Support\Facades\DB::listen(static function () use (&$databaseQueries): void { $databaseQueries++; });
function verifyDemo13(string $name, bool $condition): void {
    global $checks;
    if (!$condition) { throw new RuntimeException('DEMO13_ASSERTION:' . $name); }
    $checks[] = $name;
}
verifyDemo13('synthetic_context', app()->environment('testing')
    && config('database.connections.mysql.database') === 'bot_fixture'
    && is_file(base_path('PRIVATE_BOT_FIXTURE')));
verifyDemo13('default_is_demo', config('mail.default') === 'gpm_ts_demo');
verifyDemo13('broadcasts_disabled', config('broadcasting.default') === 'null');
verifyDemo13('general_scheduler_has_no_events', count(app(Illuminate\Console\Scheduling\Schedule::class)->events()) === 0);
verifyDemo13('symfony_transport', Mail::mailer()->getSymfonyTransport() instanceof GpmTsDemoTransport);
$message = (new Email())->from('sender@example.invalid')->to('fixture@example.invalid')
    ->subject('Synthetic')->text('Synthetic fixture');
verifyDemo13('direct_transport_suppressed', (new GpmTsDemoTransport())->send($message) === null);
verifyDemo13('facade_mail_suppressed', Mail::raw('Synthetic', static function ($mail) {
    $mail->from('sender@example.invalid')->to('fixture@example.invalid')->subject('Synthetic');
}) === null);
foreach (['imap', 'sms', 'bank', 'calls', 'dadata', 'geocode'] as $channel) {
    try { Policy::deny($channel); throw new RuntimeException('CHANNEL_NOT_BLOCKED'); }
    catch (Symfony\Component\HttpKernel\Exception\HttpException $error) {
        verifyDemo13($channel . '_denied', $error->getStatusCode() === 409);
    }
}
try { Policy::suppress('unknown'); throw new RuntimeException('UNKNOWN_ACCEPTED'); }
catch (InvalidArgumentException $error) { verifyDemo13('unknown_channel_rejected', true); }
foreach (['CheckDebit', 'CheckCustomerDebit', 'ParseEmailLead', 'RefreshBankingToken',
    'CheckWorkerIsActive', 'setStatementsAndGetTransactionsFromApi',
    'DebitCalculate', 'DebitNotify', 'DebitRemindersDryRun'] as $name) {
    // Unit invocation of the already guarded method, never Artisan/scheduler/cron.
    $command = (new ReflectionClass('App\\Console\\Commands\\' . $name))->newInstanceWithoutConstructor();
    verifyDemo13($name . '_stops_before_background_work', $command->handle() === 0);
}
$debtorClient = (new ReflectionClass(App\Services\WebKlexMailClient::class))->newInstanceWithoutConstructor();
$document = (new ReflectionClass(App\Models\Documents\DocumentLink::class))->newInstanceWithoutConstructor();
verifyDemo13('verified_debtor_mail_rejected_before_attachment_work', $debtorClient->sendVerifiedDebitMessage('fixture@example.invalid', $document, 100, []) === 'rejected');
verifyDemo13('partial_payment_mail_rejected_before_attachment_work', $debtorClient->sendPartialPaymentInquiry('fixture@example.invalid', $document, []) === 'rejected');
foreach (['send', 'sendManual'] as $method) {
    try {
        $workerMail = app(App\Services\Order\OrderWorkerMailService::class);
        $method === 'send' ? $workerMail->send(123) : $workerMail->sendManual(['order_id' => 123, 'selected' => [456]]);
        throw new RuntimeException('WORKER_MAIL_NOT_BLOCKED');
    } catch (Symfony\Component\HttpKernel\Exception\HttpException $error) {
        verifyDemo13('worker_mail_' . $method . '_blocked_before_state_changes', $error->getStatusCode() === 409);
    }
}
$url = config('app.url');
config(['app.url' => 'https://workstaffcrm.ru']);
try { Policy::assertContext(); throw new RuntimeException('MAIN_ACCEPTED'); }
catch (RuntimeException $error) { verifyDemo13('main_identity_rejected', $error->getMessage() === 'GPM_TS_DEMO_CONTEXT_REQUIRED'); }
config(['app.url' => $url]);

// Loopback-only SMTP exists solely in the runner's isolated network namespace.
$server = stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
verifyDemo13('synthetic_smtp_listener', is_resource($server));
$port = (int) substr(strrchr(stream_socket_get_name($server, false), ':'), 1);
$child = pcntl_fork();
if ($child === -1) { throw new RuntimeException('SMTP_FORK_FAILED'); }
if ($child === 0) {
    $connection = stream_socket_accept($server, 8);
    if (!$connection) { exit(21); }
    stream_set_timeout($connection, 5);
    fwrite($connection, "220 synthetic ESMTP\r\n");
    $messages = 0; $recipient = false; $body = ''; $data = false;
    while (($line = fgets($connection)) !== false) {
        if ($data) {
            if (rtrim($line, "\r\n") === '.') {
                $messages++; $data = false; fwrite($connection, "250 accepted\r\n");
            } else { $body .= $line; }
            continue;
        }
        $command = strtoupper(strtok($line, ' '));
        if (str_starts_with($command, 'EHLO') || str_starts_with($command, 'HELO')) {
            fwrite($connection, "250-synthetic\r\n250 8BITMIME\r\n");
        } elseif ($command === 'RCPT') {
            $recipient = str_contains($line, 'fixture@example.invalid');
            fwrite($connection, "250 recipient\r\n");
        } elseif (str_starts_with($command, 'DATA')) {
            $data = true; fwrite($connection, "354 data\r\n");
        } elseif (str_starts_with($command, 'QUIT')) {
            fwrite($connection, "221 bye\r\n"); break;
        } else { fwrite($connection, "250 ok\r\n"); }
    }
    fclose($connection); fclose($server);
    $decoded = quoted_printable_decode($body);
    if (stripos($body, 'Content-Transfer-Encoding: base64') !== false) {
        $parts = preg_split('/\r?\n\r?\n/', $body, 2);
        $decoded = base64_decode($parts[1] ?? '', true) ?: '';
    }
    exit($messages === 1 && $recipient && str_contains($decoded, 'SYNTHETIC-CODE-ONLY') ? 0 : 22);
}
fclose($server);
$mailer = null;
try {
    $smtpConfig = ['host' => '127.0.0.1', 'port' => $port,
        'encryption' => '', 'username' => '', 'password' => ''];
    $mailer = Policy::loginMailer($smtpConfig);
    verifyDemo13('separate_login_mailer', $mailer !== Mail::mailer());
    $smtpConfig['username'] = 'sender@example.invalid';
    $client = (new ReflectionClass(App\Services\WebKlexMailClient::class))->newInstanceWithoutConstructor();
    (new ReflectionProperty($client, 'config'))->setValue($client, $smtpConfig);
    $sent = $client->sendVerifyMessage((object) ['email' => 'fixture@example.invalid', 'remember_token' => 'SYNTHETIC-CODE-ONLY']);
    verifyDemo13('existing_login_helper_delivers_template_to_fake_smtp', $sent === true);
} finally {
    if ($mailer !== null) { $mailer->getSymfonyTransport()->stop(); }
    pcntl_waitpid($child, $status);
}
verifyDemo13('fake_smtp_verified_recipient_body_and_single_message', pcntl_wifexited($status) && pcntl_wexitstatus($status) === 0);
verifyDemo13('global_mailer_still_suppressed', Mail::mailer()->getSymfonyTransport() instanceof GpmTsDemoTransport);
$tlsMailer = Policy::loginMailer(['host' => '127.0.0.1', 'port' => $port,
    'encryption' => 'tls', 'username' => '', 'password' => '']);
verifyDemo13('configured_tls_is_required', (new ReflectionProperty($tlsMailer->getSymfonyTransport(), 'requireTls'))->getValue($tlsMailer->getSymfonyTransport()) === true);
verifyDemo13('ordinary_mail_still_blocked_after_login', Mail::raw('Synthetic', static function ($mail) {
    $mail->from('sender@example.invalid')->to('fixture@example.invalid')->subject('Synthetic');
}) === null);
verifyDemo13('no_database_queries_during_demo_acceptance', $databaseQueries === 0);
echo json_encode(['status' => 'PASS', 'checks' => $checks, 'scenarios' => count($checks),
    'smtp' => 'isolated_loopback_fixture', 'production_database_used' => false,
    'live_files_changed' => false]);

<?php
namespace App\Services\Release;

use Illuminate\Mail\Events\MessageSending;
use Illuminate\Foundation\Http\Events\RequestHandled;
use Illuminate\Support\Facades\Mail;
use Symfony\Component\HttpKernel\Exception\HttpException;

/** TS-only: ordinary mail is blocked; login mail uses a separate local mailer. */
final class GpmTsDemoPolicy
{
    public const LIVE = '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru';
    public const PRIVATE_ROOT = '/root/gpm-ts-update/20261110-demo-06/runtime';
    public const VERSION = 'ts-demo-20261110-06';
    public const URL = 'https://ts.workstaffcrm.ru';
    private const CHANNELS = ['daily_mail', 'mail', 'imap', 'sms', 'bank', 'calls', 'dadata', 'geocode', 'background'];

    public static function assertContext(): void
    {
        $root = realpath(base_path());
        if (rtrim((string) config('app.url'), '/') !== self::URL) {
            throw new \RuntimeException('GPM_TS_DEMO_IDENTITY_MISMATCH');
        }
        if ($root === self::LIVE) { return; }
        $privateDatabase = config('database.default') === 'forbidden'
            || (config('database.default') === 'mysql'
                && config('database.connections.mysql.unix_socket') === '/root/gpm-ts-update/20261106-baseline-01/sql-recovery-20261109/rehearsal-mysql/mysql.sock'
                && config('database.connections.mysql.database') === 'gpm_ts_backup_20261109'
                && config('database.connections.mysql.username') === 'gpm_ts_backup_recovery');
        if ($root === self::PRIVATE_ROOT && PHP_SAPI === 'cli' && $privateDatabase
            && getenv('GPM_TS_DEMO_REHEARSAL') === '1'
            && is_file($root . '/PRIVATE_DEMO_NO_DATABASE')
            && readlink('/proc/self/ns/net') !== readlink('/proc/1/ns/net')) { return; }
        throw new \RuntimeException('GPM_TS_DEMO_CONTEXT_REQUIRED');
    }

    public static function suppress(string $channel): void
    {
        self::assertContext();
        if (!in_array($channel, self::CHANNELS, true)) { throw new \InvalidArgumentException('UNKNOWN_DEMO_CHANNEL'); }
        // No recipients, bodies, codes, credentials, request URLs or bank data.
        app('log')->info('GPM_TS_DEMO_SUPPRESSED', ['channel' => $channel, 'delivered' => false]);
    }

    public static function deny(string $channel): void
    {
        self::suppress($channel);
        throw new HttpException(409, 'Р”РµРјРѕРЅСЃС‚СЂР°С†РёРѕРЅРЅС‹Р№ СЂРµР¶РёРј TS: РІРЅРµС€РЅСЏСЏ РѕРїРµСЂР°С†РёСЏ РѕС‚РєР»СЋС‡РµРЅР°.');
    }

    public static function installNullMailer(): bool
    {
        self::assertContext();
        Mail::setSwiftMailer(new \Swift_Mailer(new GpmTsDemoTransport()));
        return true;
    }

    /** Not registered in the container or Mail facade: only sendVerifyMessage uses it. */
    public static function loginMailer(array $config): \Illuminate\Mail\Mailer
    {
        self::assertContext();
        $transport = (new \Swift_SmtpTransport($config['host'], $config['port'], $config['encryption']))
            ->setUsername($config['username'])->setPassword($config['password'])->setTimeout(3);
        // Independent events: the ordinary mail cancellation remains installed globally.
        // No credentials, recipients, body or code are logged or stored here.
        return new \Illuminate\Mail\Mailer('gpm_ts_login_only', app('view'),
            new \Swift_Mailer($transport), new \Illuminate\Events\Dispatcher(app()));
    }

    public static function register($app): void
    {
        self::assertContext();
        // Override the default at runtime; never modify stored SMTP credentials.
        $app['config']->set('mail.default', 'gpm_ts_demo');
        $app['config']->set('mail.driver', 'gpm_ts_demo');
        $app['config']->set('mail.mailers.gpm_ts_demo', ['transport' => 'gpm_ts_demo']);
        // Local notifications remain local; Pusher is a separate paid transport.
        $app['config']->set('broadcasting.default', 'null');
        $app['mail.manager']->extend('gpm_ts_demo', static function () {
            return new GpmTsDemoTransport();
        });
        $app['events']->listen(MessageSending::class, static function () {
            self::suppress('mail');
            return false;
        });
        $app['events']->listen(RequestHandled::class, static function ($event) {
            $event->response->headers->set('X-GPM-TS-Demo', self::VERSION);
        });
    }
}

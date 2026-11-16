<?php
namespace App\Services\Release;

use Illuminate\Foundation\Http\Events\RequestHandled;
use Illuminate\Mail\Events\MessageSending;
use Symfony\Component\HttpKernel\Exception\HttpException;

/** Laravel 13 mail isolation. Login delivery gets its own unregistered mailer. */
final class GpmTsDemoPolicy
{
    public const VERSION = 'ts-demo-laravel13-20261116-01';
    private const CHANNELS = ['daily_mail', 'mail', 'imap', 'sms', 'bank', 'calls', 'dadata', 'geocode', 'background'];

    public static function assertContext(): void
    {
        if (!GpmTsBotContext::matches()) {
            throw new \RuntimeException('GPM_TS_DEMO_CONTEXT_REQUIRED');
        }
    }

    public static function suppress(string $channel): void
    {
        self::assertContext();
        if (!in_array($channel, self::CHANNELS, true)) {
            throw new \InvalidArgumentException('UNKNOWN_DEMO_CHANNEL');
        }
        app('log')->info('GPM_TS_DEMO_SUPPRESSED', ['channel' => $channel, 'delivered' => false]);
    }

    public static function deny(string $channel): never
    {
        self::suppress($channel);
        throw new HttpException(409, 'External operation disabled in TS demo mode.');
    }

    public static function installNullMailer(): bool
    {
        self::assertContext();
        app('mail.manager')->mailer()->setSymfonyTransport(new GpmTsDemoTransport());
        return true;
    }

    /** Only the existing sendVerifyMessage may call this method. */
    public static function loginMailer(array $config): \Illuminate\Mail\Mailer
    {
        self::assertContext();
        $encryption = strtolower((string) ($config['encryption'] ?? ''));
        if (!in_array($encryption, ['', 'tls', 'ssl', 'smtps', 'starttls'], true)) {
            throw new \InvalidArgumentException('UNSUPPORTED_LOGIN_SMTP_ENCRYPTION');
        }
        $transport = app('mail.manager')->createSymfonyTransport([
            'transport' => 'smtp',
            'scheme' => in_array($encryption, ['ssl', 'smtps'], true) ? 'smtps' : 'smtp',
            'host' => $config['host'],
            'port' => (int) $config['port'],
            'username' => $config['username'],
            'password' => $config['password'],
            'timeout' => 3,
        ]);
        if (in_array($encryption, ['tls', 'starttls'], true)) {
            $transport->setRequireTls(true);
        }
        // Do not share MessageSending listeners or register this mailer globally.
        return new \Illuminate\Mail\Mailer('gpm_ts_login_only', app('view'),
            $transport, new \Illuminate\Events\Dispatcher(app()));
    }

    public static function register($app): void
    {
        self::assertContext();
        $app['config']->set('mail.default', 'gpm_ts_demo');
        $app['config']->set('mail.mailers.gpm_ts_demo', ['transport' => 'gpm_ts_demo']);
        $app['config']->set('broadcasting.default', 'null');
        $app['mail.manager']->extend('gpm_ts_demo', static fn () => new GpmTsDemoTransport());
        $app['mail.manager']->forgetMailers();
        $app['events']->listen(MessageSending::class, static function () {
            self::suppress('mail');
            return false;
        });
        $app['events']->listen(RequestHandled::class, static function ($event) {
            $event->response->headers->set('X-GPM-TS-Demo', self::VERSION);
        });
    }
}

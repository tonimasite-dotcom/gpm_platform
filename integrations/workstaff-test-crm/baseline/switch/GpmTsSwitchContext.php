<?php
namespace App\Services\Release;

use Illuminate\Support\Facades\DB;

/** Only the explicit new private switch runtime. No live environment is accepted. */
final class GpmTsSwitchContext
{
    public const WORK = '/root/gpm-ts-update/20261109-switch-01';
    public const ROOT = self::WORK . '/runtime';

    public static function version(): string
    {
        $marker = self::ROOT . '/.gpm-switch-version';
        if (PHP_SAPI !== 'cli' || getenv('GPM_TS_SWITCH') !== '1' || getenv('GPM_TS_REHEARSAL') !== '1'
            || realpath(base_path()) !== self::ROOT || realpath($marker) !== $marker || !is_file($marker)
            || !is_file(storage_path('framework/down'))
            || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')) {
            throw new \RuntimeException('PRIVATE_SWITCH_RUNTIME_REQUIRED');
        }
        $version = trim(file_get_contents($marker));
        if (!in_array($version, ['old', 'new'], true)) throw new \RuntimeException('PRIVATE_SWITCH_VERSION_REQUIRED');
        return $version;
    }

    public static function expected(string $version): array
    {
        if (!in_array($version, ['old', 'new'], true)) throw new \RuntimeException('PRIVATE_SWITCH_VERSION_REQUIRED');
        $generation = self::ROOT . '/.gpm-switch-generation';
        $final = false;
        if ($version === 'new' && file_exists($generation)) {
            if (realpath($generation) !== $generation || !is_file($generation)
                || trim(file_get_contents($generation)) !== 'final') {
                throw new \RuntimeException('PRIVATE_SWITCH_GENERATION_REQUIRED');
            }
            $final = true;
        }
        return ['database' => $version === 'old' ? 'gpm_ts_backup_20261109' : ($final ? 'gpm_ts_switch_final' : 'gpm_ts_switch_new'),
            'username' => $version === 'old' ? 'gpm_ts_switch_old' : ($final ? 'gpm_ts_switch_final' : 'gpm_ts_switch_new'),
            'unix_socket' => self::WORK . '/mysql-' . $version . '/mysql.sock',
            'datadir' => self::WORK . '/mysql-' . $version . '/data'];
    }

    public static function assertRuntime(): string
    {
        $version = self::version();
        $expected = self::expected($version);
        if (config('database.default') !== 'mysql' || config('app.env') !== 'testing'
            || config('database.connections.mysql.driver') !== 'mysql'
            || config('database.connections.mysql.host') !== 'localhost'
            || config('database.connections.mysql.database') !== $expected['database']
            || config('database.connections.mysql.username') !== $expected['username']
            || config('database.connections.mysql.unix_socket') !== $expected['unix_socket']
            || realpath($expected['unix_socket']) !== $expected['unix_socket']
            || config('cache.default') !== 'array' || config('session.driver') !== 'array'
            || config('gpm_app_order_sync.enabled') === true
            || !in_array(config('mail.default'), ['log', null], true)) {
            throw new \RuntimeException('PRIVATE_SWITCH_CONFIG_REQUIRED');
        }
        // Every path/config/network check is complete before the first DB connection.
        $row = DB::selectOne('SELECT DATABASE() AS db, CURRENT_USER() AS account,
            @@datadir AS datadir, @@skip_networking AS isolated, VERSION() AS version');
        if ($row->db !== $expected['database'] || $row->account !== $expected['username'] . '@localhost'
            || realpath($row->datadir) !== $expected['datadir'] || (int)$row->isolated !== 1
            || strpos($row->version, '5.7.') !== 0) {
            throw new \RuntimeException('PRIVATE_SWITCH_DATABASE_REQUIRED');
        }
        DB::statement('SET SESSION lock_wait_timeout=15');
        return $version;
    }

    public static function assertUpgrade(): void
    {
        if (self::assertRuntime() !== 'new') throw new \RuntimeException('PRIVATE_SWITCH_NEW_VERSION_REQUIRED');
    }
}

<?php
namespace App\Services\Release;

use Illuminate\Support\Facades\DB;

/** Strictly private rehearsal context. Deliberately has NO live apply mode. */
final class GpmTsRehearsal
{
    public const ROOT = '/root/gpm-ts-update/20261106-baseline-01/candidate';
    public const DATA = '/root/gpm-ts-update/20261106-baseline-01/rehearsal-mysql/data';
    public const SOCKET = '/root/gpm-ts-update/20261106-baseline-01/rehearsal-mysql/mysql.sock';

    public static function isCandidate(): bool
    {
        return PHP_SAPI === 'cli' && getenv('GPM_TS_REHEARSAL') === '1'
            && realpath(base_path()) === self::ROOT
            && rtrim((string) config('app.url'), '/') === 'https://ts.workstaffcrm.ru'
            && config('database.connections.mysql.unix_socket') === self::SOCKET
            && config('database.connections.mysql.database') === 'gpm_ts_rehearsal_20261106'
            && config('database.connections.mysql.username') === 'gpm_ts_rehearsal';
    }

    public static function assertContext(): void
    {
        if (!self::isCandidate() || !is_file(storage_path('framework/down'))
            || readlink('/proc/self/ns/net') === readlink('/proc/1/ns/net')) {
            throw new \RuntimeException('GPM_TS_PRIVATE_REHEARSAL_REQUIRED');
        }
        // All configuration/path checks precede the first DB connection.
        $row = DB::selectOne('SELECT DATABASE() AS db, CURRENT_USER() AS account, @@datadir AS datadir');
        if ($row->db !== 'gpm_ts_rehearsal_20261106'
            || explode('@', $row->account)[0] !== 'gpm_ts_rehearsal'
            || realpath($row->datadir) !== self::DATA) {
            throw new \RuntimeException('GPM_TS_PRIVATE_DATABASE_REQUIRED');
        }
        $version = (string) (DB::selectOne('SELECT VERSION() AS v')->v ?? '');
        if (strpos($version, '5.7.') !== 0) {
            throw new \RuntimeException('GPM_TS_REHEARSAL_MYSQL_VERSION');
        }
        DB::statement('SET SESSION lock_wait_timeout=15');
    }
}

<?php
namespace App\Services\Release;

/** Explicit live TS identity or the separately verified private rehearsal. */
final class GpmTsRuntimeContext
{
    public static function isTsOrPrivateRehearsal(): bool
    {
        if (realpath(base_path()) === '/var/www/gruzpiter/data/www/ts.workstaffcrm.ru'
            && rtrim((string)config('app.url'), '/') === 'https://ts.workstaffcrm.ru') {
            return true;
        }
        if (class_exists(GpmTsRehearsal::class) && GpmTsRehearsal::isCandidate()) {
            GpmTsRehearsal::assertContext();
            return true;
        }
        return false;
    }
}

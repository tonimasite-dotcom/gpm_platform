<?php
namespace App\Services\Release;

/** Explicit old/new private contexts; no production-path imitation. */
final class GpmTsRuntimeContext
{
    public static function isTsOrPrivateRehearsal(): bool
    {
        if (getenv('GPM_TS_REHEARSAL') !== '1') return false;
        GpmTsSwitchContext::assertRuntime();
        return true;
    }
}

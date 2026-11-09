<?php
namespace App\Services\Release;

/** Adapter for the copied migration package, strictly the NEW private switch DB. */
final class GpmTsRehearsal
{
    public static function isCandidate(): bool
    {
        try { return GpmTsSwitchContext::version() === 'new'; }
        catch (\RuntimeException $error) { return false; }
    }
    public static function assertContext(): void { GpmTsSwitchContext::assertUpgrade(); }
}

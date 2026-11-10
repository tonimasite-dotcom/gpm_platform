<?php
namespace App\Services\Release;

use App\Models\User;
use Illuminate\Support\Facades\Crypt;

/** Operator-only delivery of existing challenges. No HTTP retrieval endpoint. */
final class GpmTsDemoLoginInbox
{
    public const DISPLAY_SECONDS = 600;

    public static function capture($user): bool
    {
        GpmTsDemoPolicy::assertContext();
        $actor = auth()->user();
        if (!$user instanceof User || !$user->exists || !$user->active || !$actor
            || (int) $actor->getAuthIdentifier() !== (int) $user->id
            || !is_string($user->remember_token) || strlen($user->remember_token) < 8) {
            throw new \RuntimeException('VERIFIED_LOGIN_CHALLENGE_REQUIRED');
        }
        self::write((int) $user->id, ['version' => 1, 'user_id' => (int) $user->id,
            'email' => (string) $user->email, 'code' => $user->remember_token, 'issued_at' => time()]);
        GpmTsDemoPolicy::suppress('login_code_local');
        return true;
    }

    public static function consume($user): void
    {
        GpmTsDemoPolicy::assertContext();
        if (!$user instanceof User || !$user->exists || (int) $user->id < 1) {
            throw new \RuntimeException('VERIFIED_LOGIN_USER_REQUIRED');
        }
        self::write((int) $user->id, ['version' => 1, 'user_id' => (int) $user->id,
            'email' => (string) $user->email, 'code' => null, 'issued_at' => time()]);
    }

    private static function write(int $id, array $payload): void
    {
        if ($id < 1 || realpath(storage_path('app')) !== storage_path('app')) {
            throw new \RuntimeException('EXACT_PRIVATE_LOGIN_STORAGE_REQUIRED');
        }
        $folder = storage_path('app/gpm-ts-demo-login');
        if (!is_dir($folder) && !mkdir($folder, 0700) && !is_dir($folder)) {
            throw new \RuntimeException('PRIVATE_LOGIN_STORAGE_UNAVAILABLE');
        }
        if (realpath($folder) !== $folder || (fileperms($folder) & 0077) !== 0
            || fileowner($folder) !== posix_geteuid()) {
            throw new \RuntimeException('PRIVATE_LOGIN_STORAGE_PERMISSIONS_REQUIRED');
        }
        $target = $folder . '/' . $id . '.enc';
        if (is_link($target)) { throw new \RuntimeException('LOGIN_FILE_SYMLINK_REJECTED'); }
        $encrypted = Crypt::encryptString(json_encode($payload, JSON_THROW_ON_ERROR));
        $temporary = tempnam($folder, '.challenge-');
        try {
            chmod($temporary, 0600);
            if (file_put_contents($temporary, $encrypted, LOCK_EX) !== strlen($encrypted)
                || !rename($temporary, $target)) {
                throw new \RuntimeException('ENCRYPTED_LOGIN_CAPTURE_FAILED');
            }
        } finally {
            // Only the temporary file created by this write, never stored data.
            if (is_file($temporary)) { unlink($temporary); }
        }
    }
}

<?php
namespace App\Services\Gpm;

use App\Models\Branch;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

final class GpmPreviewWorkerSync
{
    public function enabled(): bool
    {
        return rtrim((string) config('app.url'), '/') === GpmPreviewWorkerPolicy::INSTANCE
            && filter_var(env('GPM_PREVIEW_WORKER_SYNC_ENABLED', false), FILTER_VALIDATE_BOOLEAN);
    }

    private function directory(): string
    {
        $path = storage_path('app/gpm-preview-worker-links');
        if (is_link($path) || (!is_dir($path) && !mkdir($path, 0700, true) && !is_dir($path))) {
            throw new \RuntimeException('Unsafe preview worker storage');
        }
        chmod($path, 0700);
        return $path;
    }

    private function path(string $id): string
    {
        if (!preg_match('/^preview_[a-f0-9]{32}$/D', $id)) {
            throw new \RuntimeException('Invalid preview identity');
        }
        $path = $this->directory() . '/' . $id . '.json';
        if (is_link($path)) throw new \RuntimeException('Unsafe preview worker receipt');
        return $path;
    }

    private function save(string $id, array $value): void
    {
        $temporary = tempnam($this->directory(), '.pending-');
        try {
            chmod($temporary, 0600);
            $text = json_encode($value, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
            if (file_put_contents($temporary, $text) === false || !rename($temporary, $this->path($id))) {
                throw new \RuntimeException('Cannot save preview worker receipt');
            }
        } finally {
            if (is_file($temporary)) unlink($temporary);
        }
    }

    private function request(array $input): array
    {
        $base = rtrim((string) env('GPM_APP_API_URL', ''), '/');
        $token = (string) env('GPM_APP_API_TOKEN', '');
        if (!$this->enabled() || $base !== 'https://app-api.gpmbot.ru' || $token === '') {
            throw new \RuntimeException('Test worker integration is not configured');
        }
        $payload = array_merge($input, ['source_instance'=>GpmPreviewWorkerPolicy::INSTANCE]);
        $response = Http::timeout(4)->withOptions(['allow_redirects'=>false])
            ->acceptJson()->asJson()->withHeaders(['X-GPM-App-Token'=>$token])
            ->post($base . '/app-api/integration/registration-preview/workers', $payload);
        if (!$response->successful() || !is_array($response->json())) {
            throw new \RuntimeException('Test worker server unavailable');
        }
        return $response->json();
    }

    private function links(): array
    {
        $result = [];
        foreach (glob($this->directory() . '/preview_*.json') as $path) {
            if (is_link($path)) throw new \RuntimeException('Unsafe preview worker receipt');
            $value = json_decode(file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
            if (($value['status'] ?? '') === 'linked') {
                $result[(string) $value['profile_id']] = $value;
            }
        }
        return $result;
    }

    private function people(array $profile, array $links, ?array $link = null): array
    {
        $index = [];
        foreach ($links as $id=>$link) $index[(string) $link['crm_worker_id']] = $id;
        $phone = GpmWorkerMatchPolicy::phone($profile['phone'], $profile['phone_country']);
        $ids = [];
        foreach (DB::table('users')->get(['id','phone']) as $row) {
            $candidate = GpmWorkerMatchPolicy::phone($row->phone);
            if (!$candidate) $candidate = GpmWorkerMatchPolicy::phone($row->phone, 'INT');
            if ($candidate === $phone) $ids[(string) $row->id] = true;
        }
        if ($link && !empty($link['crm_worker_id'])) $ids[(string) $link['crm_worker_id']] = true;
        if (!$ids) return [];
        return User::withTrashed()->whereIn('id', array_keys($ids))->with('roles')
            ->get(['id','phone','active','deleted_at','email','note'])
            ->map(function ($user) use ($index) {
                return ['id'=>(string) $user->id, 'phone'=>$user->phone,
                    'roles'=>$user->getRoleNames()->values()->all(),
                    'deleted'=>$user->deleted_at !== null, 'active'=>(bool) $user->active,
                    'preview_profile_id'=>$index[(string) $user->id] ?? null,
                    'email'=>$user->email, 'note'=>$user->note];
            })->all();
    }

    private function branch(array $profile): ?int
    {
        $names = $profile['cities'];
        $branches = Branch::with('city')->get(['id','city_id','name']);
        foreach ($names as $name) {
            $matches = $branches->filter(function ($branch) use ($name) {
                $company = preg_replace('/[^\\p{L}\\p{N}]/u', '', mb_strtolower($branch->name));
                return $company === 'оооджипиэм' && $branch->city
                    && mb_strtolower(trim($branch->city->name)) === mb_strtolower(trim($name));
            });
            if ($matches->count() === 1) return (int) $matches->first()->id;

        }
        return null;
    }

    private function testEmail(string $id): string
    {
        return 'gpm-preview-' . substr($id, 8) . '@gpm-test.invalid';
    }

    private function bind(array $profile, array $links, bool $dry): array
    {
        $id = $profile['profile_id'];
        $email = $this->testEmail($id);
        // Recover a DB commit whose private receipt/HTTP acknowledgement was lost.
        $recovered = User::withTrashed()->where('email', $email)->first();
        $link = $links[$id] ?? null;
        $wasRecovered = false;
        if (!$link && $recovered) {
            if ($recovered->note !== 'Тестовая регистрация GPM') {
                return ['action'=>'conflict','reason'=>'invalid_preview_profile','crm_worker_id'=>null];
            }
            $link = ['crm_worker_id'=>(string) $recovered->id];
            $wasRecovered = true;
        }
        $branchId = $this->branch($profile);
        $decision = GpmPreviewWorkerPolicy::resolve($profile, $this->people($profile, $links, $link), $link,
            $branchId, $this->enabled(), (string) config('app.url'));
        if ($wasRecovered && $decision['action'] === 'link') $decision['reason'] = 'recovered_test_worker';
        if ($decision['action'] !== 'create' || $dry) return $decision;
        return DB::transaction(function () use ($profile, $links, $branchId, $email) {
            // Recheck immediately before creating; the job lock serializes TS imports.
            $decision = GpmPreviewWorkerPolicy::resolve($profile, $this->people($profile, $links), null,
                $branchId, $this->enabled(), (string) config('app.url'));
            if ($decision['action'] !== 'create') return $decision;
            $worker = User::create([
                'surname'=>$profile['surname'], 'first_name'=>$profile['first_name'],
                'middle_name'=>$profile['middle_name'] !== '' ? $profile['middle_name'] : null,
                'birthday'=>$profile['birth_date'], 'phone'=>$profile['phone'],
                'email'=>$email, 'password'=>null, 'active'=>true,
                'branch_id'=>$branchId, 'all_branches'=>false,
                'fact_city'=>$profile['cities'][0] ?? '', 'employment_type'=>'contract',
                'send_sms_about_hiring'=>false, 'note'=>'Тестовая регистрация GPM',
            ]);
            $worker->assignRole('loader');
            return ['action'=>'link','reason'=>'created_test_worker','crm_worker_id'=>(string) $worker->id];
        });
    }

    public function run(bool $dry = false): array
    {
        $counts = ['linked'=>0,'created'=>0,'conflict'=>0,'deferred'=>0,'dry_run'=>$dry,'enabled'=>$this->enabled()];
        if (!$this->enabled()) return $counts;
        $lock = null;
        try {
            $lockPath = $this->directory() . '/sync.lock';
            if (is_link($lockPath)) throw new \RuntimeException('Unsafe worker sync lock');
            $lock = fopen($lockPath, 'c');
            if (!$lock) throw new \RuntimeException('Cannot lock worker sync');
            chmod($lockPath, 0600);
            if (!flock($lock, LOCK_EX | LOCK_NB)) return array_merge($counts, ['deferred'=>1]);
            $since = (float) env('GPM_PREVIEW_WORKER_SYNC_SINCE', 0);
            if (!is_finite($since) || $since <= 0 || $since > time()+30) {
                throw new \RuntimeException('A test registration start time is required');
            }
            $deadline = microtime(true)+12;
            $profiles = GpmPreviewWorkerPolicy::snapshot($this->request([
                'operation'=>'list','since'=>$since,'limit'=>25,
            ]));
            $links = $this->links();
            foreach ($profiles as $profile) {
                if (microtime(true) >= $deadline) { $counts['deferred']++; break; }
                if ((float) $profile['created_at'] < $since) throw new \RuntimeException('Unexpected old test profile');
                try {
                    $decision = $this->bind($profile, $links, $dry);
                    if ($dry) {
                        $key = $decision['action'] === 'create' ? 'created'
                            : ($decision['action'] === 'link' ? 'linked' : $decision['action']);
                        $counts[$key] = ($counts[$key] ?? 0)+1;
                        continue;
                    }
                    if ($decision['action'] === 'link') {
                        $receipt = ['status'=>'linked','profile_id'=>$profile['profile_id'],
                            'crm_worker_id'=>$decision['crm_worker_id'],'revision'=>$profile['revision'],
                            'created_by_sync'=>in_array($decision['reason'], ['created_test_worker','recovered_test_worker'], true)
                                || !empty($links[$profile['profile_id']]['created_by_sync']),
                            'linked_at'=>gmdate('c')];
                        $this->save($profile['profile_id'], $receipt);
                        $links[$profile['profile_id']] = $receipt;
                        $this->request(['operation'=>'ack','profile_id'=>$profile['profile_id'],
                            'revision'=>$profile['revision'],'status'=>'linked',
                            'crm_worker_id'=>$decision['crm_worker_id'],'error_code'=>null]);
                        $counts['linked']++;
                        if ($decision['reason']==='created_test_worker') $counts['created']++;
                    } else {
                        $status = $decision['action'] === 'conflict' ? 'conflict' : 'deferred';
                        $this->request(['operation'=>'ack','profile_id'=>$profile['profile_id'],
                            'revision'=>$profile['revision'],'status'=>$status,
                            'crm_worker_id'=>null,'error_code'=>$decision['reason']]);
                        $counts[$status]++;
                    }
                } catch (\Throwable $error) {
                    $counts['deferred']++;
                    Log::warning('GPM test worker deferred', ['error_type'=>get_class($error)]);
                    try {
                        $this->request(['operation'=>'ack','profile_id'=>$profile['profile_id'],
                            'revision'=>$profile['revision'],'status'=>'deferred',
                            'crm_worker_id'=>null,'error_code'=>'temporary_unavailable']);
                    } catch (\Throwable $ignored) {}
                }
            }
        } catch (\Throwable $error) {
            $counts['deferred']++;
            Log::warning('GPM test worker sync unavailable', ['error_type'=>get_class($error)]);
        } finally {
            if (is_resource($lock)) { flock($lock, LOCK_UN); fclose($lock); }
        }
        return $counts;
    }
}

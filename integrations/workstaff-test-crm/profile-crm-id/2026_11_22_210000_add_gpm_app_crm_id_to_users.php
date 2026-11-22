<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

class AddGpmAppCrmIdToUsers extends Migration
{
    public function up()
    {
        if (rtrim((string) config('app.url'), '/') !== 'https://ts.workstaffcrm.ru') {
            throw new RuntimeException('This migration is scoped to the approved TS instance');
        }
        if (Schema::hasColumn('users', 'gpm_app_crm_id')) {
            throw new RuntimeException('Column already exists; inspect before applying');
        }
        DB::statement('ALTER TABLE users ADD COLUMN gpm_app_crm_id INT UNSIGNED NULL, ALGORITHM=INPLACE, LOCK=NONE');
    }

    public function down()
    {
        throw new RuntimeException('Rollback application code only; preserve saved GPM IDs');
    }
}

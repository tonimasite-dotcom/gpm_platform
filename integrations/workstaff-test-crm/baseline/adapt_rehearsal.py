#!/usr/bin/env python3
"""Prepare migration adaptations ONLY for a strict private rehearsal.

Not deployable: GpmTsRehearsal rejects the live TS and primary CRM. Keep the
upstream transformation of deleted emails and bank cards deferred separately.
"""
from pathlib import Path
import base64
import hashlib
import json
import os
import re
import secrets

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
ROOT = WORK / 'candidate'
CONTEXT = '\\App\\Services\\Release\\GpmTsRehearsal::assertContext();'


def body_span(text, method):
    match = re.search(r'function\s+' + re.escape(method) + r'\s*\([^)]*\)[^{]*\{', text)
    if not match: raise RuntimeError('Missing function: ' + method)
    start = match.end();depth = 1;i = start;quote = None
    while i < len(text):
        char = text[i]
        if quote:
            if char == '\\': i += 2;continue
            if char == quote: quote = None
        elif text.startswith('//', i) or char == '#':
            end = text.find('\n', i);i = len(text) if end < 0 else end;continue
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            if end < 0: raise RuntimeError('Unclosed comment')
            i = end + 2;continue
        elif char in ['"', "'"]: quote = char
        elif char == '{': depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0: return start, i
        i += 1
    raise RuntimeError('Unbalanced function')


def replace_body(text, method, value):
    a, b = body_span(text, method)
    return text[:a] + '\n' + value + '\n    ' + text[b:]


def adapt_guards(text):
    if not ('workstaffcrm.ru' in text or 'test_gruzpiter' in text):
        return text, False
    for method in ['assertEnvironment', 'guard']:
        if re.search(r'function\s+' + method + r'\s*\(', text):
            a, b = body_span(text, method);body = text[a:b]
            # Keep non-environment prerequisites and lock/version checks after
            # replacing site/database identity checks with our stricter context.
            suffix = ''
            if method == 'guard':
                tails = [m.start() for m in re.finditer(r'if\s*\(\s*!Schema::|if\s*\(\s*!self::mysql|foreach\s*\(\s*\[', body)]
                if tails: suffix = body[min(tails):]
            return replace_body(text, method, '        ' + CONTEXT + '\n        ' + suffix), True
    a, b = body_span(text, 'up');body = text[a:b]
    markers = ['// Existing records', 'self::schema();', 'self::create();',
               "if (Schema::hasTable('admin_permission_overrides'))",
               "if(!Schema::hasTable('order_worker_calculations'))"]
    positions = [body.index(marker) for marker in markers if marker in body]
    if not positions: raise RuntimeError('Unrecognized guarded migration')
    suffix = body[min(positions):]
    return replace_body(text, 'up', '        ' + CONTEXT + "\n        $env = 'ts-rehearsal';\n        " + suffix), True


def prepare():
    os.umask(0o077)
    if ROOT.resolve() != ROOT: raise RuntimeError('Unsafe candidate')
    original = json.loads((WORK / 'preparation.json').read_text())
    missing = [name for name in original['source_manifests']['main']
               if name.startswith('database/migrations/') and name not in original['source_manifests']['ts']]
    if len(missing) != 37: raise RuntimeError('Unexpected migration set')
    outcomes = []
    for relative in sorted(missing):
        source = WORK / 'source-main' / relative;text = source.read_text()
        if hashlib.sha256(source.read_bytes()).hexdigest() != original['source_manifests']['main'][relative]['sha256']:
            raise RuntimeError('Upstream migration changed')
        target = ROOT / relative
        if 'transfer_banking_card_to_card_number' in relative:
            archive = ROOT / 'database/gpm-upstream' / target.name
            archive.parent.mkdir(parents=True, exist_ok=True)
            if target.exists(): target.rename(archive)
            outcomes.append({'source': relative, 'status': 'data_transform_deferred', 'guard_adapted': False})
            continue
        text, guarded = adapt_guards(text)
        if 'add_city_id_to_users_table' in relative:
            body = r'''        \App\Services\Release\GpmTsRehearsal::assertContext();
        $column = DB::selectOne("SELECT COLUMN_TYPE AS t,IS_NULLABLE AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='users' AND COLUMN_NAME='city_id'");
        $foreign = DB::selectOne("SELECT COUNT(*) AS n FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME WHERE k.CONSTRAINT_SCHEMA=DATABASE() AND k.TABLE_NAME='users' AND k.COLUMN_NAME='city_id' AND k.REFERENCED_TABLE_NAME='cities' AND k.REFERENCED_COLUMN_NAME='id' AND r.DELETE_RULE='SET NULL' AND r.UPDATE_RULE='RESTRICT'");
        if (!$column || strtolower($column->t) !== 'bigint(20) unsigned' || $column->n !== 'YES' || (int)$foreign->n !== 1) {
            throw new \RuntimeException('GPM_TS_EXISTING_CITY_SCHEMA_MISMATCH');
        }'''
            # Fully qualify DB because this historical migration does not import it.
            body = body.replace('DB::', '\\Illuminate\\Support\\Facades\\DB::')
            text = replace_body(text, 'up', body)
        if 'release_deleted_user_emails' in relative:
            archive = ROOT / 'database/gpm-upstream' / target.name
            archive.parent.mkdir(parents=True, exist_ok=True)
            if target.exists(): target.rename(archive)
            # This is explicitly a DIFFERENT schema-only migration. Do not record
            # upstream's release(true) data transformation as applied.
            alias = ROOT / 'database/migrations/2026_10_28_110001_add_deleted_email_schema_for_gpm_ts.php'
            alias.write_text('''<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
class AddDeletedEmailSchemaForGpmTs extends Migration {
 public function up() {
  \App\Services\Release\GpmTsRehearsal::assertContext();
  if (Schema::hasColumn('users','deleted_email')) throw new \RuntimeException('GPM_TS_DELETED_EMAIL_ALREADY_EXISTS');
  Schema::table('users',function(Blueprint $table){$table->string('deleted_email',255)->nullable()->after('email')->comment('e-mail на момент удаления аккаунта (аудит)');});
 }
 public function down(){throw new \RuntimeException('EXPLICIT_RESTORE_REQUIRED');}
}
''')
            outcomes.append({'source': relative, 'status': 'separate_schema_only_email_data_deferred', 'guard_adapted': guarded,
                             'candidate': str(alias.relative_to(ROOT))})
            continue
        target.write_text(text)
        outcomes.append({'source': relative, 'status': 'rehearsal_only', 'guard_adapted': guarded,
                         'candidate': relative})
    if sum(row['guard_adapted'] for row in outcomes) != 17:
        raise RuntimeError('Guard adaptation count changed')
    identity = json.loads((WORK / 'rehearsal-mysql/identity.json').read_text())
    folders = ['storage/app', 'storage/logs', 'storage/framework/cache/data',
               'storage/framework/sessions', 'storage/framework/views', 'bootstrap/cache']
    for folder in folders: (ROOT / folder).mkdir(parents=True, exist_ok=True)
    config = {'APP_NAME': 'GPM TS Private Rehearsal', 'APP_ENV': 'testing', 'APP_DEBUG': 'false',
              'APP_URL': 'https://ts.workstaffcrm.ru', 'APP_KEY': 'base64:' + base64.b64encode(secrets.token_bytes(32)).decode(),
              'DB_CONNECTION': 'mysql', 'DB_SOCKET': identity['socket'], 'DB_HOST': 'localhost',
              'DB_DATABASE': identity['database'], 'DB_USERNAME': identity['username'], 'DB_PASSWORD': identity['password'],
              'CACHE_DRIVER': 'array', 'SESSION_DRIVER': 'array', 'QUEUE_CONNECTION': 'sync',
              'BROADCAST_DRIVER': 'log', 'MAIL_MAILER': 'log', 'MAIL_DRIVER': 'log', 'LOG_CHANNEL': 'single',
              'JWT_SECRET': secrets.token_hex(32), 'GPM_APP_ORDER_SYNC_ENABLED': 'false',
              'GPM_APP_API_URL': 'https://invalid.invalid', 'GPM_APP_API_TOKEN': '', 'LOGIN_EMAIL_CODE_ENABLED': 'false'}
    (ROOT / '.env').write_text('\n'.join(name + '=' + json.dumps(value) for name, value in config.items()) + '\n')
    (ROOT / 'storage/framework/down').write_text(json.dumps({'time': 0, 'message': 'Private rehearsal', 'retry': 60, 'allowed': []}))
    (WORK / 'rehearsal-adaptations.json').write_text(json.dumps({'deployable': False, 'live_changed': False, 'migrations': outcomes}, indent=2))
    print(json.dumps({'migration_sources_reviewed': 37, 'environment_guards_adapted': 17,
                      'bank_card_data_deferred': True, 'deleted_email_data_deferred': True,
                      'live_changed': False, 'deployable': False}))


if __name__ == '__main__': prepare()

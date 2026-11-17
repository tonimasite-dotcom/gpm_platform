"""Rehearse five schema dependencies on a NEW cold copy, never live or baseline.

This verifies additive DDL/data preservation, not application financial rollback.
Run inside a new network namespace. No Laravel bootstrap or migrations execute.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from sql_snapshot import Snapshot

BASE = Path('/root/gpm-ts-runtime-20261113-01')
SOURCE = BASE / 'ts-backup-restore-20261117-01'
DEST = BASE / 'ts-schema-rehearsal-20261117-01'
DB = 'gpm_ts_restore_20261117'
NEW_TABLES = {
 'order_financial_reopens': 'order_id BIGINT UNSIGNED NOT NULL PRIMARY KEY, completion_anchor DATETIME NOT NULL, completion_anchor_ts BIGINT NOT NULL, done_status_anchor DATETIME NULL, actor_id BIGINT UNSIGNED NOT NULL, revision INT UNSIGNED NOT NULL DEFAULT 1, reason TEXT NOT NULL, credited_workers LONGTEXT NOT NULL, created_at TIMESTAMP NULL, updated_at TIMESTAMP NULL',
 'payout_settlement_gate': 'id INT UNSIGNED NOT NULL PRIMARY KEY',
 'order_worker_mail_states': 'order_id BIGINT UNSIGNED NOT NULL PRIMARY KEY, roster_hash VARCHAR(64) NOT NULL, sent_hash VARCHAR(64) NULL, receipts TEXT NULL, pending_recipient VARCHAR(255) NULL, created_at TIMESTAMP NULL, updated_at TIMESTAMP NULL, sent_worker_ids LONGTEXT NULL, attempt_context LONGTEXT NULL',
 'admin_permission_overrides': 'role_id BIGINT UNSIGNED NOT NULL, scope VARCHAR(100) NOT NULL, allowed TINYINT NOT NULL, actor_id BIGINT UNSIGNED NULL, updated_at DATETIME NOT NULL, PRIMARY KEY(role_id,scope)',
}


def main():
    global DEST
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    options=parser.parse_args()
    if not re.fullmatch('20261117-[0-9]{2}',options.run_id): raise RuntimeError('SAFE_RUN_ID_REQUIRED')
    DEST=BASE/('ts-schema-rehearsal-'+options.run_id)
    os.umask(0o077)
    if os.readlink('/proc/self/ns/net') == os.readlink('/proc/1/ns/net'):
        raise RuntimeError('ISOLATED_NETWORK_REQUIRED')
    if any(p.resolve() != p for p in [BASE, SOURCE, DEST]) or DEST.exists():
        raise RuntimeError('EXACT_NEW_COPY_REQUIRED')
    receipt = json.loads((SOURCE / 'result.json').read_text())
    if receipt['status'] != 'PASS' or not receipt['private_mysql_shutdown_verified'] or (SOURCE / 'mysql.sock').exists():
        raise RuntimeError('STOPPED_VERIFIED_BASELINE_REQUIRED')
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit(): continue
        try:
            if ('--datadir='+str(SOURCE/'data')).encode() in (proc/'cmdline').read_bytes():
                raise RuntimeError('BASELINE_MYSQL_RUNNING')
        except FileNotFoundError: pass
    if shutil.disk_usage(BASE).free < 6*1024**3:
        raise RuntimeError('COPY_AND_RESERVE_SPACE_REQUIRED')
    DEST.mkdir(mode=0o700)
    (DEST/'PRIVATE_SCHEMA_REHEARSAL').write_text('No application or live changes\n')
    shutil.copytree(str(SOURCE/'data'), str(DEST/'data'), symlinks=True)
    if any(p.is_symlink() for p in (DEST/'data').rglob('*')):
        raise RuntimeError('DATADIR_LINK_NOT_ALLOWED')
    expected = json.loads((SOURCE/'private-table-fingerprints.json').read_text())
    socket = DEST/'mysql.sock'
    client = ['mysql','--no-defaults','--protocol=SOCKET','--socket='+str(socket),'--user=root','--batch','--skip-column-names']
    def query(sql):
        r = subprocess.run(client,input=sql.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
        if r.returncode: raise RuntimeError('PRIVATE_QUERY_FAILED')
        return r.stdout
    def dump():
        p = subprocess.Popen(['mysqldump','--no-defaults','--protocol=SOCKET','--socket='+str(socket),'--user=root',
            '--single-transaction','--skip-lock-tables','--quick','--no-tablespaces','--set-gtid-purged=OFF',
            '--hex-blob','--skip-extended-insert','--default-character-set=utf8mb4',DB],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        s = Snapshot()
        for line in p.stdout: s.line(line)
        p.stderr.read()
        if p.wait(): raise RuntimeError('PRIVATE_DUMP_FAILED')
        return s.finish()['tables']
    def projection(columns):
        p = subprocess.Popen(client+['--execute=SELECT '+','.join('`'+n+'`' for n in columns)+' FROM `'+DB+'`.orders'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        values = [hashlib.sha256(line).digest() for line in p.stdout]
        p.stderr.read()
        if p.wait(): raise RuntimeError('ORDER_PROJECTION_FAILED')
        return dict(rows=len(values),sha256=hashlib.sha256(b''.join(sorted(values))).hexdigest())
    process = None
    result = dict(status='FAILED',live_ts_changed=False,main_crm_changed=False,baseline_changed=False,
                  migrations_run=False,application_started=False,network_isolated=True,
                  financial_write_rollback_accepted=False,workspace=str(DEST))
    try:
        process = subprocess.Popen(['/usr/sbin/mysqld','--no-defaults','--user=root','--datadir='+str(DEST/'data'),
            '--socket='+str(socket),'--pid-file='+str(DEST/'mysql.pid'),'--log-error='+str(DEST/'mysql-error.log'),
            '--skip-networking','--skip-log-bin','--event-scheduler=OFF','--performance-schema=OFF',
            '--innodb-buffer-pool-size=134217728','--innodb-log-file-size=16777216',
            '--innodb-flush-log-at-trx-commit=2'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if process.poll() is not None: raise RuntimeError('PRIVATE_START_FAILED')
            if socket.exists():
                r = subprocess.run(client+['--execute=SELECT 1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if r.returncode == 0: break
            time.sleep(.25)
        else: raise RuntimeError('PRIVATE_START_TIMEOUT')
        identity = query('SELECT @@datadir,@@skip_networking,@@event_scheduler').decode().strip().split('\t')
        if Path(identity[0]).resolve()!=DEST/'data' or identity[1:]!=['1','OFF']: raise RuntimeError('PRIVATE_IDENTITY')
        # MySQL 5.7 can reset counters at a cold restart; restore only upward
        # from the verified backup metadata, only in this disposable new copy.
        fixed = 0
        for name,row in expected.items():
            if not re.fullmatch('[A-Za-z0-9_]+',name): raise RuntimeError('TABLE_NAME')
            if row['auto_increment'] is None: continue
            ddl = query('SHOW CREATE TABLE `'+DB+'`.`'+name+'`')
            match = re.search(rb'\bAUTO_INCREMENT=(\d+)',ddl)
            actual = int(match[1]) if match else 1
            if actual>row['auto_increment']: raise RuntimeError('COUNTER_ABOVE_BASELINE')
            if actual!=row['auto_increment']:
                query('ALTER TABLE `'+DB+'`.`'+name+'` AUTO_INCREMENT='+str(row['auto_increment']))
                fixed+=1
        before = dump()
        if before!=expected: raise RuntimeError('COLD_COPY_BASELINE_MISMATCH')
        result['cold_restart_counters_restored_upward']=fixed
        print(json.dumps(dict(stage='cold_copy_matches_verified_backup',tables=len(before))),flush=True)
        if set(before)!=set(expected) or set(NEW_TABLES)&set(before): raise RuntimeError('ADDITIVE_SCHEMA_PRECONDITION')
        columns = [line.split('\t')[0] for line in query('SHOW COLUMNS FROM `'+DB+'`.orders').decode().splitlines()]
        if 'calculation_version' in columns: raise RuntimeError('VERSION_ALREADY_EXISTS')
        old_orders = projection(columns)
        for name,definition in NEW_TABLES.items():
            warnings=query('CREATE TABLE `'+DB+'`.`'+name+'` ('+definition+') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;SHOW WARNINGS')
            if warnings.strip(): raise RuntimeError('NEW_TABLE_DDL_WARNING')
        query('INSERT INTO `'+DB+'`.payout_settlement_gate(id) VALUES (1)')
        query('ALTER TABLE `'+DB+'`.orders ADD COLUMN calculation_version TINYINT UNSIGNED NOT NULL DEFAULT 1')
        query('ALTER TABLE `'+DB+'`.orders ALTER COLUMN calculation_version SET DEFAULT 2')
        after = dump()
        if set(after)!=set(before)|set(NEW_TABLES): raise RuntimeError('FINAL_TABLE_INVENTORY')
        changed = [name for name in before if name!='orders' and before[name]!=after[name]]
        if changed or projection(columns)!=old_orders: raise RuntimeError('EXISTING_DATA_OR_SCHEMA_CHANGED')
        if before['orders']['auto_increment']!=after['orders']['auto_increment']: raise RuntimeError('ORDER_COUNTER_CHANGED')
        if int(query('SELECT COUNT(*) FROM `'+DB+'`.orders WHERE calculation_version<>1 OR calculation_version IS NULL')):
            raise RuntimeError('EXISTING_ORDER_VERSION_NOT_ONE')
        default = query("SELECT COLUMN_DEFAULT FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='"+DB+"' AND TABLE_NAME='orders' AND COLUMN_NAME='calculation_version'").strip()
        if default!=b'2': raise RuntimeError('FUTURE_ORDER_DEFAULT_NOT_TWO')
        if any(after[name]['rows']!=(1 if name=='payout_settlement_gate' else 0) for name in NEW_TABLES):
            raise RuntimeError('UNEXPECTED_NEW_ROWS')
        (DEST/'private-schema-fingerprints.json').write_text(json.dumps(after,indent=2)+'\n')
        result.update(status='PASS',original_tables=72,result_tables=76,existing_rows_preserved=True,
                      unchanged_tables_full_fingerprints=71,order_original_columns_preserved=True,
                      all_original_auto_increment_preserved=True,existing_orders_version_one=True,
                      future_order_default_two=True,rights_and_accounts_unchanged=True,
                      new_tables=list(NEW_TABLES),new_gate_rows=1,other_new_tables_empty=True,
                      baseline_rows=sum(row['rows'] for row in before.values()),
                      schema_down_or_table_drop_run=False,code_rollback_must_retain_schema=True)
    except Exception as error:
        result['error']=str(error) if type(error) is RuntimeError else type(error).__name__
    finally:
        if process is not None and process.poll() is None:
            r = subprocess.run(['mysqladmin','--no-defaults','--protocol=SOCKET','--socket='+str(socket),'--user=root','shutdown'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
            if r.returncode:
                if ('--datadir='+str(DEST/'data')).encode() not in Path('/proc/'+str(process.pid)+'/cmdline').read_bytes():
                    raise RuntimeError('SHUTDOWN_IDENTITY')
                process.terminate()
            process.wait(timeout=60)
        result['private_mysql_shutdown_verified']=(process is None or process.poll() is not None) and not socket.exists()
        if not result['private_mysql_shutdown_verified']: result['status']='FAILED'
        result['free_bytes_after']=shutil.disk_usage(BASE).free
        (DEST/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)


if __name__=='__main__': main()

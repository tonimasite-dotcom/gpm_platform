"""Run only the existing synthetic database in an already isolated network namespace.

No init, restore, migration, grant or live database operation is supported.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

BASE=Path('/root/gpm-ts-runtime-20261113-01')
ROOTFS=BASE/'rootfs'
DATA=BASE/'bot-schema-fixture-01/mysql-data'
SOCKET=ROOTFS/'tmp/gpm-bot-fixture.sock'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--prepare-gate',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]+',args.run_id):
        raise RuntimeError('SAFE_UNIQUE_RUN_ID_REQUIRED')
    os.umask(0o077)
    if os.readlink('/proc/self/ns/net')==os.readlink('/proc/1/ns/net'):
        raise RuntimeError('ISOLATED_NETWORK_NAMESPACE_REQUIRED')
    if DATA.resolve()!=DATA or not (DATA/'ibdata1').is_file() or SOCKET.exists():
        raise RuntimeError('STOPPED_EXISTING_SYNTHETIC_DATABASE_REQUIRED')
    if not (ROOTFS/'work/crm-private-01/PRIVATE_BOT_FIXTURE').is_file():
        raise RuntimeError('MARKED_CANDIDATE_REQUIRED')
    report=BASE/('http-acceptance-'+args.run_id)
    report.mkdir(mode=0o700)
    client=['mysql','--no-defaults','--protocol=SOCKET','--socket='+str(SOCKET),
            '--user=root','--batch','--skip-column-names']

    def query(sql):
        result=subprocess.run(client,input=sql.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if result.returncode:
            raise RuntimeError('SYNTHETIC_MYSQL_QUERY_FAILED')
        return result.stdout

    def snapshot():
        names=query('SHOW TABLES FROM bot_fixture').decode().splitlines()
        rows={}
        for name in names:
            if not re.fullmatch(r'[A-Za-z0-9_]+',name):
                raise RuntimeError('UNEXPECTED_TABLE_NAME')
            content=query('SELECT * FROM bot_fixture.`'+name+'`').splitlines()
            rows[name]={'count':len(content),'sha256':hashlib.sha256(b'\n'.join(sorted(content))).hexdigest()}
        return rows

    process=None
    result={'status':'FAILED','run_id':args.run_id,'live_ts_changed':False,'database_initialized':False,
            'migrations_run':False,'network_isolated':True}
    try:
        process=subprocess.Popen(['/usr/sbin/mysqld','--no-defaults','--user=root','--datadir='+str(DATA),
            '--socket='+str(SOCKET),'--pid-file='+str(report/'mysql.pid'),'--log-error='+str(report/'mysql-error.log'),
            '--skip-networking','--skip-log-bin','--performance-schema=OFF','--innodb-buffer-pool-size=134217728',
            '--max-connections=10','--character-set-server=utf8mb4','--collation-server=utf8mb4_unicode_ci'],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for unused in range(80):
            if process.poll() is not None:
                raise RuntimeError('PRIVATE_MYSQL_START_FAILED')
            if SOCKET.exists():
                probe=subprocess.run(client+['--execute=SELECT 1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if probe.returncode==0:
                    break
            time.sleep(0.25)
        else:
            raise RuntimeError('PRIVATE_MYSQL_START_TIMEOUT')
        actual=query('SELECT @@datadir').decode().strip().rstrip('/')
        if actual!=str(DATA):
            raise RuntimeError('PRIVATE_DATADIR_IDENTITY_MISMATCH')
        if args.prepare_gate:
            if query("SHOW TABLES FROM bot_fixture LIKE 'payout_settlement_gate'").strip():
                raise RuntimeError('GATE_FIXTURE_ALREADY_EXISTS')
            original=snapshot()
            query('CREATE TABLE bot_fixture.payout_settlement_gate (id INT UNSIGNED NOT NULL PRIMARY KEY) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci')
            query('INSERT INTO bot_fixture.payout_settlement_gate (id) VALUES (1)')
            prepared=snapshot()
            if len(prepared)!=len(original)+1 or any(prepared.get(name)!=row for name,row in original.items()):
                raise RuntimeError('PREEXISTING_FIXTURE_ROWS_CHANGED')
            result['fixture_schema_additions']=['payout_settlement_gate: id=1 transaction mutex only']
            result['upstream_payout_migration_marked_applied']=False
            (report/'schema-addition-original-checks.json').write_text(json.dumps(original,indent=2)+'\n')
        before=snapshot()
        (report/'before.json').write_text(json.dumps(before,indent=2)+'\n')
        test_path='/work/crm-private-01/private-http-rate-'+args.run_id+'.php'
        test=subprocess.run(['env','PHP_INI_DIR=/usr/local/etc/php','PHP_INI_SCAN_DIR=/usr/local/etc/php/conf.d',
            'chroot',str(ROOTFS),'/usr/local/bin/php',test_path],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
        (report/'stdout').write_bytes(test.stdout)
        (report/'stderr').write_bytes(test.stderr)
        after=snapshot()
        (report/'after.json').write_text(json.dumps(after,indent=2)+'\n')
        result.update(test_exit_code=test.returncode,all_table_rows_restored=before==after,
                      table_count=len(before),changed_tables=[name for name in before if before.get(name)!=after.get(name)])
        try:
            parsed=json.loads(test.stdout)
        except (ValueError,UnicodeError):
            parsed={'status':'NON_JSON_FAILURE','output_tail':test.stdout.decode(errors='replace')[-800:]}
        result['test']=parsed
        if test.returncode==0 and parsed.get('status')=='PASS' and before==after:
            result['status']='PASS'
    except Exception as error:
        result['runner_error']=str(error)
    finally:
        if process is not None and process.poll() is None:
            stop=subprocess.run(['mysqladmin','--no-defaults','--protocol=SOCKET','--socket='+str(SOCKET),'--user=root','shutdown'],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
            if stop.returncode:
                command=Path('/proc/'+str(process.pid)+'/cmdline').read_bytes()
                if ('--datadir='+str(DATA)).encode() not in command:
                    raise RuntimeError('SHUTDOWN_PROCESS_IDENTITY_MISMATCH')
                process.terminate()
            process.wait(timeout=60)
        result['private_db_shutdown_verified']=(process is None or process.poll() is not None) and not SOCKET.exists()
        if not result['private_db_shutdown_verified']:
            result['status']='FAILED'
        (report/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()

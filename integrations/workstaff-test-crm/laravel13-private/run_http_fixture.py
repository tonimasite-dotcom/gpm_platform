"""Run only the existing synthetic database in an already isolated network namespace.

No init, restore, migration, grant or live database operation is supported.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import socket
import threading
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
    parser.add_argument('--prepare-worker-mail-state',action='store_true')
    parser.add_argument('--with-smtp-fixture',action='store_true')
    parser.add_argument('--prepare-admin-overrides',action='store_true')
    parser.add_argument('--prepare-calculation-version',action='store_true')
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
    smtp=None; smtp_thread=None; smtp_stop=threading.Event(); smtp_messages=[]
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
        if args.prepare_worker_mail_state:
            if query("SHOW TABLES FROM bot_fixture LIKE 'order_worker_mail_states'").strip():
                raise RuntimeError('WORKER_MAIL_STATE_FIXTURE_ALREADY_EXISTS')
            original=before
            query('CREATE TABLE bot_fixture.order_worker_mail_states (order_id BIGINT UNSIGNED NOT NULL PRIMARY KEY, roster_hash VARCHAR(64) NOT NULL, sent_hash VARCHAR(64) NULL, receipts TEXT NULL, pending_recipient VARCHAR(255) NULL, created_at TIMESTAMP NULL DEFAULT NULL, updated_at TIMESTAMP NULL DEFAULT NULL, sent_worker_ids LONGTEXT NULL, attempt_context LONGTEXT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci')
            before=snapshot()
            if len(before)!=len(original)+1 or any(before.get(name)!=row for name,row in original.items()):
                raise RuntimeError('PREEXISTING_FIXTURE_ROWS_CHANGED')
            result.setdefault('fixture_schema_additions',[]).append('order_worker_mail_states: empty state schema only; sender disabled')
            result['upstream_worker_mail_migrations_marked_applied']=False
            (report/'worker-mail-schema-original-checks.json').write_text(json.dumps(original,indent=2)+'\n')
        (report/'before.json').write_text(json.dumps(before,indent=2)+'\n')
        if args.prepare_admin_overrides:
            if query("SHOW TABLES FROM bot_fixture LIKE 'admin_permission_overrides'").strip():
                raise RuntimeError('ADMIN_OVERRIDE_FIXTURE_ALREADY_EXISTS')
            original=before
            query('CREATE TABLE bot_fixture.admin_permission_overrides (role_id BIGINT UNSIGNED NOT NULL, scope VARCHAR(100) NOT NULL, allowed TINYINT NOT NULL, actor_id BIGINT UNSIGNED NULL, updated_at DATETIME NOT NULL, PRIMARY KEY (role_id,scope)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci')
            before=snapshot()
            if len(before)!=len(original)+1 or any(before.get(name)!=row for name,row in original.items()):
                raise RuntimeError('PREEXISTING_FIXTURE_ROWS_CHANGED')
            result.setdefault('fixture_schema_additions',[]).append('admin_permission_overrides: empty table; no rights or role changes')
            result['upstream_admin_override_migration_marked_applied']=False
            (report/'admin-override-schema-original-checks.json').write_text(json.dumps(original,indent=2)+'\n')
            (report/'before-after-explicit-schema-addition.json').write_text(json.dumps(before,indent=2)+'\n')
        test_path='/work/crm-private-01/private-http-rate-'+args.run_id+'.php'
        if args.prepare_calculation_version:
            if query("SHOW COLUMNS FROM bot_fixture.orders LIKE 'calculation_version'").strip():
                raise RuntimeError('CALCULATION_VERSION_FIXTURE_ALREADY_EXISTS')
            original=before
            if original['orders']['count']!=0:
                raise RuntimeError('EMPTY_ORDER_FIXTURE_REQUIRED_FOR_SCHEMA_STEP')
            query('ALTER TABLE bot_fixture.orders ADD COLUMN calculation_version TINYINT UNSIGNED NOT NULL DEFAULT 1')
            query('ALTER TABLE bot_fixture.orders ALTER COLUMN calculation_version SET DEFAULT 2')
            before=snapshot()
            if before!=original:raise RuntimeError('PREEXISTING_FIXTURE_ROWS_CHANGED')
            result.setdefault('fixture_schema_additions',[]).append('orders.calculation_version: existing default 1, future default 2')
            result['upstream_calculation_version_migration_marked_applied']=False
            (report/'calculation-version-schema-original-checks.json').write_text(json.dumps(original,indent=2)+'\n')
        extra_env=[]
        if args.with_smtp_fixture:
            subprocess.run(['ip','link','set','lo','up'],check=True,stdout=subprocess.DEVNULL)
            smtp=socket.socket();smtp.bind(('127.0.0.1',0));smtp.listen(2);smtp.settimeout(0.25)
            port=smtp.getsockname()[1]
            def serve_smtp():
                while not smtp_stop.is_set():
                    try:connection,address=smtp.accept()
                    except socket.timeout:continue
                    except OSError:return
                    try:
                        connection.settimeout(10)
                        stream=connection.makefile('rwb');stream.write(b'220 synthetic ESMTP\r\n');stream.flush()
                        recipients=[];body_bytes=0;in_data=False
                        while True:
                            line=stream.readline()
                            if not line:break
                            if in_data:
                                if line.rstrip(b'\r\n')==b'.':
                                    smtp_messages.append({'all_recipients_synthetic':bool(recipients) and all(recipients),'body_bytes':body_bytes})
                                    in_data=False;response=b'250 accepted\r\n'
                                else:body_bytes+=len(line);continue
                            elif line.upper().startswith(b'EHLO') or line.upper().startswith(b'HELO'):
                                response=b'250-synthetic\r\n250 8BITMIME\r\n'
                            elif line.upper().startswith(b'RCPT '):
                                recipients.append(b'@example.invalid' in line.lower());response=b'250 recipient\r\n'
                            elif line.upper().startswith(b'DATA'):
                                in_data=True;response=b'354 data\r\n'
                            elif line.upper().startswith(b'QUIT'):
                                stream.write(b'221 bye\r\n');stream.flush();break
                            else:response=b'250 ok\r\n'
                            stream.write(response);stream.flush()
                        stream.close()
                    except (OSError,ValueError):pass
                    finally:connection.close()
            smtp_thread=threading.Thread(target=serve_smtp);smtp_thread.daemon=True;smtp_thread.start()
            extra_env=['GPM_PRIVATE_SMTP_PORT='+str(port)]
        test=subprocess.run(['env','PHP_INI_DIR=/usr/local/etc/php','PHP_INI_SCAN_DIR=/usr/local/etc/php/conf.d']+extra_env+[
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
        if args.with_smtp_fixture:
            result['synthetic_smtp_messages']=len(smtp_messages)
            result['synthetic_smtp_verified']=len(smtp_messages)==1 and all(row['all_recipients_synthetic'] and row['body_bytes']>0 for row in smtp_messages)
        if test.returncode==0 and parsed.get('status')=='PASS' and before==after:
            result['status']='PASS'
            if args.with_smtp_fixture and not result['synthetic_smtp_verified']:result['status']='FAILED'
    except Exception as error:
        result['runner_error']=str(error)
    finally:
        smtp_stop.set()
        if smtp is not None:smtp.close()
        if smtp_thread is not None:smtp_thread.join(timeout=12)
        result['fake_smtp_shutdown_verified']=smtp_thread is None or not smtp_thread.is_alive()
        if not result['fake_smtp_shutdown_verified']:result['status']='FAILED'
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

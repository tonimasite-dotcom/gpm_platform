#!/usr/bin/env python3
"""Scoped production backup. Does not initialize/migrate the application or DB."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path('/opt/gpm/gpm_platform')
FRONT = Path('/var/www/gpm-app')
BASES = {'backend': Path('/opt/gpm/backups/managed-v1'),
         'frontend': Path('/opt/gpm/front-backups/managed-v1')}

def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()

def validate_run(value):
    if not re.fullmatch(r'[0-9]{5,20}-[0-9]{1,5}', value):
        raise ValueError('Invalid run identifier')
    return value

def validate_recipient(value):
    if not re.fullmatch(r'age1[023456789acdefghjklmnpqrstuvwxyz]{58}', value):
        raise ValueError('Expected a native age X25519 public recipient')
    return value

def child_env(dsn, parse_dsn):
    mapping = {'host':'PGHOST','port':'PGPORT','user':'PGUSER','password':'PGPASSWORD',
               'dbname':'PGDATABASE','hostaddr':'PGHOSTADDR','sslmode':'PGSSLMODE',
               'sslcert':'PGSSLCERT','sslkey':'PGSSLKEY','sslrootcert':'PGSSLROOTCERT',
               'sslcrl':'PGSSLCRL','connect_timeout':'PGCONNECT_TIMEOUT',
               'options':'PGOPTIONS','application_name':'PGAPPNAME',
               'target_session_attrs':'PGTARGETSESSIONATTRS','channel_binding':'PGCHANNELBINDING',
               'service':'PGSERVICE','passfile':'PGPASSFILE'}
    result = {k:v for k,v in os.environ.items() if k in {'PATH','LANG','LC_ALL','HOME'}}
    for key,value in parse_dsn(dsn).items():
        if key not in mapping:
            raise ValueError('Unsupported connection parameter; credentials not printed')
        result[mapping[key]] = value
    result['PGAPPNAME'] = 'gpm-managed-backup'
    result.setdefault('PGCONNECT_TIMEOUT','15')
    return result

def checked(command, log, **kwargs):
    with log.open('ab') as stream:
        subprocess.run(command, stdout=stream, stderr=stream, check=True, **kwargs)

def add_path(archive, source, target, records):
    """Hash precisely the bytes written; never follow symlinks implicitly."""
    source = Path(source)
    info = archive.gettarinfo(str(source), arcname=target)
    if info.isdir():
        archive.addfile(info)
        for child in sorted(source.iterdir()):
            add_path(archive, child, target+'/'+child.name, records)
    elif info.issym():
        archive.addfile(info)
        records.append({'path':target,'symlink':info.linkname})
    elif info.isfile():
        before = source.stat()
        digest = hashlib.sha256()
        class HashingReader:
            def __init__(self, stream): self.stream = stream
            def read(self, size=-1):
                chunk = self.stream.read(size)
                digest.update(chunk)
                return chunk
        with source.open('rb') as stream:
            archive.addfile(info, HashingReader(stream))
        after = source.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise RuntimeError('A source file changed while being copied')
        records.append({'path':target,'bytes':info.size,'sha256':digest.hexdigest()})
    else:
        raise RuntimeError('Unsupported filesystem object in backup scope')

def nginx_configs(host):
    matches = set()
    for folder in [Path('/etc/nginx/sites-enabled'),Path('/etc/nginx/sites-available'),Path('/etc/nginx/conf.d')]:
        if folder.is_dir():
            for path in folder.iterdir():
                if path.is_file() and host in path.read_text(errors='replace'):
                    matches.add(path.resolve())
    return sorted(matches)

def backend_dump(raw):
    sys.path.insert(0,str(ROOT))
    from app import app_orders_api as api
    import psycopg2
    from psycopg2 import extensions, sql
    if Path.cwd().resolve()!=ROOT or os.getenv('GPM_APP_ENV')!='production':
        raise RuntimeError('Unexpected backend runtime')
    dsn = api.postgres_dsn()
    if not dsn:
        raise RuntimeError('Missing production PostgreSQL connection')
    conn = psycopg2.connect(dsn)
    try:
        conn.set_session(isolation_level='REPEATABLE READ',readonly=True)
        with conn.cursor() as cursor:
            cursor.execute('SHOW server_version_num')
            major = int(cursor.fetchone()[0])//10000
            cursor.execute('SELECT pg_export_snapshot()')
            snapshot = cursor.fetchone()[0]
            cursor.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY schemaname,tablename")
            tables = cursor.fetchall()
            counts = {}
            for schema,table in tables:
                cursor.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(table)))
                counts[schema+'.'+table] = cursor.fetchone()[0]
            binaries = Path('/usr/lib/postgresql')/str(major)/'bin'
            dump = raw/'database.dump'
            checked([str(binaries/'pg_dump'),'--format=custom','--lock-wait-timeout=15s',
                     '--snapshot='+snapshot,'--file='+str(dump)],raw/'private-diagnostics.log',
                    env=child_env(dsn,extensions.parse_dsn),timeout=900)
            checked([str(binaries/'pg_restore'),'--list',str(dump)],raw/'dump-toc.txt',timeout=60)
    finally:
        conn.rollback()
        conn.close()
    uploads = api.private_upload_dir()
    if not uploads.is_absolute() or not uploads.is_dir():
        raise RuntimeError('Private uploads directory missing')
    for folder,dirs,files in os.walk(uploads,followlinks=False):
        for name in dirs+files:
            if (Path(folder)/name).is_symlink():
                raise RuntimeError('Private uploads symlink requires an explicit scope review')
    return {'postgres_major':major,'table_counts':counts,
            'backend_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()},uploads

def create_backup(component,run_id,recipient,age_binary):
    os.umask(0o077)
    validate_run(run_id)
    validate_recipient(recipient)
    base = BASES[component]
    base.mkdir(parents=True,mode=0o700,exist_ok=True)
    if base.resolve()!=base or age_binary.resolve().parent.name != 'gpm-backup-tools-'+run_id:
        raise RuntimeError('Unexpected backup/tool path')
    out = base/(component+'-'+run_id)
    out.mkdir(mode=0o700,exist_ok=False)
    raw = out/'private-staging'
    raw.mkdir(mode=0o700)
    payload = raw/'payload.tar.gz'
    manifest = {'format':'gpm-production-backup-v1','component':component,'run_id':run_id,
                'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'files':[],'consistency':'DB uses one exported repeatable-read snapshot; file copy is live and separate'}
    stage = 'preflight'
    try:
        if shutil.disk_usage(base).free < 256*1024*1024:
            raise RuntimeError('Insufficient free backup space')
        if component=='backend':
            stage='database-dump'
            details,uploads = backend_dump(raw)
            manifest.update(details)
            checked(['git','bundle','create',str(raw/'repository.bundle'),'--all'],raw/'private-diagnostics.log',cwd=ROOT,timeout=120)
        stage='archive-files'
        with tarfile.open(payload,'w:gz',dereference=False) as archive:
            for path in sorted(raw.iterdir()):
                if path!=payload:
                    add_path(archive,path,'backup/'+path.name,manifest['files'])
            if component=='backend':
                for child in sorted(ROOT.iterdir()):
                    if child.name not in {'.git','.venv','__pycache__','.dart_tool','build'}:
                        add_path(archive,child,'repository/'+child.name,manifest['files'])
                add_path(archive,uploads,'filesystem'+str(uploads),manifest['files'])
                config_paths = [Path('/root/gpm-app-env')]
                for optional in ['/root/gpm-app-login.txt','/etc/systemd/system/gpm-app-api.service']:
                    if Path(optional).is_file():config_paths.append(Path(optional))
                dropins=Path('/etc/systemd/system/gpm-app-api.service.d')
                if dropins.is_dir():config_paths.extend(dropins.glob('*.conf'))
                config_paths.extend(nginx_configs('app-api.gpmbot.ru'))
                for path in sorted(set(config_paths)):
                    add_path(archive,path.resolve(),'filesystem'+str(path),manifest['files'])
            else:
                if FRONT.resolve()!=FRONT or not (FRONT/'index.html').is_file() or not (FRONT/'main.dart.js').is_file():
                    raise RuntimeError('Unexpected frontend runtime')
                add_path(archive,FRONT,'filesystem'+str(FRONT),manifest['files'])
                for path in nginx_configs('app.gpmbot.ru'):
                    add_path(archive,path,'filesystem'+str(path),manifest['files'])
            manifest_file=raw/'manifest.json'
            manifest_file.write_text(json.dumps(manifest,indent=2)+'\n')
            archive.add(manifest_file,arcname='manifest.json',recursive=False)
        stage='encrypt'
        encrypted=out/(component+'.tar.gz.age')
        checked([str(age_binary),'--encrypt','--recipient',recipient,'--output',str(encrypted),str(payload)],
                raw/'private-encryption.log',timeout=900)
        result={'component':component,'run_id':run_id,'bytes':encrypted.stat().st_size,
                'sha256':sha(encrypted),'age_recipient':recipient,
                'created_at_utc':manifest['created_at_utc']}
        (out/'encrypted-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'ok':True,**result}),flush=True)
    except Exception:
        print('Backup failed at stage='+stage+'; private contents/credentials were not printed.',file=sys.stderr)
        raise
    finally:
        # Only this newly created run's disposable plaintext staging is removed.
        if raw.parent==out and raw.name=='private-staging' and not raw.is_symlink():
            shutil.rmtree(raw)

def inspect():
    if Path.cwd().resolve() != ROOT or os.getenv('GPM_APP_ENV') != 'production':
        raise RuntimeError('Unexpected runtime scope')
    sys.path.insert(0, str(ROOT))
    from app import app_orders_api as api
    import psycopg2
    with psycopg2.connect(api.postgres_dsn()) as connection:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor() as cursor:
            cursor.execute('SHOW server_version')
            version = cursor.fetchone()[0]
            cursor.execute('SELECT pg_database_size(current_database())')
            db_bytes = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
            tables = cursor.fetchone()[0]
            cursor.execute('SELECT extname FROM pg_extension ORDER BY extname')
            extensions = [r[0] for r in cursor.fetchall()]
    versions = {}
    for name in ['pg_dump', 'pg_restore', 'pg_config']:
        binary = shutil.which(name)
        versions[name] = subprocess.check_output([binary, '--version'], text=True).strip() if binary else None
    uploads = api.private_upload_dir()
    upload_bytes = 0
    upload_files = 0
    if uploads.is_dir():
        for folder, dirs, files in os.walk(uploads, followlinks=False):
            for name in files:
                p = Path(folder)/name
                if p.is_file() and not p.is_symlink():
                    upload_bytes += p.stat().st_size
                    upload_files += 1
    head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git','status','--porcelain','--untracked-files=no'], cwd=ROOT, text=True)
    major = version.split('.')[0]
    print(json.dumps({'operation':'inspect', 'backend_head':head, 'tracked_changes':len(dirty.splitlines()),
        'postgres_version':version,'database_bytes':db_bytes,'public_tables':tables,'extensions':extensions,
        'tools':versions,'matching_initdb_exists':Path('/usr/lib/postgresql/'+major+'/bin/initdb').is_file(),
        'uploads_dir':str(uploads),'uploads_exists':uploads.is_dir(),'upload_files':upload_files,'upload_bytes':upload_bytes,
        'disk_free_bytes':shutil.disk_usage(ROOT).free,
        'service_active':subprocess.run(['systemctl','is-active','--quiet','gpm-app-api.service']).returncode==0},indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--operation',choices=['inspect','backup'],required=True)
    parser.add_argument('--component',choices=['backend','frontend'],default='backend')
    parser.add_argument('--run-id')
    parser.add_argument('--recipient')
    parser.add_argument('--age-binary',type=Path)
    args=parser.parse_args()
    try:
        if args.operation == 'inspect':inspect()
        else:create_backup(args.component,args.run_id,args.recipient,args.age_binary)
    except Exception as error:
        print('Production backup operation failed ('+type(error).__name__+'); no credentials printed.',file=sys.stderr)
        raise SystemExit(1)

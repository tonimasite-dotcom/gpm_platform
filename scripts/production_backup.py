#!/usr/bin/env python3
"""Read-only production discovery; backup implementation follows after discovery."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path('/opt/gpm/gpm_platform')

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
    args=parser.parse_args()
    try:
        if args.operation != 'inspect':
            raise RuntimeError('Backup not enabled until inspection completes')
        inspect()
    except Exception as error:
        print('Production backup inspection failed ('+type(error).__name__+'); no credentials printed.',file=sys.stderr)
        raise SystemExit(1)

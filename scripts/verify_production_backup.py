#!/usr/bin/env python3
"""Decrypt privately, hash every file, and restore only in a network-isolated container."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import time

POSTGRES_IMAGE = 'postgres@sha256:1a66d744c1b459e13b05a8fca341da84cb63383e99ce262210efee5a319d4551'

def run(args, **kwargs):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, **kwargs).stdout

def inspect_tar(path, dump_destination=None):
    with tarfile.open(path, 'r:gz') as archive:
        names = [m.name for m in archive.getmembers()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive paths')
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts:
                raise ValueError('Unsafe archive path')
        member = archive.getmember('manifest.json')
        if not member.isfile() or member.size > 16 * 1024 * 1024:
            raise ValueError('Invalid encrypted manifest')
        manifest = json.loads(archive.extractfile(member).read())
        if manifest.get('format') != 'gpm-production-backup-v1':
            raise ValueError('Unsupported backup format')
        expected = {r['path']:r for r in manifest['files']}
        if len(expected) != len(manifest['files']):
            raise ValueError('Duplicate inventory paths')
        actual = set()
        for member in archive.getmembers():
            if member.isdir() or member.name == 'manifest.json':
                continue
            record = expected.get(member.name)
            if record is None:
                raise ValueError('Archive entry missing from inventory')
            actual.add(member.name)
            if member.issym():
                if record.get('symlink') != member.linkname:
                    raise ValueError('Symlink mismatch')
                continue
            if not member.isfile():
                raise ValueError('Unsupported archive entry')
            digest = hashlib.sha256()
            count = 0
            output = dump_destination.open('wb') if member.name == 'backup/database.dump' and dump_destination else None
            try:
                with archive.extractfile(member) as source:
                    for chunk in iter(lambda: source.read(1024*1024), b''):
                        digest.update(chunk)
                        count += len(chunk)
                        if output: output.write(chunk)
            finally:
                if output: output.close()
            if count != record['bytes'] or digest.hexdigest() != record['sha256']:
                raise ValueError('Backup file checksum mismatch')
        if actual != set(expected):
            raise ValueError('Missing archive entries')
    return manifest

def restore_and_compare(dump, manifest):
    if manifest['postgres_major'] != 16:
        raise ValueError('A matching isolated restore image is required')
    name = 'gpm-backup-verify-'+str(os.getpid())
    print('restore_stage=pull-isolated-image',flush=True)
    run(['docker','pull',POSTGRES_IMAGE], timeout=300)
    try:
        run(['docker','run','--detach','--rm','--network','none','--memory','1g','--cpus','2',
             '--name',name,'-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_DB=gpm_verify',POSTGRES_IMAGE], timeout=60)
        for _ in range(60):
            probe = subprocess.run(['docker','exec',name,'pg_isready','-h','127.0.0.1','-U','postgres','-d','gpm_verify'],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if probe.returncode == 0: break
            time.sleep(1)
        else: raise RuntimeError('Isolated PostgreSQL did not become ready')
        print('restore_stage=import-into-isolated-container',flush=True)
        run(['docker','cp',str(dump),name+':/tmp/production.dump'], timeout=120)
        run(['docker','exec',name,'chown','postgres:postgres','/tmp/production.dump'])
        run(['docker','exec','-u','postgres',name,'pg_restore','--exit-on-error','--no-owner','--no-privileges',
             '--dbname=gpm_verify','/tmp/production.dump'], timeout=900)
        def query(sql):
            return run(['docker','exec','-u','postgres',name,'psql','-X','-A','-t','-q','-v','ON_ERROR_STOP=1',
                        '-d','gpm_verify','-c',sql], timeout=120).decode().strip()
        actual_tables = set(query("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1").splitlines())
        print('restore_stage=compare-source-snapshot',flush=True)
        if actual_tables != set(manifest['table_counts']):
            raise RuntimeError('Restored table set differs from source snapshot')
        for table, expected in manifest['table_counts'].items():
            schema, name_part = table.split('.',1)
            identifier = '"'+schema.replace('"','""')+'"."'+name_part.replace('"','""')+'"'
            if int(query('SELECT count(*) FROM '+identifier)) != expected:
                raise RuntimeError('Restored row count differs from the source snapshot')
        # Indexes, constraints, sequences and data were all accepted by pg_restore --exit-on-error.
        return len(actual_tables)
    finally:
        subprocess.run(['docker','rm','--force',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--identity',type=Path,required=True)
    parser.add_argument('--age',type=Path,required=True)
    parser.add_argument('--skip-database-restore',action='store_true',help='Local decryption/hash check only; never claimed as restore validation')
    args=parser.parse_args()
    os.umask(0o077)
    results=[]
    with tempfile.TemporaryDirectory(prefix='gpm-private-verification-',dir=args.artifacts.parent) as temporary:
        temp=Path(temporary)
        for component in ['backend','frontend']:
            encrypted=args.artifacts/(component+'.tar.gz.age')
            public=json.loads((args.artifacts/(component+'-manifest.json')).read_text())
            digest=hashlib.sha256()
            with encrypted.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            if encrypted.stat().st_size!=public['bytes'] or digest.hexdigest()!=public['sha256']:
                raise ValueError('Encrypted backup does not match server checksum')
            plain=temp/(component+'.tar.gz')
            run([str(args.age),'--decrypt','--identity',str(args.identity),'--output',str(plain),str(encrypted)], timeout=900)
            dump=temp/'database.dump' if component=='backend' else None
            manifest=inspect_tar(plain,dump)
            if manifest['component']!=component or manifest['run_id']!=public['run_id']:
                raise ValueError('Backup component/run mismatch')
            verified=restore_and_compare(dump,manifest) if component=='backend' and not args.skip_database_restore else None
            required = {'filesystem/var/www/gpm-app/index.html','filesystem/var/www/gpm-app/main.dart.js'} if component=='frontend' else {'backup/database.dump','filesystem/root/gpm-app-env'}
            if not required.issubset({r['path'] for r in manifest['files']}):
                raise ValueError('Essential backup files missing')
            results.append({'component':component,'file_hashes_verified':True,'file_count':len(manifest['files']),
                            'restore_tables_verified':verified,'run_id':manifest['run_id'],
                            'backend_head':manifest.get('backend_head')})
            plain.unlink()
            if dump:dump.unlink()
    summary={'ok':True,'decryption_verified':True,'isolated_database_restore':not args.skip_database_restore,
             'restore_image':POSTGRES_IMAGE if not args.skip_database_restore else None,'components':results}
    (args.artifacts/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Backup verification failed ('+type(error).__name__+'); decrypted data and credentials were not printed.',flush=True)
        raise SystemExit(1)

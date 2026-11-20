import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'

def load(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

backup=load('production_backup')
verify=load('verify_production_backup')

class ProductionBackupTests(unittest.TestCase):
    def test_run_scope_and_native_recipient_guards(self):
        self.assertEqual(backup.validate_run('123456-1'),'123456-1')
        for bad in ['../12345','123456-1/../../','main','12345;true']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):backup.validate_run(bad)
        recipient='age1'+'q'*58
        self.assertEqual(backup.validate_recipient(recipient),recipient)
        for bad in [recipient+'\n',recipient+';true','ssh-ed25519 KEY','AGE-SECRET-KEY-'+('X'*58)]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):backup.validate_recipient(bad)

    def test_pg_child_environment_does_not_inherit_app_credentials(self):
        from unittest.mock import patch
        with patch.dict('os.environ',{'GPM_APP_API_TOKEN':'synthetic-private-api-token','PGDATABASE':'wrong-source'},clear=True):
            child=backup.child_env('not-printed',lambda _: {'host':'127.0.0.1','password':'synthetic-password','dbname':'expected'})
        self.assertNotIn('GPM_APP_API_TOKEN',child)
        self.assertEqual(child['PGDATABASE'],'expected')
        self.assertEqual(child['PGPASSWORD'],'synthetic-password')
        with self.assertRaises(ValueError):backup.child_env('',lambda _: {'unsupported':'value'})

    def test_archived_bytes_and_manifest_verify(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            payload=folder/'example.txt'
            payload.write_bytes(b'synthetic backup content')
            records=[]
            target=folder/'backup.tar.gz'
            with tarfile.open(target,'w:gz') as archive:
                backup.add_path(archive,payload,'repository/example.txt',records)
                manifest=json.dumps({'format':'gpm-production-backup-v1','files':records}).encode()
                member=tarfile.TarInfo('manifest.json');member.size=len(manifest)
                archive.addfile(member,io.BytesIO(manifest))
            restored=verify.inspect_tar(target)
            self.assertEqual(restored['files'][0]['sha256'],hashlib.sha256(payload.read_bytes()).hexdigest())

    def make_archive(self,path,filename,data,bad_hash=False,duplicate=False):
        record={'path':filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        if bad_hash:record['sha256']='0'*64
        manifest=json.dumps({'format':'gpm-production-backup-v1','files':[record]}).encode()
        with tarfile.open(path,'w:gz') as archive:
            for name,content in [('manifest.json',manifest),(filename,data)]+([(filename,data)] if duplicate else []):
                item=tarfile.TarInfo(name);item.size=len(content);archive.addfile(item,io.BytesIO(content))

    def test_corruption_duplicate_and_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'test.tar.gz'
            for args in [('safe',b'data',True,False),('safe',b'data',False,True),('../outside',b'data',False,False),('/outside',b'data',False,False)]:
                self.make_archive(target,*args)
                with self.subTest(args=args),self.assertRaises(ValueError):verify.inspect_tar(target)

    def test_registration_preview_online_snapshot_is_separate_and_recoverable(self):
        import sqlite3
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'; root.mkdir()
            private = root / '.registration_preview_private'; private.mkdir()
            live = private / 'state.sqlite3'
            with sqlite3.connect(live) as db:
                for name in ('preview_sessions','preview_profiles','preview_events'):
                    db.execute('CREATE TABLE '+name+' (id TEXT)')
                    db.execute('INSERT INTO '+name+' VALUES (?)', ('synthetic',))
            stage = Path(temp) / 'snapshot'; stage.mkdir()
            with patch.object(backup, 'ROOT', root), patch.dict('os.environ', {}, clear=True):
                details = backup.snapshot_registration_preview(stage)
            with sqlite3.connect(live) as db:
                db.execute('INSERT INTO preview_sessions VALUES (?)', ('later',))
            snapshot = stage / 'registration-preview.sqlite3'
            with sqlite3.connect(snapshot) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM preview_sessions').fetchone()[0], 1)
            target = Path(temp) / 'archive.tar.gz'; records = []
            with tarfile.open(target,'w:gz') as archive:
                backup.add_path(archive,snapshot,'backup/registration-preview.sqlite3',records)
                data = json.dumps({'format':'gpm-production-backup-v1','files':records,**details}).encode()
                member = tarfile.TarInfo('manifest.json'); member.size=len(data)
                archive.addfile(member,io.BytesIO(data))
            restored = Path(temp) / 'restored'; restored.mkdir()
            manifest = verify.inspect_tar(target, restored/'database.dump')
            self.assertTrue(manifest['registration_preview_verified'])

if __name__=='__main__':unittest.main()

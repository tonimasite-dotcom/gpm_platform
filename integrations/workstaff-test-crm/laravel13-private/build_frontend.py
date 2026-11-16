"""Build the synthetic candidate frontend offline, using retained private dependencies."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path

BASE=Path('/root/gpm-ts-runtime-20261113-01')
CANDIDATE=BASE/'rootfs/work/crm-private-01'
TOOLCHAIN=Path('/root/gpm-ts-update/order-parity-20261111-04/frontend-build')
BUILD=BASE/'frontend-build-20261116-01'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume-build',action='store_true');parser.add_argument('--attempt',default='02');args=parser.parse_args()
    if len(args.attempt)!=2 or not args.attempt.isdigit():raise RuntimeError('TWO_DIGIT_ATTEMPT_REQUIRED')
    os.umask(0o077)
    if CANDIDATE.resolve()!=CANDIDATE or not (CANDIDATE/'PRIVATE_BOT_FIXTURE').is_file():
        raise RuntimeError('MARKED_SYNTHETIC_CANDIDATE_REQUIRED')
    if os.readlink('/proc/self/ns/net')==os.readlink('/proc/1/ns/net'):
        raise RuntimeError('OFFLINE_NETWORK_NAMESPACE_REQUIRED')
    if BUILD.is_symlink() or shutil.disk_usage(str(BASE)).free<3*1024**3 or (BUILD/'result.json').exists():
        raise RuntimeError('NEW_BUILD_DIRECTORY_AND_THREE_GIB_RESERVE_REQUIRED')
    if args.resume_build:
        if not BUILD.is_dir() or (BUILD/'node_modules').resolve()!=(TOOLCHAIN/'node_modules').resolve():
            raise RuntimeError('EXACT_EXISTING_PRIVATE_BUILD_REQUIRED')
        for path in (CANDIDATE/'resources').rglob('*'):
            if path.is_file():
                copied=BUILD/path.relative_to(CANDIDATE)
                if not copied.is_file() or hashlib.sha256(path.read_bytes()).digest()!=hashlib.sha256(copied.read_bytes()).digest():
                    raise RuntimeError('RESOURCES_CHANGED_SINCE_FAILED_BUILD')
        if json.loads((BUILD/'unit.stdout').read_text())['status']!='PASS':
            raise RuntimeError('EXISTING_PASSED_CONTRACT_TEST_REQUIRED')
    else:
        BUILD.mkdir(mode=0o700)
        shutil.copytree(str(CANDIDATE/'resources'),str(BUILD/'resources'),symlinks=True)
        for name in ['package.json','package-lock.json','.babelrc','webpack.mix.js']:
            source=TOOLCHAIN/name
            if source.is_symlink() or not source.is_file():raise RuntimeError('RETAINED_TOOLCHAIN_REQUIRED')
            shutil.copyfile(str(source),str(BUILD/name))
        for name in ['artisan','composer.json']:
            shutil.copyfile(str(CANDIDATE/name),str(BUILD/name))
        config=BUILD/'webpack.mix.js'
        with config.open('a') as stream:
            stream.write("\n// Isolated build output and bounded minifier concurrency.\nmix.setPublicPath('public')\nmix.options({ terser: { parallel: false } })\n")
        (BUILD/'public').mkdir()
        (BUILD/'node_modules').symlink_to(TOOLCHAIN/'node_modules',target_is_directory=True)
        shutil.copyfile(str(Path(__file__).parent/'frontend_contract_test.js'),str(BUILD/'frontend_contract_test.js'))
        unit=subprocess.run(['node',str(BUILD/'frontend_contract_test.js'),str(BUILD)],cwd=str(BUILD),
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        (BUILD/'unit.stdout').write_bytes(unit.stdout);(BUILD/'unit.stderr').write_bytes(unit.stderr)
        if unit.returncode:raise RuntimeError('FRONTEND_CONTRACT_TEST_FAILED')
        print(unit.stdout.decode(),flush=True)
    clean_env={'PATH':'/usr/local/bin:/usr/bin:/bin','NODE_ENV':'production',
        'NODE_OPTIONS':'--max-old-space-size=3072','NPM_CONFIG_USERCONFIG':'/dev/null',
        'npm_config_cache':str(BUILD/'.npm-cache')}
    prefix='build-'+args.attempt if args.resume_build else 'build'
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    with (BUILD/(prefix+'.stdout')).open('xb') as out,(BUILD/(prefix+'.stderr')).open('xb') as err:
        result=subprocess.run(['nice','-n','10','npm','run','production'],cwd=str(BUILD),env=clean_env,
                              stdout=out,stderr=err,timeout=900)
    if result.returncode:raise RuntimeError('PRIVATE_FRONTEND_BUILD_FAILED_INSPECT_PRIVATE_LOGS')
    public=BUILD/'public';manifest=json.loads((public/'mix-manifest.json').read_text())
    if set(manifest)!={'/dist/js/app.js','/dist/css/app.css'}:
        raise RuntimeError('EXPECTED_LARAVEL_ASSET_KEYS_REQUIRED')
    assets=[]
    for key,value in manifest.items():
        path=public/value.lstrip('/').split('?')[0]
        if public not in path.resolve().parents or not path.is_file():
            raise RuntimeError('GENERATED_ASSET_MISSING_OR_OUTSIDE_BUILD')
        assets.append({'key':key,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size})
    result={'status':'PASS','private_build_only':True,'resources_from_current_candidate':True,
        'toolchain_source':'retained_private_TS_build','toolchain_verified_against_current_main':False,
        'external_network_disabled':True,'live_files_changed':False,'manifest_entries':len(manifest),'assets':assets,
        'free_bytes_after':shutil.disk_usage(str(BASE)).free}
    (BUILD/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()

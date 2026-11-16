"""Retain TS's existing SCSS inputs and Laravel build markers in the private build.

The deployed primary source contains neither SCSS nor its package/build config.
This is TS styling preservation, not a claim of matching primary build tooling.
"""
import hashlib,json,os,shutil
from pathlib import Path

BASE=Path('/root/gpm-ts-runtime-20261113-01')
CANDIDATE=BASE/'rootfs/work/crm-private-01'
BUILD=BASE/'frontend-build-20261116-01'
RETAINED=Path('/root/gpm-ts-update/order-parity-20261111-04/frontend-build')

def main():
    os.umask(0o077)
    if not (CANDIDATE/'PRIVATE_BOT_FIXTURE').is_file() or CANDIDATE.resolve()!=CANDIDATE or BUILD.resolve()!=BUILD:
        raise RuntimeError('MARKED_SYNTHETIC_AND_EXISTING_PRIVATE_BUILD_REQUIRED')
    report=BASE/'frontend-retained-inputs-20261116-01.json'
    if report.exists():raise RuntimeError('INPUT_RESTORE_REPORT_ALREADY_EXISTS')
    source=RETAINED/'resources/sass'
    files=sorted(path for path in source.rglob('*') if path.is_file())
    if not files:raise RuntimeError('RETAINED_TS_STYLES_REQUIRED')
    rows=[]
    for path in files:
        if path.is_symlink() or path.suffix not in ['.scss','.sass'] or RETAINED not in path.resolve().parents:
            raise RuntimeError('REGULAR_TS_STYLES_ONLY')
        relative=path.relative_to(RETAINED)
        for root in [CANDIDATE,BUILD]:
            target=root/relative
            if target.exists():raise RuntimeError('STYLE_DESTINATION_ALREADY_EXISTS')
        rows.append({'file':str(relative),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    for row in rows:
        for root in [CANDIDATE,BUILD]:
            target=root/row['file'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(str(RETAINED/row['file']),str(target))
    for name in ['artisan','composer.json']:
        target=BUILD/name
        if target.exists():raise RuntimeError('BUILD_MARKER_ALREADY_PRESENT')
        shutil.copyfile(str(CANDIDATE/name),str(target))
    result={'private_only':True,'live_files_changed':False,'retained_ts_styles':rows,
            'laravel_build_markers_restored':True,'primary_style_source_available':False}
    report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()

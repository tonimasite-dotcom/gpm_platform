#!/usr/bin/env python3
"""Offline release inventory. Secrets/state contents stay out of reports."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
ROOT = WORK/'candidate'
EXPECTED_CODE = 'dce57370efff2615fafde248addfb7808f13a0560254f2fb4e3982fd7a661b5d'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def semantic_hash(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    os.umask(0o077)
    if ROOT.resolve() != ROOT or WORK.resolve() != WORK or not (ROOT/'storage/framework/down').is_file():
        raise RuntimeError('PRIVATE_CANDIDATE_REQUIRED')
    destinations = [WORK/'candidate-vendor-manifest-order-forms-20261109.json',
        WORK/'candidate-release-inventory-20261109.json']
    if any(path.exists() for path in destinations):
        raise RuntimeError('NEW_REPORT_REQUIRED')
    code = json.loads((WORK/'candidate-manifest-order-forms-20261109.json').read_text())
    if semantic_hash(code) != EXPECTED_CODE:
        raise RuntimeError('CODE_MANIFEST_MISMATCH')
    for relative, expected in code.items():
        path = ROOT/relative
        if path.resolve() != path or digest(path) != expected:
            raise RuntimeError('CODE_CONTENT_MISMATCH')
    vendor = ROOT/'vendor'
    if vendor.resolve() != vendor or not vendor.is_dir():
        raise RuntimeError('PRIVATE_VENDOR_REQUIRED')
    entries = {}
    byte_count = 0
    internal_links = 0
    for directory, subdirs, files in os.walk(str(vendor), followlinks=False):
        for name in subdirs + files:
            path = Path(directory)/name
            if path.is_symlink():
                target = path.resolve(strict=True)
                if vendor not in target.parents:
                    raise RuntimeError('EXTERNAL_VENDOR_LINK_REQUIRES_REVIEW')
                entries[str(path.relative_to(ROOT))] = {'type': 'symlink', 'target': os.readlink(str(path)),
                    'resolved_relative_path': str(target.relative_to(ROOT))}
                internal_links += 1
        for name in files:
            path = Path(directory)/name
            if path.is_symlink():
                continue
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise RuntimeError('UNEXPECTED_VENDOR_OBJECT')
            entries[str(path.relative_to(ROOT))] = {'sha256': digest(path),
                'bytes': info.st_size, 'mode': stat.S_IMODE(info.st_mode)}
            byte_count += info.st_size
    lock = json.loads((ROOT/'composer.lock').read_text())
    installed = json.loads((vendor/'composer/installed.json').read_text())
    installed = installed.get('packages', []) if isinstance(installed, dict) else installed
    installed_map = {item['name']: item['version'] for item in installed}
    mismatches = [item['name'] for item in lock['packages']
        if installed_map.get(item['name']) != item['version']]
    if mismatches:
        raise RuntimeError('PRODUCTION_COMPOSER_LOCK_MISMATCH')
    # Read only literal activation/state path references from source, never data values.
    referenced = set()
    dynamic_references = 0
    for path in (ROOT/'app/Services').rglob('*.php'):
        source = path.read_text()
        for literal in re.findall(r"storage_path\(['\"]([^'\"]+\.json)['\"]\)", source):
            if re.fullmatch(r'app/[a-z0-9_./-]+\.json', literal) and '..' not in literal.split('/'):
                referenced.add(literal)
        dynamic_references += len(re.findall(r'storage_path\(\s*self::', source))
    states = []
    for relative in sorted(referenced):
        path = ROOT/'storage'/relative
        if path.is_symlink() or path.resolve() != path:
            raise RuntimeError('PRIVATE_STATE_LINK_REQUIRES_REVIEW')
        states.append({'relative_path': 'storage/'+relative, 'present': path.is_file(),
            'sha256': digest(path) if path.is_file() else None})
    assets = json.loads((ROOT/'public/mix-manifest.json').read_text())
    report = {'private_candidate_only': True, 'code_files': len(code), 'code_manifest_sha256': EXPECTED_CODE,
        'vendor_entries': len(entries), 'vendor_regular_files': len(entries)-internal_links,
        'vendor_internal_links': internal_links, 'vendor_bytes': byte_count, 'vendor_manifest_sha256': semantic_hash(entries),
        'production_composer_packages': len(lock['packages']), 'installed_packages': len(installed_map),
        'production_composer_versions_match_lock': True, 'frontend_manifest_entries': len(assets),
        'literal_state_references': states, 'dynamic_state_references_requiring_review': dynamic_references,
        'env_included_in_release': False, 'maintenance_present': True,
        'node_modules_required_at_runtime': False, 'live_crm_accessed': False,
        'state_manifest_complete': False, 'switch_and_rollback_rehearsed': False, 'release_ready': False}
    with destinations[0].open('x') as output:
        output.write(json.dumps(entries, indent=2))
    with destinations[1].open('x') as output:
        output.write(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(json.dumps({'inventory_completed': False, 'safe_code': str(error)}))
        raise SystemExit(1)

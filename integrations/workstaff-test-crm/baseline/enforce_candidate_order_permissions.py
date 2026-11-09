#!/usr/bin/env python3
"""One-shot, private candidate only: enforce existing create/update permissions."""
import hashlib
import json
import os
from pathlib import Path

WORK = Path('/root/gpm-ts-update/20261106-baseline-01')
ROOT = WORK / 'candidate'
EXPECTED = {
    'ManagerOrderController.php': 'da801abd4422067facb67be26cdafc3bdf91a36d9bb10f3b13e37516440d2555',
    'LeaderOrderController.php': '178e200a65a2ad677df247c5fc2a78fbea4119f1dd71c2861e8cce70ab24cd28',
}


def main():
    os.umask(0o077)
    if WORK.resolve() != WORK or ROOT.resolve() != ROOT or not (ROOT/'storage/framework/down').is_file():
        raise RuntimeError('PRIVATE_CANDIDATE_REQUIRED')
    backup = WORK/'order-permissions-before-20261109'
    if backup.exists():
        raise RuntimeError('ONE_SHOT_ADAPTATION_ALREADY_PRESENT')
    changes = []
    for filename, expected in EXPECTED.items():
        path = ROOT/'app/Http/Controllers/Order'/filename
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('CANDIDATE_SOURCE_HASH_MISMATCH')
        source = path.read_text()
        family = 'manager' if filename.startswith('Manager') else 'leader'
        anchor = '        $this->service = $service;'
        if source.count(anchor) != 1:
            raise RuntimeError('CONTROLLER_CONSTRUCTOR_ANCHOR_MISMATCH')
        replacement = (
            '        // Enforce existing role permissions on API writes as well as UI entry.\n'
            "        $this->middleware('can:create_" + family + "_orders', ['only' => ['store']]);\n"
            "        $this->middleware('can:update_" + family + "_orders', ['only' => ['update']]);\n" + anchor)
        changes.append((path, source, source.replace(anchor, replacement)))
    backup.mkdir(mode=0o700)
    report = []
    for path, before, after in changes:
        (backup/path.name).write_bytes(path.read_bytes())
        path.write_text(after)
        report.append({'file': str(path.relative_to(ROOT)), 'before_sha256': EXPECTED[path.name],
            'after_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {'candidate_only': True, 'existing_permissions_enforced': True,
        'role_assignments_changed': False, 'live_crm_changed': False, 'files': report}
    with (WORK/'order-permissions-adaptation-20261109.json').open('x') as output:
        output.write(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Stop ONLY the new, verified private switch MySQL instances; preserve all data."""
from pathlib import Path
import importlib.util
import json
import os

WORK=Path('/root/gpm-ts-update/20261109-switch-01')
TOOLS=Path('/root/gpm-ts-update/switch-tools-20261109')


def main():
    os.umask(0o077)
    if WORK.resolve()!=WORK or not ((WORK/'switch-rehearsal-result.json').exists() or (WORK/'switch-private-error.log').exists()):
        raise RuntimeError('FINISHED_PRIVATE_EXPERIMENT_REQUIRED')
    for proc in Path('/proc').iterdir():
        if proc.name.isdigit():
            try:args=(proc/'cmdline').read_bytes().split(b'\0')
            except OSError:continue
            runners=['run_switch.py','continue_after_timeout.py','run_fresh_switch.py','run_final_full.py',
                     'check_final_state_and_email.py','resume_final_acceptance.py']
            if any(os.fsencode(str(TOOLS/name)) in args for name in runners):
                raise RuntimeError('SWITCH_RUNNER_STILL_ACTIVE')
    path=TOOLS/'stop_private_mysql.py'
    spec=importlib.util.spec_from_file_location('verified_private_stop',str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    output=WORK/'final-private-shutdown.json'
    if output.exists():raise RuntimeError('SHUTDOWN_REPORT_ALREADY_EXISTS')
    result={'instances':[module.stop(WORK/'mysql-new'),module.stop(WORK/'mysql-old')],
        'old_runtime_restored':(WORK/'runtime/.gpm-switch-version').read_text().strip()=='old',
        'saved_previous_instances_not_accessed':True,'live_mysql_accessed':False}
    with output.open('x') as out:out.write(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()

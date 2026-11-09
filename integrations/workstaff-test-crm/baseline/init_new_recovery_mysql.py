#!/usr/bin/env python3
"""Create a NEW separate instance for the November 9 backup recovery check."""
from pathlib import Path
import init_rehearsal

WORK = Path('/root/gpm-ts-update/20261106-baseline-01/sql-recovery-20261109')


if __name__ == '__main__':
    if WORK.parent.resolve() != WORK.parent or WORK.exists() or WORK.is_symlink():
        raise RuntimeError('NEW_PRIVATE_RECOVERY_ROOT_REQUIRED')
    WORK.mkdir(mode=0o700)
    init_rehearsal.WORK = WORK
    init_rehearsal.MYSQL = WORK / 'rehearsal-mysql'
    init_rehearsal.DATABASE = 'gpm_ts_backup_20261109'
    init_rehearsal.ACCOUNT = 'gpm_ts_backup_recovery'
    init_rehearsal.main()

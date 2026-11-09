#!/usr/bin/env python3
"""Receive only into the new, empty November 9 private recovery database."""
from pathlib import Path
import restore_receiver

if __name__ == '__main__':
    restore_receiver.WORK = Path('/root/gpm-ts-update/20261106-baseline-01/sql-recovery-20261109')
    restore_receiver.main()

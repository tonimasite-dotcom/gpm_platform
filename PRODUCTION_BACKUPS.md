# Production GPM: encrypted backups and recovery

`Backup production` is separate from deployment. It runs daily at 03:00 UTC
(06:00 Moscow), or manually from **main**, in the existing `production`
environment. The same concurrency group as deployment prevents their overlap.
It never deploys the app, runs migrations/backfills, modifies production rows,
or touches either Workstaff CRM. Production SSH keys remain in Actions secrets.

## What is saved

- Backend PostgreSQL custom-format dump. `pg_export_snapshot()` and a read-only
  repeatable-read transaction keep the dump and per-table row counts consistent.
- The running backend checkout (including untracked configuration), its Git
  bundle and SHA. Regenerable `.venv`, `.git`, caches/build are excluded from
  the filesystem copy; Git history is in the bundle, dependencies in lock files.
- `/root/gpm-app-env`, optional login file, the app systemd unit/drop-ins and
  matching Nginx configs. Private uploads from the configured absolute path
  are included; unexpected upload symlinks stop the run for scope review.
- The actual frontend files under `/var/www/gpm-app` and matching Nginx configs.
- An encrypted manifest with every file's SHA-256, symlinks, DB table counts,
  backend SHA, timestamps and consistency notes.

This is an application recovery backup, not an image of the operating system.
TLS/SSH private keys, external SDKs/venvs and unrelated databases/sites are not
copied. Provision the OS, PostgreSQL roles, TLS and services separately when
rebuilding a host. Live files and DB are copied at separate moments; changing
files cause failure rather than an unreported corrupt copy. A filesystem/DB
single-instant snapshot would require a separately planned maintenance window.

## Encryption, locations and retention

[age v1.3.2](https://github.com/FiloSottile/age/releases/tag/v1.3.2) is pinned by
official release SHA-256. Encryption occurs **on each production host** before
transfer. Disposable plaintext staging is root-only and removed in `finally`.

- Backend: `/opt/gpm/backups/managed-v1/backend-<run_id>-<attempt>/`.
- Frontend: `/opt/gpm/front-backups/managed-v1/frontend-<run_id>-<attempt>/`.
- Off-server: Actions artifact
  `gpm-production-encrypted-<run_id>-<attempt>`, retention **30 days**.
  Only `.age` ciphertext, nonsecret checksum/verification metadata are uploaded.
- Host copies and preexisting backups are **not automatically deleted**.
  The workflow stops if free disk is below 256 MiB; monitor disk usage and
  explicitly agree host retention before adding deletion. Off-server copies
  expire after 30 days, so retain any particular milestone separately.

`GPM_BACKUP_AGE_RECIPIENT` is a production **variable**, containing only the
public encryption recipient. `GPM_BACKUP_AGE_IDENTITY` is a production **secret**,
used privately for verification/recovery. It is not committed or logged.
Its second copy is on the owner's original computer, in the ACL-restricted
`.tmp/production-backup-20261015/age-identity.txt`, outside Git. Keep an additional
owner-controlled recovery copy in a password manager/offline secure store;
loss of both the GitHub secret/account and local key makes decryption impossible.

The repository is public. Neither plaintext backups nor the decryption key
may be uploaded as artifacts, logs, releases or source files. Existing GitHub
secret permissions must be retained. An encrypted artifact by itself does not
expose database contents to a repository visitor.

## What verification actually proves

The runner decrypts into private temporary files, verifies every archive member
against its encrypted manifest, and restores the database into a disposable
PostgreSQL **16** Docker container. The image is pinned to
`postgres@sha256:1a66d744c1b459e13b05a8fca341da84cb63383e99ce262210efee5a319d4551`.
The container has **no network**, no production mounts or credentials, and no
published ports. Restore uses `--exit-on-error --no-owner --no-privileges`.
The complete table set and every table's row count must match the source snapshot.
The container and decrypted temporary files are removed afterwards.

An off-server artifact is published only after those checks succeed. Public
`verification.json` records file verification, table count, source SHA and
restore image; it does not contain business rows or per-table row counts.
Public health checks follow. No application login/sessions are created.

This verifies archive integrity and PostgreSQL reconstruction, including accepted
indexes/constraints/sequences. It is not a complete app smoke test of a rebuilt
host; that requires a separately configured isolated application and domain.

For PostgreSQL server-major upgrades, update and verify the pinned restore image
before relying on new scheduled backups. The tool refuses an unsupported major.

## Recovering from another computer

Download the encrypted artifact and `SHA256SUMS.txt` from a successful run;
verify the hashes before recovery. Source of the tool is
`scripts/verify_production_backup.py`. With a local protected identity and age,
it can verify without Docker using `--skip-database-restore`; that mode is
explicitly not reported as a DB restore rehearsal.

If the original computer/key is unavailable, use the separately manual
`Recover encrypted backup` workflow to re-encrypt a saved artifact for a new
public age recipient. It uses the protected identity internally; neither the
identity nor plaintext is returned. Generate a new local key, supply only its
public recipient and the original backup run ID, and download the re-encrypted
recovery artifact. This operation does not restore or connect to production.

Before restoring a real host, inspect the encrypted manifest, prepare a separate
test environment and perform a full recovery there. Recreating roles/config,
extracting private files and restoring a live DB must be an explicitly scoped
operation; never restore over the live production database merely to test a copy.

## Monitoring

Check **Actions → Backup production** for the latest successful run and artifact.
Workflow failures use GitHub's configured notification settings. A missed run
cannot be detected by the same workflow; an independent alert channel and its
recipient require separate configuration. Do not claim notification delivery
until its destination is agreed and tested. GitHub may delay scheduled jobs;
06:00 is the nominal time, not a guaranteed exact start.

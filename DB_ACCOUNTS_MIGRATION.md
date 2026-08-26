# DB-backed accounts migration

This runbook describes the first backward-compatible migration from the three
production bootstrap credentials to database-backed accounts. It does not
authorize a production deployment or the use of real personal data.

## What the migration creates

Schema version `0001_db_accounts` creates:

- `gpm_app_accounts` — stable account IDs, normalized unique usernames,
  versioned `scrypt` password hashes, server-owned roles, activation state,
  login failure counters, lockout timestamps and token versions;
- `gpm_app_sessions` — server-side sessions tied to an account and token
  version, with expiry and revocation timestamps;
- `gpm_app_audit_log` — append-only application events for account bootstrap,
  login attempts and logout;
- `gpm_app_schema_migrations` — applied schema versions.
- `gpm_app_account_invitations` — one-time hashed invitations for closed
  onboarding; see `INVITE_REGISTRATION.md`.

JWTs now contain a stable account ID and session ID. Every authenticated request
checks that the account is active, the token versions match and the session has
not expired or been revoked. Five consecutive failed password checks lock the
account for 15 minutes. Password verification runs outside the async event loop.

## First production deployment

1. Keep the existing `GPM_APP_CLIENT_*`, `GPM_APP_WORKER_*` and
   `GPM_APP_LOGIST_*` values in the root-owned production environment. Do not
   print or copy them into logs.
2. Create the normal database and private environment backups required by
   `PRODUCTION_DEPLOYMENT.md`.
3. Deploy the backend through `Deploy production`. Startup creates the schema
   transactionally and imports the configured accounts only when the accounts
   table is empty.
4. Verify health, all three logins, role isolation, logout revocation and that
   `admin/admin` still returns `401`.
5. Verify the schema version, three active accounts, non-plaintext password
   hashes, active sessions and audit events using aggregate/redacted queries
   only. Never print hashes, tokens, passwords or full audit details.
6. Keep the bootstrap environment values through the agreed rollback window.
   The previous release needs them if rollback is required.
7. After the release and rollback plan are accepted, back up the environment,
   remove only the six role bootstrap variables, restart, and repeat health and
   login checks. The database accounts remain the source of truth.

The deploy workflow accepts either valid bootstrap accounts or at least one
active DB account, while continuing to reject the legacy shared
`GPM_APP_USERNAME`, `GPM_APP_PASSWORD` and `GPM_APP_ROLE` variables.

## Rollback

The new tables are additive and the old release ignores them. Before removing
bootstrap variables, rollback can switch directly to the previous code and
environment. After removing them, restore the protected pre-removal environment
copy before starting the previous release.

Do not drop the account, session, audit or migration tables during rollback.
Their retention and possible legal-hold status must be decided separately.

## Deliberate limits of this increment

This foundation does not expose public registration, password recovery, contact
verification, account administration or subject-data deletion. Invite-only
registration is limited to pre-provisioned roles and usernames. The remaining
flows need approved product rules and separate permission/API tests before real
users are allowed. The current release status remains closed testing on
synthetic data.

# GPM Production Readiness

## Target Architecture

Orders should flow through the GPM backend, not through Bitrix24:

```text
External order system -> GPM backend -> PostgreSQL -> Flutter app
```

Bitrix24 can remain a separate sales/support CRM for incoming service requests,
but it is not the source of truth for app orders, workers, assignments, chats,
or payouts.

## Current Transition

- Flutter now uses `GpmApiService` as the neutral application data service.
- `Bitrix24Service` remains only as a deprecated compatibility alias.
- New external orders use `source: external`.
- Legacy `source: crm` orders are still accepted and normalized.
- The app orders API can use PostgreSQL through `GPM_APP_DATABASE_URL`.
- Human app users authenticate through `/app-api/auth/login` and read orders
  through `/app-api/me/orders`.
- Production currently has three separate server-assigned transition accounts
  (`client`, `worker`, `logist`); the former shared `admin/admin` is disabled.
- Accounts, sessions, audit events and one-time invitations are stored in
  PostgreSQL.
- Profiles, dashboards and chats are server-backed. Applications and
  assignments persist inside the order document; worker finance is derived from
  completed orders and is not a payment ledger.
- SQLite remains a local development fallback only.

## Production Requirements

- Host PostgreSQL and personal data inside the Russian Federation.
- Keep secrets in server environment variables, not in Git, mobile builds, web
  assets, logs, or GitHub Pages workflow fallbacks.
- Rotate any tokens that were ever committed or embedded into public web builds.
- Keep the server-side integration token separate from human user sessions.
- Store only the minimum personal data needed for each role and workflow.
- Keep audit logs for access and changes to orders, profiles, assignments, and
  payout details.
- Define data retention and deletion rules for personal data.
- Serve production over HTTPS only.
- Restrict CORS with `GPM_APP_ALLOWED_ORIGINS`.

## Required Environment

```bash
GPM_APP_ENV=production
GPM_APP_DATABASE_URL=postgresql://user:password@host:5432/database
GPM_APP_API_TOKEN=<server-side integration token>
GPM_APP_JWT_SECRET=<server-side JWT signing secret>
GPM_APP_CLIENT_USERNAME=client
GPM_APP_CLIENT_PASSWORD=<temporary client password>
GPM_APP_WORKER_USERNAME=worker
GPM_APP_WORKER_PASSWORD=<temporary worker password>
GPM_APP_LOGIST_USERNAME=logist
GPM_APP_LOGIST_PASSWORD=<temporary logist password>
GPM_APP_ALLOWED_ORIGINS=https://app.gpmbot.ru,http://localhost:8090,http://127.0.0.1:8090
```

Frontend production builds should use only public app settings:

```bash
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Do not put `GPM_APP_API_TOKEN`, `GPM_APP_JWT_SECRET`, or user passwords into
Flutter web assets.

## Local Secrets

Tracked `app/config.yml` contains safe placeholders only. For local development,
create ignored `app/config.local.yml` with real values, or export environment
variables before starting the bot/API.

Credentials that existed in tracked config must be considered exposed. Use
`SECRET_ROTATION.md` as the rotation list.

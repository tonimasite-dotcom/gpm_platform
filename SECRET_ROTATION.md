# Secret Rotation Checklist

Real credentials were previously present in tracked configuration and/or public
web build configuration. Treat them as exposed and rotate them before production.

Do not paste replacement secrets into chat, Git, docs, screenshots, or web
assets. Put them into server environment variables or an ignored
`app/config.local.yml` only where local development needs them.

## Rotate Now

- Telegram bot tokens:
  - `API_TOKEN`
  - any commented historical `API_TOKEN` values
- PostgreSQL credentials:
  - `DB_USER`
  - `DB_PASS`
  - database user password for `operator_db`/future `gpm_platform`
- Yandex Disk/OAuth credentials:
  - `YANDEX_TOKEN`
  - `CLIENT_ID`
  - `CLIENT_SECRET`
- Geocoder API keys:
  - all historical `GEOCODER_API` values
- Gosuslugi automation credentials:
  - `GOSUSLUGI_LOGIN`
  - `GOSUSLUGI_PASSWORD`
  - proxy credentials inside `GOSUSLUGI_HTTP_PROXY`
- CapMonster:
  - `CAPMONSTER_API_KEY`
- YouDo integration:
  - `YOUDO_ISS`
  - `YOUDO_KID`
  - `YOUDO_CID`
  - private key referenced by `YOUDO_PRIVATE_KEY_PATH`
- External Workstaff/test CRM integration:
  - `CRM_API_KEY`
  - `GPM_APP_API_TOKEN`
- Supabase demo values previously embedded into demo web builds:
  - review project access and RLS policies
  - rotate if the key has more access than a publishable anon key should have

## After Rotation

- Put production values into environment variables on the server.
- Use `app/config.local.yml` only for local development; it is ignored by Git.
- Set `GPM_APP_ALLOWED_ORIGINS` to the real frontend domains only.
- Remove public fallback tokens from all CI workflows.
- Review GitHub Actions secrets and replace any old values.
- Review hosting logs for accidental credential output.
- Keep a dated record of who rotated each credential and where it was updated.

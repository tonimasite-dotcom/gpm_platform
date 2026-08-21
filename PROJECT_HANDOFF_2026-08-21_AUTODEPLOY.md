# GPM Project Handoff: mobile auth, address suggestions and production CI/CD

Snapshot date: 2026-08-21 (Europe/Moscow)

This document is the authoritative continuation snapshot after the first
successful automated production deployment. Read it together with
`CONTINUE_PROJECT_PROMPT_2026-08-21.md` and the older infrastructure history in
`PROJECT_HANDOFF_2026-08-18_PROD_SWITCH.md`.

## 1. Current outcome

The GPM Flutter web application and FastAPI backend are online:

- application: https://app.gpmbot.ru
- API: https://app-api.gpmbot.ru
- API health: https://app-api.gpmbot.ru/health
- GitHub repository: https://github.com/tonimasite-dotcom/gpm_platform
- stable branch: `main`
- production deployment workflow: `.github/workflows/deploy-production.yml`

Production base before this handoff document was commit `e595d15`:

```text
e595d15 Add manual production deployment workflow
1993464 Allow manual address fallback
e1e222c Add secure DaData address suggestions
68de462 Polish mobile authentication experience
9e78bb7 Refine role selection copy and logo
c1f8f15 Split role selection from authentication
54e1da8 Add role selection to app login
30dea56 Add production switch handoff snapshot
```

The first GitHub Actions production run succeeded:

- workflow: `Deploy production`
- run: `#1`
- run ID: `32490148967`
- target: `all`
- commit deployed: `e595d15`
- result: success
- duration shown by GitHub: 1 minute 28 seconds
- URL: https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/32490148967

All job steps succeeded: checkout, Flutter setup, public config generation,
analysis/build, verified SSH setup, backend deployment, frontend upload and
atomic frontend switch.

### Product and workflow decisions captured from this chat

- Role selection must be a separate first step, before login/registration.
- The heading is `Выберите роль`, without the removed explanatory subtitle.
- Role labels are `Клиент`, `Исполнитель`, `Логист`, without `Я`.
- Each role card keeps its explanatory text so users understand the difference.
- The logo is centered in a deliberately mobile-styled header; the role and
  authentication screens share the polished mobile visual language.
- After selecting a role, the user sees `Вход / Регистрация` for that role.
- For the test stage all three roles intentionally share one login.
- Address completion should happen while typing, but the provider decision is
  still open after the user asked whether it should be Yandex.
- Production deployment should be picked up automatically from GitHub tooling,
  without manually moving build archives through MobaXterm.
- Production publishing remains an explicit button click for now rather than an
  automatic deploy on every push to `main`.

Earlier screenshots in the chat were design references; the resulting UI is
captured in `lib/screens/auth/login_screen.dart`. The relevant operational state
and decisions are recorded here so the screenshots are not required to resume.

## 2. Repository and local development

Local checkout at the time of this snapshot:

```text
C:\Users\Юра\Desktop\gpm_platform\gpm_platform
```

Remote:

```text
origin https://github.com/tonimasite-dotcom/gpm_platform.git
```

Flutter version used by production CI:

```text
3.38.5 stable
```

Important files:

- `.github/workflows/deploy-production.yml` — manual production CI/CD.
- `.github/workflows/deploy-demo.yml` — separate GitHub Pages demo; do not
  confuse it with production.
- `PRODUCTION_DEPLOYMENT.md` — short production workflow instructions.
- `app/app_orders_api.py` — FastAPI app, role authentication, orders and
  protected address suggestion proxy.
- `app/config.yml` and `app/config.example.yml` — safe placeholders only.
- `lib/screens/auth/login_screen.dart` — two-step mobile role/authentication UI.
- `lib/screens/client/client_create_order_screen.dart` — client order form and
  address suggestion UI with manual fallback.
- `lib/services/gpm_api_service.dart` — frontend calls to the GPM API.
- `PROJECT_HANDOFF_2026-08-18_PROD_SWITCH.md` — earlier detailed production
  infrastructure handoff.

Never commit `.env`, private keys, production passwords, tokens or populated
server configuration. `.gitignore` already excludes common secret files.

## 3. Production infrastructure

### Frontend

```text
Domain: https://app.gpmbot.ru
Server IP: 186.246.10.163
SSH user currently used by deployment: root
Web root: /var/www/gpm-app
Backup root: /opt/gpm/front-backups
Server name seen in the terminal: gpm-app-prod
```

Public frontend config must contain only:

```text
GPM_APP_MODE=api
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

### Backend

```text
Domain: https://app-api.gpmbot.ru
Server IP: 46.149.71.147
SSH user currently used by deployment: root
Repository: /opt/gpm/gpm_platform
Service: gpm-app-api.service
Environment file: /root/gpm-app-env
Login reference file: /root/gpm-app-login.txt
Backup root: /opt/gpm/backups
Server name seen in the terminal: msk-1-vm-smqt
Storage: PostgreSQL
```

Expected health response:

```json
{"status":"ok","storage":"postgres"}
```

DNS and TLS were already configured before this snapshot. Nginx serves the
frontend and proxies the API. Do not repeat the production switch procedure
unless diagnosing infrastructure.

## 4. Authentication and current UX

Authentication is a two-step mobile flow:

1. The user sees the centered GPM logo and `Выберите роль`.
2. Available roles are `Клиент`, `Исполнитель`, `Логист`, each with a short
   explanation.
3. Selecting a role opens its `Вход / Регистрация` screen.
4. `Изменить роль` returns to role selection.

API role values are:

```text
client
worker
logist
```

Temporary test credentials are intentionally the same for all roles:

```text
admin / admin
```

They are temporary and must be replaced before real customer use. Production
credential configuration is held in `/root/gpm-app-env` using
`GPM_APP_USERNAME` and `GPM_APP_PASSWORD`. Do not copy real credential values
into Git or future chat messages.

Self-service registration is not implemented yet. The registration tab shows a
notice telling testers to use the temporary login.

Verified API login behavior before the CI/CD work:

```text
client LOGIN_OK
worker LOGIN_OK
logist LOGIN_OK
```

## 5. Address autocomplete status

The frontend previously called the public OpenStreetMap Nominatim endpoint
directly. That approach was removed. Current code uses a protected backend
endpoint:

```text
POST /app-api/me/address-suggestions
Authorization: Bearer <app token>
```

Backend implementation currently targets DaData and reads only:

```text
DADATA_API_KEY
```

Features already implemented:

- API key stays on the backend and is never embedded in Flutter assets.
- Queries require authenticated GPM users.
- Response is normalized to title/details/street/house/coordinates/completeness.
- Results are cached for five minutes, with a bounded cache.
- The client debounces requests.
- Complete suggestions preserve coordinates.
- Incomplete suggestions ask the user to add a house number.
- When the provider/key is unavailable, the UI allows manual address entry and
  shows `Подсказки временно недоступны. Введите адрес вручную.`

Current production state:

- `DADATA_API_KEY` was not configured.
- `app/config.yml` and `app/config.example.yml` contain only `change-me`.
- Automatic suggestions are therefore disabled.
- Manual address entry works and production is not blocked.

Important product decision still open: the user paused and asked whether this
should instead work through Yandex. Do not silently activate DaData. Confirm the
provider with the user first:

- keep DaData/free-tier integration and add its backend key; or
- replace it with the selected Yandex address/geocoding API and its terms/key.

If DaData is confirmed, place the real value only in `/root/gpm-app-env`, restart
`gpm-app-api.service`, and verify the authenticated suggestions endpoint. Never
put the key in `.env` used by Flutter or in tracked YAML.

## 6. Production deployment automation

Future production deployments no longer require a locally built ZIP or
MobaXterm. Use:

```text
GitHub -> Actions -> Deploy production -> Run workflow
Branch: main
Component to deploy: all | backend | frontend
```

Direct workflow URL:

https://github.com/tonimasite-dotcom/gpm_platform/actions/workflows/deploy-production.yml

The `production` GitHub Environment exists and is restricted to branch `main`.
It contains these environment secrets:

```text
PROD_SSH_PRIVATE_KEY
PROD_SSH_KNOWN_HOSTS
```

Do not reveal or replace their values unless deliberately rotating deployment
access.

Deployment key facts safe to retain for verification:

```text
Deploy key fingerprint: SHA256:ihX7IWxBo32in5dSZkkap3eDAN6MtOuZaknoUkxv+hk
Backend host fingerprint: SHA256:dAcCgb8rkH+GkWoW+92d7xR8QEwVVyASs2OrdHbBDHc
Frontend host fingerprint: SHA256:JxM4B2DANmDA6fMWKaxH8aVg1Jsj33a8yFowi2z5xFQ
```

The public deploy key was added to `/root/.ssh/authorized_keys` on both servers
with the OpenSSH `restrict` option. SSH access was tested successfully against
the pinned host keys:

```text
BACKEND_SSH_OK
FRONTEND_SSH_OK
```

A local copy of the deploy key pair was generated outside the repository:

```text
C:\tmp\gpm-production-github-actions
C:\tmp\gpm-production-github-actions.pub
```

The private file is sensitive. It is not needed for routine deployment after
the GitHub secret has been verified. Move it to an approved secure credential
store or delete the exact local pair after the owner confirms no offline backup
is required. Never upload it to Git or paste it into chat.

### Workflow behavior

For target `all`, the workflow:

1. checks out `main`;
2. generates the public production `.env`;
3. runs `flutter pub get`, `flutter analyze --no-pub` and release web build;
4. configures SSH using the two environment secrets and pinned host keys;
5. refuses backend deployment when tracked local server changes exist;
6. creates a Git bundle and records the old backend commit;
7. fast-forwards the backend, compiles Python, restarts systemd and checks the
   public health endpoint;
8. transfers the web artifact, validates required files and public config;
9. backs up and atomically switches `/var/www/gpm-app`;
10. verifies nginx and public frontend URLs;
11. automatically restores the previous frontend if verification fails.

Only one production deployment can run at a time. It is manual
(`workflow_dispatch`); pushing to `main` does not automatically deploy
production. The older `Deploy demo` workflow still runs independently for
GitHub Pages.

## 7. Last verified backups

Manual address-update deployment:

```text
Backend: /opt/gpm/backups/20260821_131659
Frontend: /opt/gpm/front-backups/20260821_133633
Previous frontend: /var/www/gpm-app-previous-20260821_133633
```

First automated deployment:

```text
Backend: /opt/gpm/backups/20260821_140522
Frontend: /opt/gpm/front-backups/20260821_140532
Previous frontend: /var/www/gpm-app-previous-20260821_140532
```

Manual build archives from earlier iterations may still exist in `/root` on the
frontend server and under `C:\tmp` locally. They are no longer part of the normal
deployment process. Do not delete them recursively without resolving exact
paths and confirming with the owner.

## 8. Tests completed

For address suggestion changes:

- `python -m py_compile app/app_orders_api.py` passed.
- Backend normalization was tested with a mocked provider response.
- `flutter analyze` passed with no issues.
- `flutter build web --release` passed.
- The Linux-compatible web archive was validated and manually deployed once.

For production automation:

- YAML parsed successfully.
- deploy key authentication passed against both pinned hosts.
- full GitHub Actions production run `32490148967` passed.
- backend finished at `e595d15` and health returned OK.
- nginx configuration tests passed before and after the frontend switch.
- frontend and public `.env` checks passed.

## 9. Known issues and recommended next work

1. Decide whether address suggestions should use DaData or Yandex, then enable
   and test the chosen provider.
2. Replace temporary shared `admin/admin` authentication with real user
   registration, password storage and role-aware accounts before public use.
3. The workflow currently uses `actions/checkout@v4`. GitHub emitted a harmless
   Node.js 20 deprecation warning while forcing Node.js 24. Verify the current
   official checkout release and update separately.
4. During backend startup retries, an early empty health response can produce a
   noisy Python JSON traceback in the Actions log. The retry subsequently
   succeeds; improve the check to parse JSON only after curl succeeds.
5. Consider replacing broad root SSH execution with a dedicated deployment user
   and narrowly scoped server-side commands as a later hardening task.
6. Decide whether to delete the local deploy private key pair after placing an
   approved backup in a credential manager.
7. Implement real registration; current registration screen is informational.
8. Continue end-to-end role testing and the client order creation flow after the
   address provider decision.

## 10. Safe operating rules for the next chat

- Communicate in Russian and give the user one clear operation at a time.
- Prefer GitHub Actions for production; do not return to manual ZIP deployment
  unless Actions is unavailable and the user explicitly agrees.
- Do not request, print, commit or echo passwords, API keys, access tokens,
  private keys or populated environment files.
- Treat existing local/server changes and backups as user data.
- Before editing, inspect `git status`, current branch and `origin/main`.
- Work on a feature branch for new GitHub changes; stage only named files.
- Run tests proportional to each change before publishing.
- Production workflow is manual; never trigger it unless the user asks to
  publish/deploy the change.
- If an Actions run fails, inspect the exact failed step and logs before asking
  the user to use MobaXterm.

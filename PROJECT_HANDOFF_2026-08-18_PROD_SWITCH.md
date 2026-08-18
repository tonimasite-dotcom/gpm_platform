# GPM Project Handoff: Production Switch

Date: 2026-08-18
Language/context: user works in Russian. Continue step-by-step, with concrete
commands for PowerShell or MobaXterm depending on where the command should run.

## Where We Stopped

The user said "Стоп" immediately after the production frontend started showing
the login screen at:

```text
https://app.gpmbot.ru
```

Do not continue actions automatically in the old chat. In a new chat, continue
from the first login/check step.

Current visible state:

- Frontend opens and shows the login screen.
- User has not yet logged in.
- Backend login endpoint was tested from the server and returned `LOGIN_OK`.
- Backend order list returned `ORDERS_COUNT 0`.
- Expected after login: no demo orders; empty real order list.

## Key Decision

Orders for the app are not sourced from Bitrix24.

Target flow:

```text
Self-written external order system -> GPM backend -> PostgreSQL -> Flutter app
```

Bitrix24 may remain only for incoming service/sales/support requests. It is not
the source of truth for app orders, workers, assignments, chats, or payouts.

## Domains And Servers

Frontend:

```text
Domain: https://app.gpmbot.ru
Server name in Timeweb: gpm-app-prod / Frontend app
IP: 186.246.10.163
OS: Ubuntu 26.04 LTS
Web root: /var/www/gpm-app
Nginx site: /etc/nginx/sites-available/gpm-app
Current archive on server: /root/gpm-platform-web-api.zip
Backups: /opt/gpm/front-backups/
```

Backend:

```text
Domain: https://app-api.gpmbot.ru
Server name in Timeweb: Platform
IP: 46.149.71.147
Hostname seen in shell: msk-1-vm-smqt
OS: Ubuntu 24.04.3 LTS
Repo path: /opt/gpm/gpm_platform
Service: gpm-app-api.service
Uvicorn bind: 127.0.0.1:8081
Nginx proxy: /etc/nginx/sites-available/app-api.gpmbot.ru
Backend env file: /root/gpm-app-env
Login credential file: /root/gpm-app-login.txt
Backups: /opt/gpm/backups/
```

DNS in Timeweb:

```text
app.gpmbot.ru     A 186.246.10.163
app-api.gpmbot.ru A 46.149.71.147
```

SSL:

- `app.gpmbot.ru` certificate issued by Certbot and deployed to nginx.
- `app-api.gpmbot.ru` certificate already existed and works.

## Secret Handling

Do not paste secrets into chat.

Secrets live on backend server:

```text
/root/gpm-app-env
/root/gpm-app-login.txt
```

Important:

- `GPM_APP_API_TOKEN` is a server-side integration token only. It is for the
  self-written external order system to publish orders.
- `GPM_APP_API_TOKEN` must not be embedded into Flutter web assets.
- Human app users log in through `/app-api/auth/login` and then use a bearer
  token for `/app-api/me/orders`.
- The frontend production `.env` contains only public values:

```text
GPM_APP_MODE=api
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

## Git State

Local workspace:

```text
C:\Users\Юра\Desktop\gpm_platform\gpm_platform
```

Local git status was clean when this handoff was created.

Recent commits:

```text
d541d4b Add app auth and API-mode order access
0a1fe04 Prepare production app API configuration
4c06a5a Pin Flutter version for Pages deploy
c031a45 Retry demo deploy
7f8d272 Improve client worker profiles and chats
```

Both key commits were pushed to:

```text
origin/main -> https://github.com/tonimasite-dotcom/gpm_platform.git
```

## Code Changes Already Made

Commit `0a1fe04 Prepare production app API configuration`:

- Replaced hardcoded/unsafe app config with placeholders.
- Added env-first config handling.
- Added PostgreSQL support for `app/app_orders_api.py`.
- Kept SQLite only as local fallback.
- Renamed app data service from Bitrix-specific naming to `GpmApiService`.
- Kept `Bitrix24Service` only as a compatibility alias.
- Changed app order source from `crm` to `external`, while still accepting
  legacy `crm`.
- Added production/security docs:
  - `PRODUCTION_READINESS.md`
  - `SECRET_ROTATION.md`
- Added `requirements-api.txt` with API runtime dependencies.

Commit `d541d4b Add app auth and API-mode order access`:

- Backend:
  - Added `/app-api/auth/login`.
  - Added `/app-api/me`.
  - Added `/app-api/me/orders` GET and POST for logged-in app users.
  - Added `/app-api/me/orders/{order_id}` PATCH for logged-in app users.
  - Kept `/app-api/orders` GET/POST/PATCH protected by `X-GPM-App-Token` for
    the external integration.
  - Added standard-library HS256 JWT handling, no extra backend dependency.
  - Added `PATCH` to CORS allowed methods.
- Frontend:
  - Added production login screen in `lib/screens/auth/login_screen.dart`.
  - App shows login screen only when `GPM_APP_MODE=api` and backend is set.
  - Access token is stored in browser localStorage via demo storage helpers.
  - Added logout button in the header for API mode.
  - In API mode, bundled demo orders are cleared and not mixed into the list.
  - API mode reads from `/app-api/me/orders`.
  - API mode creates/patches through `/app-api/me/orders`.
- Config/docs:
  - Added placeholder env keys:
    - `GPM_APP_JWT_SECRET`
    - `GPM_APP_LOGIST_USERNAME`
    - `GPM_APP_LOGIST_PASSWORD`
  - Documented that frontend builds must not contain server secrets.

## Validation Already Done

Local validation:

```text
python -m py_compile app/app_orders_api.py -> OK
backend smoke-test with FastAPI TestClient -> OK
flutter analyze --no-pub -> No issues found
```

`dart format` on the Windows machine timed out/hung, same as before. The analyzer
still passed. Do not assume formatting succeeded.

Backend server validation:

```text
curl https://app-api.gpmbot.ru/health -> {"status":"ok","storage":"postgres"}
Login test -> LOGIN_OK
/app-api/me/orders -> ORDERS_COUNT 0, []
```

Frontend deployment validation:

```text
curl -I https://app.gpmbot.ru/ -> HTTP/1.1 200 OK
curl -s https://app.gpmbot.ru/assets/.env ->
GPM_APP_MODE=api
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

User confirmed:

```text
Есть экран!
```

Meaning: production login screen is visible.

## Important Command History

Backend code update:

```bash
cd /opt/gpm/gpm_platform

mkdir -p /opt/gpm/backups/$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=$(ls -td /opt/gpm/backups/* | head -n 1)

cp app/app_orders_api.py "$BACKUP_DIR/app_orders_api.py.before_auth"
cp app/config.yml "$BACKUP_DIR/config.yml.before_auth"

git fetch origin
git checkout -- app/app_orders_api.py app/config.yml app/config.example.yml CRM_APP_PUBLICATION.md PRODUCTION_READINESS.md SECRET_ROTATION.md
git pull --ff-only origin main
```

Backend env additions:

```bash
cd /opt/gpm/gpm_platform

if ! grep -q '^GPM_APP_JWT_SECRET=' /root/gpm-app-env; then
  echo "GPM_APP_JWT_SECRET=$(openssl rand -hex 32)" >> /root/gpm-app-env
fi

if ! grep -q '^GPM_APP_LOGIST_USERNAME=' /root/gpm-app-env; then
  echo "GPM_APP_LOGIST_USERNAME=logist" >> /root/gpm-app-env
fi

if ! grep -q '^GPM_APP_LOGIST_PASSWORD=' /root/gpm-app-env; then
  LOGIST_PASSWORD=$(openssl rand -base64 18 | tr -d '\n')
  echo "GPM_APP_LOGIST_PASSWORD=$LOGIST_PASSWORD" >> /root/gpm-app-env
  {
    echo "GPM app login"
    echo "URL: https://app.gpmbot.ru"
    echo "Username: logist"
    echo "Password: $LOGIST_PASSWORD"
  } > /root/gpm-app-login.txt
fi

chmod 600 /root/gpm-app-env /root/gpm-app-login.txt
systemctl restart gpm-app-api.service
```

Frontend local production build had to use ASCII path because Flutter failed to
write shaders under `C:\Users\Юра\...`:

```powershell
Set-Location "C:\Users\Юра\Desktop\gpm_platform\gpm_platform"

$buildSrc = "C:\tmp\gpm_platform_build_src"
$zipPath = "C:\tmp\gpm-platform-web-api.zip"

if (Test-Path $buildSrc) {
  Remove-Item -LiteralPath $buildSrc -Recurse -Force
}

New-Item -ItemType Directory -Path $buildSrc | Out-Null

robocopy . $buildSrc /MIR /XD .git .dart_tool build .venv __pycache__ /XF app\crm_app_orders.sqlite3 app\gpm_app_orders.sqlite3

Set-Location $buildSrc

Set-Content -Path ".env" -Encoding UTF8 -Value @"
GPM_APP_MODE=api
GPM_APP_API_URL=https://app-api.gpmbot.ru
"@

flutter build web --release --base-href /

if (Test-Path $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path "build\web\*" -DestinationPath $zipPath -Force
Get-Item $zipPath | Select-Object FullName,Length,LastWriteTime
```

Result:

```text
C:\tmp\gpm-platform-web-api.zip
Length: 11305688
LastWriteTime: 18.08.2026 16:57:15
```

Frontend deploy:

```bash
ls -lah /root/gpm-platform-web-api.zip

mkdir -p /opt/gpm/front-backups/$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=$(ls -td /opt/gpm/front-backups/* | head -n 1)

cp -a /var/www/gpm-app "$BACKUP_DIR/gpm-app-before-api"

rm -rf /var/www/gpm-app/*
unzip -o /root/gpm-platform-web-api.zip -d /var/www/gpm-app

find /var/www/gpm-app -type d -exec chmod 755 {} \;
find /var/www/gpm-app -type f -exec chmod 644 {} \;
chown -R www-data:www-data /var/www/gpm-app

nginx -t
systemctl reload nginx

curl -I https://app.gpmbot.ru/
curl -s https://app.gpmbot.ru/assets/.env
```

## Known Gotchas

- Do not paste URLs like `https://skr.sh/...` into bash; those are screenshots,
  not commands.
- MobaXterm SFTP upload must put frontend archives into `/root/`.
- If deploy command is run before upload, `/var/www/gpm-app` can become empty.
  Restore from latest backup:

```bash
BACKUP_DIR=$(ls -td /opt/gpm/front-backups/* | head -n 1)

rm -rf /var/www/gpm-app
cp -a "$BACKUP_DIR/gpm-app-before-api" /var/www/gpm-app

find /var/www/gpm-app -type d -exec chmod 755 {} \;
find /var/www/gpm-app -type f -exec chmod 644 {} \;
chown -R www-data:www-data /var/www/gpm-app

nginx -t
systemctl reload nginx
curl -I https://app.gpmbot.ru/
```

- Frontend asset directories previously unpacked with missing execute
  permissions. Always run the `find ... chmod 755/644` commands after unzip.
- Local `dart format` may hang. Use `flutter analyze --no-pub` as the immediate
  safety check if this repeats.
- Public internet scanners are hitting the backend. 404 noise in uvicorn logs
  like phpunit/thinkphp paths was observed. Not caused by the app.

## Next Steps In New Chat

1. Ask user to log in at `https://app.gpmbot.ru`.
2. Tell them to retrieve the password only on backend server:

```bash
cat /root/gpm-app-login.txt
```

Do not ask them to paste the password into chat.

3. After login, verify:

- No demo orders.
- Empty list, because PostgreSQL currently has zero orders.

4. Create one test order from the frontend with the `Создать` button.
5. Verify it landed in PostgreSQL from backend:

```bash
set -a
. /root/gpm-app-env
set +a

APP_ACCESS_TOKEN=$(curl -s -X POST https://app-api.gpmbot.ru/app-api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$GPM_APP_LOGIST_USERNAME\",\"password\":\"$GPM_APP_LOGIST_PASSWORD\"}" \
  | python3 -c 'import sys,json; data=json.load(sys.stdin); print(data.get("access_token",""))')

curl -s https://app-api.gpmbot.ru/app-api/me/orders \
  -H "Authorization: Bearer $APP_ACCESS_TOKEN" \
  | python3 -c 'import sys,json; data=json.load(sys.stdin); print("ORDERS_COUNT", len(data.get("orders", []))); print(json.dumps(data.get("orders", [])[:3], ensure_ascii=False, indent=2))'
```

6. Then test external system publication through `POST /app-api/orders` with
   `X-GPM-App-Token`, preferably from the self-written test system, not by
   pasting the token into chat.
7. After successful test, decide production user/auth roadmap:
   - more logist users;
   - worker/client auth;
   - roles in DB instead of single env user;
   - audit logs and personal-data retention policy.

## Prompt For The New Chat

Copy/paste this into a new Codex chat:

```text
Продолжаем проект GPM Platform с места остановки.

Я работаю по-русски. Веди меня пошагово: явно говори, где выполнять команду
(PowerShell на Windows, MobaXterm на backend app-api.gpmbot.ru или MobaXterm на
frontend app.gpmbot.ru). Секреты, пароли и токены в чат не проси и не выводи.

Локальный проект:
C:\Users\Юра\Desktop\gpm_platform\gpm_platform

GitHub:
https://github.com/tonimasite-dotcom/gpm_platform.git
Текущий важный коммит: d541d4b Add app auth and API-mode order access
Перед ним: 0a1fe04 Prepare production app API configuration

Архитектура:
Заявки в приложение идут не из Bitrix24, а из самописной внешней системы.
Bitrix24 может остаться только для входящих обращений по услугам, но не как
источник заказов приложения.

Боевой поток:
Self-written external order system -> GPM backend -> PostgreSQL -> Flutter app

Домены:
Frontend: https://app.gpmbot.ru, сервер 186.246.10.163, web root /var/www/gpm-app
Backend: https://app-api.gpmbot.ru, сервер 46.149.71.147, repo /opt/gpm/gpm_platform

Backend уже:
- работает как systemd service gpm-app-api.service;
- слушает 127.0.0.1:8081 через uvicorn;
- проксируется nginx;
- подключен к PostgreSQL;
- /health возвращает {"status":"ok","storage":"postgres"};
- /app-api/auth/login проверен, LOGIN_OK;
- /app-api/me/orders вернул ORDERS_COUNT 0.

Секреты на backend:
/root/gpm-app-env
/root/gpm-app-login.txt
Не проси вставлять их в чат.

Frontend уже:
- собран в API-режиме;
- загружен на app.gpmbot.ru;
- curl https://app.gpmbot.ru/assets/.env показывает:
  GPM_APP_MODE=api
  GPM_APP_API_URL=https://app-api.gpmbot.ru
- пользователь подтвердил, что экран входа появился.

Где остановились:
Я сказал "Стоп" сразу после появления экрана входа. Я еще не логинился в
приложение.

Следующий шаг:
1. Дай мне команду на backend, чтобы посмотреть логин/пароль из
   /root/gpm-app-login.txt, но пароль в чат не проси.
2. Попроси меня войти на https://app.gpmbot.ru.
3. После входа проверить, что демо-заявок нет и список пустой.
4. Затем создать одну тестовую заявку через кнопку "Создать" и проверить на
   backend, что она попала в PostgreSQL через /app-api/me/orders.

Важные нюансы:
- GPM_APP_API_TOKEN только для внешней самописной системы, не для frontend.
- В frontend нельзя класть GPM_APP_API_TOKEN, GPM_APP_JWT_SECRET или пароли.
- Если нужно пересобирать Flutter web на Windows, путь с "Юра" ломает shader
  compiler. Используй ASCII-копию C:\tmp\gpm_platform_build_src и архив
  C:\tmp\gpm-platform-web-api.zip.
- После unzip на frontend сервере всегда делать chmod директорий 755, файлов 644
  и chown www-data:www-data.
```

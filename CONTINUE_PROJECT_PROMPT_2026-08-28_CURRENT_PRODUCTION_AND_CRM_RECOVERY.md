# Промт для продолжения GPM с текущего production

Скопируйте весь текст ниже в новый чат.

---

Продолжаем проект GPM Platform из репозитория:

```text
https://github.com/tonimasite-dotcom/gpm_platform
```

Работай по-русски, пошагово и только на основании проверяемых фактов. Не проси и
не выводи реальные пароли, hashes, tokens, API keys, database URL, populated env
или SSH private keys. Допустимы только синтетические данные.

## Сначала прочитай полностью

```text
PROJECT_HANDOFF_2026-08-28_CURRENT_PRODUCTION_AND_CRM_RECOVERY.md
CONTINUE_PROJECT_PROMPT_2026-08-28_CURRENT_PRODUCTION_AND_CRM_RECOVERY.md
DESIGN_FREEZE.md
INDEPENDENT_PLATFORM_ARCHITECTURE.md
WORKER_PROFILE_VERIFICATION.md
NEW_DEVICE_SETUP_2026-08-26.md
README.md
CRM_APP_PUBLICATION.md
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
PRODUCTION_DEPLOYMENT.md
SECRET_ROTATION.md
```

Главный источник истины — новый handoff от 28.08.2026. Более старые handoff и
prompt использовать только как историю.

## Выполни только read-only проверку

```text
git status --short --branch
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git rev-parse origin/feature/crm-logist-publication
git log --all --decorate --oneline -12
```

Публично проверь без авторизованных или изменяющих запросов:

```text
https://app.gpmbot.ru/
https://app-api.gpmbot.ru/health
https://app.gpmbot.ru/assets/.env
```

Публичный `.env` должен содержать только:

```text
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

## Ожидаемая опора

Кодовая точка до документационного snapshot commit:

```text
main = origin/main = 597a9d298f9d11814fe2d7e62f79fba70ef25994
production frontend = 597a9d298f9d11814fe2d7e62f79fba70ef25994
production backend = 597a9d298f9d11814fe2d7e62f79fba70ef25994
origin/feature/crm-logist-publication = e117e699c414cd3c5cb5cf3c30ef6371a23accf7
```

Документационный snapshot commit будет новее `597a9d2` и не требует production
deploy. Проверь фактические SHA и не считай несовпадение с этой строкой ошибкой,
если изменились только документы.

Production ожидается:

```text
frontend HTTP 200
health {"status":"ok","storage":"postgres"}
backend service active
```

## Что уже завершено

- DB-backed accounts/sessions/audit и invite registration;
- server-backed role workspaces, profiles, chats, applications/assignments;
- восстановленный утверждённый дизайн кабинета исполнителя;
- редактирование данных профиля исполнителя;
- выбор ремней и инструментов `Да/Нет`;
- паспортная заявка с фото на модерацию;
- заявка НПД/ИНН на модерацию;
- очередь логиста, approve/reject и причина отказа;
- приватное файловое хранилище и таблица verification;
- Email удалён только из профиля исполнителя;
- production deploy `33156246217` успешен;
- владелец вручную подтвердил, что всё работает.

Не повторяй эти миграции и deploy runs.

## Неподвижные решения

- GPM полностью самостоятельна.
- CRM только передаёт заявки server-to-server.
- Telegram, мессенджеры и соцсети не участвуют.
- Backend/PostgreSQL — источник истины ролей и данных.
- В production нельзя выбирать роль без входа.
- Действует `DESIGN_FREEZE.md`; цвета и компоновку не менять.
- Только синтетические данные до закрытия P0.

## Незавершённая CRM-линия

CRM feature находится отдельно:

```text
origin/feature/crm-logist-publication = e117e69
functional commit = 30b2bca
```

Она разошлась с текущим `main`, не слита и не развернута. Не deploy её как есть.

Полные исторические документы доступны без переключения ветки:

```text
git show origin/feature/crm-logist-publication:PROJECT_HANDOFF_2026-08-28_CRM_PUBLICATION_RECOVERY.md
git show origin/feature/crm-logist-publication:CONTINUE_PROJECT_PROMPT_2026-08-28_CRM_PUBLICATION_RECOVERY.md
git show origin/feature/crm-logist-publication:PROJECT_HANDOFF_2026-08-28_CRM_TOKEN_MISMATCH_DELTA.md
```

Workstaff test:

```text
https://ts.workstaffcrm.ru
server: 5.183.191.222
app root: /var/www/gruzpiter/data/www/ts.workstaffcrm.ru
```

Поток:

```text
Workstaff -> POST https://app-api.gpmbot.ru/app-api/orders
          -> X-Gpm-App-Token
          -> GPM PostgreSQL -> NEW у логиста -> PROCESSED у worker
```

Исторически запросы работали; последний доказанный `200 OK` был
18.08.2026. Последняя синтетическая публикация дошла до GPM и получила
`401 Unauthorized`.

Без вывода token доказано:

```text
Workstaff token: length 64, fingerprint c3b10d89a775
GPM token:       length 64, fingerprint bcc12c793afd
```

Причина `401`: server-side tokens не совпадают. URL, endpoint, publisher и кнопка
существуют. Payload пока не диагностировать: запрос отклоняется раньше.

## Рекомендуемый следующий шаг

Сначала сообщи владельцу результаты read-only проверки и остановись. Если он
явно подтверждает продолжение CRM recovery, проведи совместную безопасную
ротацию нового случайного `GPM_APP_API_TOKEN` на Workstaff и GPM:

1. новый token генерируется локально и остаётся только в clipboard;
2. на обоих серверах до изменения создаются timestamped env backups;
3. значение вводится скрыто и никогда не печатается;
4. Workstaff очищает Laravel config cache;
5. GPM API перезапускается и проходит active/health;
6. сравниваются только length и короткие SHA-256 fingerprints;
7. синтетическая заявка должна дать `200 OK`;
8. затем проверяется появление `NEW` у логиста.

Rollback выполняется только парой обоих env backups. Не менять один конец без
второго.

После доказанного `200` создать новую feature-ветку от актуального `main`,
перенести `30b2bca`, разрешить конфликты, прогнать backend tests, Flutter analyze,
Flutter tests, release web build и GitHub CI. Production deploy предлагать только
после отдельного подтверждения владельца.

## Production и backups

```text
backend host: 46.149.71.147
service: gpm-app-api.service
repo: /opt/gpm/gpm_platform
env: /root/gpm-app-env
private verification dir: /root/gpm-private-worker-verifications
```

Существуют проверенные backups worker verification release:

```text
/root/gpm-app-env.before-worker-verification-20260828T074609Z
/root/gpm-private-backups/20260828-worker-verifications-predeploy-659f3d1/gpm.dump
```

Не удаляй их. Перед любым schema/data change создай и проверь отдельный новый
PostgreSQL dump. `Deploy production` сам DB dump не создаёт.

## DaData и Яндекс

DaData активна в production. Яндекс был подготовлен, но выключен в исторической
локальной ветке `feature/address-provider-switch`, которой нет на origin и в
текущем клоне. Не включай Яндекс и не смешивай эту задачу с CRM.

## P0

Проект остаётся только закрытым тестом на синтетических данных. Не загружай
реальные паспорта, ИНН, телефоны, адреса, банковские данные или переписку.

Открыты: оператор ПДн, документы/согласия, уведомление РКН, локализация всех
хранилищ, поручения обработки, contact verification/recovery, права субъекта,
retention/deletion, secret rotation, restore drill/PITR, полный E2E isolation,
официальная проверка НПД и повторная юридическая оценка до реальных сделок.

## Обязательные правила

- Не выводи populated env и реальные секреты.
- Не восстанавливай исторический token из Git.
- Не добавляй secrets в Flutter assets/browser/Git.
- Не возвращай Email в профиль исполнителя.
- Не возвращай demo role switcher в production.
- Не меняй дизайн и цвета.
- Не включай legacy Telegram bot.
- Не повторяй завершённые миграции/deploy.
- Не трогай несвязанные пользовательские изменения.
- Любую работу делай в новой feature-ветке от актуального `origin/main`.
- Перед commit запускай `git diff --check`, backend tests, Flutter analyze/tests.
- После push жди зелёный CI.
- Production меняй только по явному запросу владельца.

## Первый ответ владельцу

После read-only проверки сообщи кратко:

1. текущую ветку, HEAD, `origin/main` и чистоту working tree;
2. production SHA, frontend HTTP и health;
3. что worker moderation и удаление Email уже опубликованы;
4. что CRM token mismatch остаётся открытым;
5. что `30b2bca` отсутствует в `main`;
6. рекомендуемое следующее действие — совместная безопасная token rotation.

Затем дождись решения владельца и не начинай изменения автоматически.

---

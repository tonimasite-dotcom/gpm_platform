# Промт для продолжения восстановления Workstaff CRM → GPM

Скопируйте весь текст ниже в новый чат.

---

Продолжаем GPM Platform из репозитория:

```text
https://github.com/tonimasite-dotcom/gpm_platform
```

Работай по-русски, веди пошагово и опирайся на доказательства. Не проси и не
выводи пароли, API keys, token values, hashes, database URL или SSH private keys.
Разрешены только синтетические тестовые данные.

## Главная задача

Восстановить ранее работавший server-to-server поток публикации заявок из
тестовой Workstaff CRM:

```text
https://ts.workstaffcrm.ru
        |
        | POST https://app-api.gpmbot.ru/app-api/orders
        | X-Gpm-App-Token: server-side secret
        v
GPM backend -> PostgreSQL -> логист GPM -> публикация -> исполнители GPM
```

Не проектируй интеграцию заново. Найдена историческая реализация и доказано, что
она работала до 18.08.2026.

## Сначала прочитай полностью

В таком порядке:

```text
PROJECT_HANDOFF_2026-08-28_CRM_PUBLICATION_RECOVERY.md
CONTINUE_PROJECT_PROMPT_2026-08-28_CRM_PUBLICATION_RECOVERY.md
DESIGN_FREEZE.md
INDEPENDENT_PLATFORM_ARCHITECTURE.md
CRM_APP_PUBLICATION.md
ADDRESS_PROVIDER_DECISION.md
README.md
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
PRODUCTION_DEPLOYMENT.md
SECRET_ROTATION.md
```

Старые handoff/prompt используй только для истории. Главный источник истины —
handoff от 28.08.2026.

## Сразу проверь Git read-only

```text
git status --short --branch
git branch -vv
git rev-parse HEAD
git rev-parse origin/main
git log --all --decorate --oneline -12
```

Ожидаемая опора до snapshot-коммита:

```text
main = origin/main = 92624b7
feature/crm-logist-publication = 30b2bca
feature/address-provider-switch = f06e540 (локальная, не опубликована)
```

Документационный snapshot-коммит будет потомком `30b2bca`. Сообщи фактические
SHA после проверки и не переключай ветки без необходимости.

## Production-опора

```text
frontend SHA: b9ebdfa
backend SHA: a6fac5c
frontend: https://app.gpmbot.ru/
health: https://app-api.gpmbot.ru/health
backend host: 46.149.71.147
backend hostname: msk-1-vm-smqt
service: gpm-app-api.service
repository: /opt/gpm/gpm_platform
env: /root/gpm-app-env
database: PostgreSQL
```

На 28.08.2026 frontend отвечал HTTP 200, health возвращал
`{"status":"ok","storage":"postgres"}`, public `.env` содержал только
`GPM_APP_MODE=production` и `GPM_APP_API_URL`.

CRM feature `30b2bca` имеет зелёный GitHub CI `33118388353`, но ещё не слита в
`main` и не развернута.

## Архитектурное правило

GPM полностью самостоятельна. CRM только передаёт данные заявки. Публикация,
статусы, назначения, отклики, внутренние чаты, уведомления и финансы работают в
GPM.

Telegram, другие мессенджеры и соцсети не участвуют. Не включай legacy bot и не
используй `/api/telegram/` как активный транспорт.

## Дизайн

Действует `DESIGN_FREEZE.md`. Дизайн, компоновка и цветовая схема финальные на
текущем этапе. Не меняй палитру, навигацию, карточки, кнопки, поля, типографику и
отступы без отдельного явного решения владельца.

## Что найдено в истории

```text
cfcf847 Add CRM app order publication API
3785502 Integrate CRM order publishing
e77ef62 Scope CRM moderation to publishing logist
54010fb Remove demo CRM import button
0a1fe04 Prepare production app API configuration
d541d4b Add app auth and API-mode order access
```

`54010fb` удалил только демонстрационную кнопку `Из CRM`. Серверный endpoint
остался. `0a1fe04` удалил старый token из публичной Flutter-сборки и назначил
ротацию. Никогда не восстанавливай историческое значение из Git.

## Что уже исправлено в `30b2bca`

- убрана frontend-фильтрация CRM-заявок по старому demo localStorage;
- `NEW` маршрутизируется backend по server-backed телефону профиля логиста;
- `+7` и `8` сопоставляются;
- без `logist_phone` заявка попадает в общую очередь;
- действие называется `Опубликовать`;
- worker не видит `NEW`, но видит `PROCESSED`;
- дизайн и цвета не менялись.

Проверки:

```text
backend tests: 23 passed, 1 PostgreSQL integration skipped locally
Flutter analyze: no issues
Flutter tests: 3 passed
Flutter release web build: success
CI 33118388353: success
```

## Production-журнал

Агрегированный journal показал успешные `POST /app-api/orders` 5, 7, 11, 12 и
18 августа. Последний success:

```text
2026-08-18T10:36:41+00:00 200 OK
```

После него были четыре `401` 25 августа и диагностический `401` 27 августа.
Источник запросов 25 августа пока не доказан.

Public checks уже показали:

- Workstaff URL отвечает 200;
- GPM health отвечает 200;
- unauthenticated POST возвращает 401, а не 503;
- значит integration auth GPM настроен, но token Workstaff может не совпадать.

## Точная точка продолжения

Попроси владельца создать в `https://ts.workstaffcrm.ru/` одну полностью
синтетическую тестовую заявку. Сразу после этого дай одну команду для MobaXterm
на backend `46.149.71.147`:

```bash
journalctl -u gpm-app-api.service --since "5 minutes ago" --no-pager -o short-iso | awk '/POST \/app-api\/orders/ {print $1, $(NF-1), $NF}'
```

Команда не выводит token/payload/ПДн.

Дальше действуй строго по результату.

### Результат `401 Unauthorized`

- Workstaff отправляет старый/неверный token.
- Не запрашивай его значение в чате.
- Определи, где находится закрытая server-side настройка интеграции Workstaff.
- Без вывода значения синхронизируй её с актуальным `GPM_APP_API_TOKEN` из
  `/root/gpm-app-env` либо проведи безопасную совместную ротацию обоих концов.
- Повтори synthetic POST до `200 OK`.

### Пустой результат

- Workstaff не отправляет запрос.
- Найди и восстанови webhook/trigger создания или обновления заявки.
- Target: `POST https://app-api.gpmbot.ru/app-api/orders`.
- Header: `X-Gpm-App-Token` только server-side.
- Не используй Telegram endpoint и не возвращай кнопку `Из CRM`.

### Результат `200 OK`

- Передача работает.
- Проверь появление записи только безопасным агрегатом без ПДн.
- Затем предложи владельцу слить `feature/crm-logist-publication` в `main` и
  развернуть backend/frontend.
- Production deploy делай только после явного подтверждения.
- После deploy проведи E2E: CRM → `NEW` у логиста → `Опубликовать` →
  `PROCESSED` у worker.

## DaData и Яндекс

DaData уже настроена в production через `/root/gpm-app-env`; синтетический адрес
и координаты проверены. Backup env:

```text
/root/gpm-app-env.before-dadata-20260827
```

Яндекс только подготовлен в локальной ветке `feature/address-provider-switch` и
выключен. Не включай его и не смешивай с CRM-задачей.

## Безопасность и P0

- Только синтетические данные.
- Не выводить server env/login file/token/password/hash/private key.
- Не добавлять secrets в Flutter assets или Git.
- Не делать production schema/data change без проверенного DB backup.
- Не удалять backups/logs без retention/legal-hold решения.
- Не считать проект готовым к реальным ПДн: legal/account/recovery/restore P0
  остаются открыты.

## Что сообщить владельцу в начале нового чата

1. Текущую ветку, HEAD, `origin/main`, clean/dirty state.
2. Production frontend/backend SHA и health.
3. Что исторический CRM push найден и когда был последний `200`.
4. Что `30b2bca` исправляет скрытие заказа, но ещё не в production.
5. Одно следующее действие: synthetic order + пяти минутный journal check.

Не начинай широкую переработку и не повторяй уже выполненные коммиты/deploy.

---

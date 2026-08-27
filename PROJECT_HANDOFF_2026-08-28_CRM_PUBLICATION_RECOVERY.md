# GPM: полный handoff по восстановлению публикации заявок из Workstaff CRM

Дата снимка: 28.08.2026. Часовой пояс: Europe/Moscow.

Это главный источник истины для следующего чата. Он продолжает снапшот
`PROJECT_HANDOFF_2026-08-27_WORKER_DESIGN_RELEASE.md` и фиксирует все решения и
изменения после него: DaData, заморозку дизайна, автономную архитектуру GPM и
текущую диагностику Workstaff CRM.

Читайте вместе с:

- `CONTINUE_PROJECT_PROMPT_2026-08-28_CRM_PUBLICATION_RECOVERY.md`;
- `DESIGN_FREEZE.md`;
- `INDEPENDENT_PLATFORM_ARCHITECTURE.md`;
- `CRM_APP_PUBLICATION.md`;
- `ADDRESS_PROVIDER_DECISION.md`;
- `DADATA_ADDRESS_SETUP.md`;
- `YANDEX_ADDRESS_SETUP.md`;
- `NEW_DEVICE_SETUP_2026-08-26.md`;
- `PROJECT_AUDIT_2026-08-25.md`;
- `LEGAL_READINESS_RU.md`;
- `PRODUCTION_DEPLOYMENT.md`;
- `SECRET_ROTATION.md`.

## 1. Точная точка остановки

Активный вопрос — восстановить ранее работавшую передачу заявок из тестовой
Workstaff CRM в самостоятельное приложение GPM:

```text
https://ts.workstaffcrm.ru
        |
        | POST /app-api/orders + X-Gpm-App-Token
        v
https://app-api.gpmbot.ru -> PostgreSQL -> кабинет логиста GPM
```

Последнее действие владельца: на backend выполнен безопасный агрегированный
просмотр журнала `POST /app-api/orders`. Он доказал, что интеграция работала до
18.08.2026, а затем перестала успешно публиковать заявки.

Точная следующая проверка:

1. Создать в `https://ts.workstaffcrm.ru/` полностью синтетическую заявку.
2. Сразу после этого на backend `46.149.71.147` выполнить:

```bash
journalctl -u gpm-app-api.service --since "5 minutes ago" --no-pager -o short-iso | awk '/POST \/app-api\/orders/ {print $1, $(NF-1), $NF}'
```

Интерпретация:

- `401 Unauthorized` — Workstaff отправляет отсутствующий/старый integration
  token; актуальное значение нужно безопасно синхронизировать на стороне CRM;
- пустой результат — webhook/триггер Workstaff не отправляет запрос;
- `200 OK` — CRM-передача работает, проблема остаётся в production UI; исправление
  видимости уже подготовлено в feature-ветке `30b2bca`.

Не восстанавливать старый токен из Git и не возвращать демонстрационную кнопку
`Из CRM`.

## 2. Git и ветки

Основная ветка:

```text
main = origin/main = 92624b7 Add August 27 worker design handoff
```

Текущая рабочая ветка перед этим документационным изменением:

```text
feature/crm-logist-publication
HEAD = origin/feature/crm-logist-publication = 30b2bca
30b2bca Restore CRM order publication by logist
working tree: clean
```

CRM-ветка опубликована в GitHub. CI:

```text
run: 33118388353
head: 30b2bcad747c0b15a28241de3ac1e2b3e8314df5
conclusion: success
```

Отдельная локальная ветка адресных провайдеров:

```text
feature/address-provider-switch
6ac65d0 Integrate Yandex address suggestions
f06e540 Use DaData as current address provider
```

Она не опубликована и не слита в `main`. Не терять её и не смешивать её код с
CRM recovery. Глобальные документационные решения из неё перенесены в текущий
handoff-коммит, чтобы новая точка продолжения была самодостаточной.

После создания этого снапшота новый документационный коммит будет потомком
`30b2bca`. Он не требует production deployment сам по себе.

## 3. Production-состояние

Production SHA не менялись после снапшота 27 августа:

```text
frontend: b9ebdfa Restore worker workspace design
backend:  a6fac5c Add server-backed role workspaces
```

Backend:

```text
Host: 46.149.71.147
Hostname: msk-1-vm-smqt
SSH user: root
Repository: /opt/gpm/gpm_platform
Service: gpm-app-api.service
EnvironmentFile: /root/gpm-app-env
Database: PostgreSQL
```

Frontend:

```text
Host: 186.246.10.163
Web root: /var/www/gpm-app
Server: nginx
URL: https://app.gpmbot.ru/
```

Read-only проверка 28.08.2026:

```text
frontend: HTTP 200
frontend Last-Modified: 27.08.2026 11:09:24 UTC
health: {"status":"ok","storage":"postgres"}
```

Публичный frontend `.env` содержит только:

```text
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

CRM-ветка `30b2bca` ещё не слита в `main` и не развернута. Повторный production
deploy не запускался.

## 4. Неподвижное продуктовое решение

Дизайн и цветовая схема утверждены как финальные на текущем этапе. Действует
`DESIGN_FREEZE.md`.

Нельзя без отдельного явного согласования менять:

- палитру и визуальные токены;
- типографику, отступы и компоновку;
- навигацию, карточки, кнопки и поля;
- визуальную подачу кабинетов клиента, логиста и исполнителя.

Разрешены необходимые функциональные состояния в существующем визуальном языке.
CRM-исправление изменило только логику и текст действия `Одобрить` на более
точный `Опубликовать`; цвета и компоненты не менялись.

## 5. Автономная архитектура GPM

Решение владельца:

```text
GPM — полностью самостоятельное приложение.
```

CRM является только источником данных заявки. Внутри GPM должны находиться:

- модерация и публикация;
- поиск и отклики исполнителей;
- назначения;
- жизненный цикл заказа;
- внутренние чаты;
- уведомления;
- финансовый учёт.

Telegram, другие мессенджеры и социальные сети не являются транспортом или
зависимостью активного workflow. Legacy bot в `main.py` и `app/handlers/**`
остаётся выключенным через `GPM_ENABLE_LEGACY_BOT`. Не включать его.

Активная схема:

```text
Workstaff CRM -- server-to-server token --> FastAPI
Flutter GPM --- bearer session ----------> FastAPI
                                              |
                                              v
                                        PostgreSQL 17
```

Файл решения: `INDEPENDENT_PLATFORM_ARCHITECTURE.md`.

## 6. Найденная история Workstaff CRM

Тестовая CRM упоминается в `CRM_APP_PUBLICATION.md`:

```text
https://ts.workstaffcrm.ru
```

Исторические коммиты:

```text
cfcf847 Add CRM app order publication API
3785502 Integrate CRM order publishing
e77ef62 Scope CRM moderation to publishing logist
54010fb Remove demo CRM import button
0a1fe04 Prepare production app API configuration
d541d4b Add app auth and API-mode order access
```

Что они делали:

- `cfcf847` создал `POST/GET /app-api/orders`, документацию и нормализацию
  payload Workstaff;
- `3785502` подключил синхронизацию/публикацию заказов;
- `e77ef62` добавил `logist_phone` и ограничение очереди новым назначенным
  логистом;
- `54010fb` удалил только демонстрационную кнопку `Из CRM`, а не серверную
  интеграцию;
- `0a1fe04` убрал integration token из публичной Flutter-конфигурации и
  потребовал его ротацию;
- `d541d4b` разделил server-to-server token и bearer-сессии людей.

Исторический Flutter token из Git считается раскрытым. Его значение запрещено
восстанавливать или копировать. Актуальный token должен жить только в закрытой
настройке Workstaff и `/root/gpm-app-env`.

## 7. Доказательства из production-журнала

Владелец выполнил команду, которая вывела только время и HTTP status без token,
payload и персональных данных.

Успешные запросы `POST /app-api/orders`:

```text
2026-08-05T11:34:04+00:00 200 OK
2026-08-05T13:03:34+00:00 200 OK
2026-08-05T13:13:19+00:00 200 OK
2026-08-07T09:04:47+00:00 200 OK
2026-08-07T11:40:40+00:00 200 OK
2026-08-07T12:25:13+00:00 200 OK
2026-08-11T13:31:53+00:00 200 OK
2026-08-12T08:40:05+00:00 200 OK
2026-08-12T09:16:44+00:00 200 OK
2026-08-12T09:57:31+00:00 200 OK
2026-08-18T10:36:41+00:00 200 OK
```

Неуспешные запросы:

```text
2026-08-25T10:54:36+00:00 401 Unauthorized
2026-08-25T10:54:45+00:00 401 Unauthorized
2026-08-25T10:54:49+00:00 401 Unauthorized
2026-08-25T10:55:08+00:00 401 Unauthorized
2026-08-27T21:43:51+00:00 401 Unauthorized
```

Последний `401` от 27 августа был намеренной диагностикой без token. Источник
четырёх запросов 25 августа пока не установлен. Они могли быть security-тестом
или отправкой Workstaff со старым token.

Дополнительные публичные проверки:

- `https://ts.workstaffcrm.ru/` отвечает HTTP 200;
- GPM `/health` отвечает HTTP 200;
- неавторизованный `POST /app-api/orders` отвечает `401`, а не `503`.

Последнее означает: integration auth на GPM backend настроен, но не доказывает,
что Workstaff хранит тот же token.

## 8. Исправление в `30b2bca`

До исправления Flutter-фронтенд логиста сам фильтровал `NEW`-заявки по телефону
из старого localStorage ключа `gpm.logist.profile.v1`. В production профили уже
серверные, поэтому пришедшая CRM-заявка могла быть скрыта.

Сделано:

- маршрутизация `NEW` по `logist_phone` перенесена на backend;
- backend использует телефон server-backed профиля логиста;
- российские форматы `+7` и `8` сопоставляются по последним десяти цифрам;
- заявка без `logist_phone` видна общей очереди логистов;
- клиентская demo-фильтрация удалена;
- существующая кнопка публикации называется `Опубликовать`;
- подтверждено: worker не видит `NEW`, но видит `PROCESSED`;
- добавлены архитектурная документация и regression tests.

Изменённые файлы коммита:

```text
app/app_orders_api.py
lib/screens/logist/logist_orders_screen.dart
tests/test_app_orders_api.py
CRM_APP_PUBLICATION.md
INDEPENDENT_PLATFORM_ARCHITECTURE.md
README.md
```

Проверки:

```text
backend tests: 23 passed, 1 PostgreSQL test skipped locally
Flutter analyze: no issues
Flutter tests: 3 passed
Flutter web release build: success
git diff --check: clean
GitHub CI 33118388353: success
```

## 9. Контракт CRM → GPM

Endpoint:

```http
POST https://app-api.gpmbot.ru/app-api/orders
Content-Type: application/json
X-Gpm-App-Token: <server-side secret>
```

Минимальные обязательные поля:

```text
order_data.order_number
order_data.completion_date.date
order_data.loaders.loader_count
order_data.info
```

Рекомендуемые routing/source поля:

```text
source_system=workstaff
logist_phone=<телефон профиля логиста GPM>
```

Новая запись нормализуется со статусом `NEW`. Логист публикует её через
authenticated endpoint:

```http
PATCH /app-api/me/orders/{order_id}
Authorization: Bearer <human session>
Content-Type: application/json

{"status":"PROCESSED"}
```

После `PROCESSED` заказ появляется у исполнителей. Повторная отправка того же
`order_number` обновляет бизнес-поля, сохраняя уже начатое workflow.

Нельзя помещать `GPM_APP_API_TOKEN` в Flutter, browser storage, Git, документацию
или сообщения.

## 10. Адреса: DaData сейчас, Яндекс потом

Владелец зарегистрировал DaData, подтвердил email и получил API-ключ. Ключ был
безопасно добавлен в `/root/gpm-app-env` на backend без вывода в чат.

Перед изменением создан backup:

```text
/root/gpm-app-env.before-dadata-20260827
```

Настройка:

```text
GPM_ADDRESS_SUGGESTION_PROVIDER=dadata
DADATA_API_KEY=<server-only secret>
```

После restart первый публичный health кратковременно вернул `502`, затем сервис
стабилизировался и вернул `{"status":"ok","storage":"postgres"}`.

Ручная синтетическая проверка в кабинете логиста прошла: адрес на Тверской был
нормализован, координаты определены, отображено подтверждение локации.

Яндекс подготовлен только в локальной ветке `feature/address-provider-switch`.
Он выключен и не должен включаться без отдельного решения владельца и проверки
лицензии/хранения координат.

## 11. Активные кабинеты и workflow

Клиент:

- создаёт заказ;
- видит только собственные заказы;
- использует server-backed профиль и внутренние чаты.

Логист:

- модерирует `NEW`;
- публикует заказ;
- принимает/отклоняет отклики;
- назначает исполнителей;
- подтверждает завершение;
- использует server-backed dashboard/profile/chats.

Исполнитель:

- видит только опубликованные `PROCESSED` и свои активные/завершённые заказы;
- до назначения не получает точный адрес и контакты;
- откликается и общается во внутренних чатах GPM;
- завершает назначенный заказ;
- видит server-backed dashboard/profile/finance.

State machine:

```text
NEW -> PROCESSED | JUNK
PROCESSED -> IN_PROCESS | JUNK
IN_PROCESS -> DONE_PENDING | JUNK
DONE_PENDING -> IN_PROCESS | CONVERTED | JUNK
CONVERTED -> terminal
JUNK -> terminal
```

Applications/assignments серверные, но пока хранятся в JSON заказа.

## 12. Учётные записи, чаты и финансы

Production использует PostgreSQL-backed:

- accounts и `scrypt` hashes;
- sessions и logout revocation;
- roles и lockout;
- audit log;
- одноразовые invitations;
- profiles;
- dashboards;
- internal chat threads/messages/read state;
- order applications/assignments;
- worker finance summary.

Три синтетические роли:

```text
client
worker
logist
```

Паролей в Git и handoff нет. Финансы — расчёт начислений, не платёжный ledger.
Чаты являются внутренними GPM-чатами, не Telegram.

## 13. Схема PostgreSQL

Production таблицы:

```text
gpm_app_orders
gpm_app_accounts
gpm_app_sessions
gpm_app_audit_log
gpm_app_account_invitations
gpm_app_profiles
gpm_app_chat_threads
gpm_app_chat_messages
gpm_app_chat_reads
gpm_app_schema_migrations
```

Миграции:

```text
0001_db_accounts
0002_account_invitations
0003_role_workspaces
```

Последние безопасные агрегаты остаются историческим снимком от 26.08.2026:

```text
orders=1
accounts=3
active_accounts=3
sessions_total=43
sessions_active=15
invitations_total=3
profiles=0
chat_threads=3
chat_messages=7
audit_events=92
```

Не считать их текущими значениями и не выводить строки с ПДн.

## 14. Backups и rollback

Последний известный DB backup перед миграцией кабинетов:

```text
/root/gpm-private-backups/20260826T114039Z-role-workspaces-predeploy
```

Backend rollback bundle:

```text
/opt/gpm/backups/20260826_114813
```

Предыдущая известная frontend-копия:

```text
/opt/gpm/front-backups/20260826_114835
```

DaData env backup:

```text
/root/gpm-app-env.before-dadata-20260827
```

Deploy workflow создаёт code/venv/frontend rollback, но не заменяет `pg_dump`.
Перед schema/data changes нужен permission-restricted dump и проверка
`pg_restore --list`.

## 15. Секреты

В этот handoff не добавлены значения:

- `GPM_APP_API_TOKEN`/`CRM_API_KEY`;
- `DADATA_API_KEY`;
- JWT secret;
- пароли и hashes;
- session tokens;
- GitHub secrets;
- SSH/private keys;
- database URL/пароль.

Закрытые locations:

```text
/root/gpm-app-env
/root/gpm-app-login.txt
GitHub environment: production
закрытая server-side настройка Workstaff CRM
```

Исторические credentials из Git считать раскрытыми до подтверждённой ротации.
Не читать и не печатать значения server env. Проверять только наличие ключей и
поведение endpoint.

## 16. P0 до реальных пользователей

Разрешены только закрытые тесты с синтетическими данными. До реального запуска:

1. Определить оператора ПДн и договорную роль GPM.
2. Утвердить карту данных, основания, согласия, retention и удаление.
3. Проверить/подать уведомление Роскомнадзору.
4. Подтвердить локализацию DB/log/files/backups в РФ.
5. Заключить поручения обработки с хостером и внешними сервисами.
6. Реализовать подтверждение телефона/email и recovery.
7. Реализовать права субъекта на доступ/исправление/блокировку/удаление.
8. Закрыть ротацию исторических secrets.
9. Провести restore drill, определить PITR/backup retention.
10. Провести E2E-изоляцию минимум двух клиентов и двух исполнителей.

Закон №289-ФЗ о платформенной экономике вступает в силу 01.10.2026. Перед
реальными сделками требуется повторная юридическая оценка.

## 17. Известный технический долг

- backend-монолит `app/app_orders_api.py`;
- крупный `GpmApiService`;
- PostgreSQL/SQLite SQL duplication;
- отсутствие pagination и общего body limit;
- отсутствие IP throttle auth endpoints;
- JSON applications/assignments;
- N+1-подобные запросы кабинета логиста;
- нативный application ID `com.example.gpm_platform`;
- legacy Telegram-код и Telegram-shaped поля в старых моделях;
- отсутствие полноценного password recovery/verification;
- судьба legacy-бота должна решаться отдельной задачей.

Не смешивать этот долг с восстановлением Workstaff webhook.

## 18. Следующий рабочий алгоритм

Сначала только синтетическая заявка и пяти минутный journal check.

### Если `401`

1. Не выводить значения token.
2. На backend подтвердить только имя активной переменной
   `GPM_APP_API_TOKEN`/fallback `CRM_API_KEY`.
3. В закрытой server-side настройке Workstaff заменить token на актуальный.
4. Повторить синтетическую отправку.
5. Требовать `200 OK`.

### Если journal пуст

1. Найти в Workstaff настройку webhook/интеграции, которая раньше отправляла
   `POST https://app-api.gpmbot.ru/app-api/orders`.
2. Восстановить trigger на создание/обновление заявки.
3. Не использовать `/api/telegram/` и messenger identifiers.
4. Повторить тест до `200 OK`.

### Если `200`

1. Проверить новую запись безопасным агрегатом PostgreSQL/API без вывода ПДн.
2. Слить проверенную CRM feature-ветку в `main`.
3. Запустить backend+frontend production deploy только по явному подтверждению
   владельца.
4. Провести ручной E2E: CRM → логист → `Опубликовать` → worker.
5. Зафиксировать run IDs и production SHA в новом handoff.

## 19. Правила следующего чата

- Сначала прочитать этот файл и continuation prompt полностью.
- Не проектировать CRM-интеграцию заново: восстановить исторический push.
- Не использовать Telegram или другие внешние чаты.
- Не восстанавливать исторический integration token.
- Не менять дизайн и цвета.
- Не смешивать CRM и address-provider branches.
- Сначала получить результат точной синтетической проверки.
- Не делать production deploy без явного запроса владельца.
- Любые данные/логи запрашивать в минимальном и обезличенном виде.
- Перед коммитом запускать backend tests, Flutter analyze/tests и
  `git diff --check`.
- После push ждать зелёный CI.
- Перед изменением production DB создавать и проверять backup.

## 20. Ключевые ссылки и runs

```text
GitHub: https://github.com/tonimasite-dotcom/gpm_platform
Application: https://app.gpmbot.ru/
API health: https://app-api.gpmbot.ru/health
Test Workstaff CRM: https://ts.workstaffcrm.ru/
```

```text
30b2bca Restore CRM order publication by logist
92624b7 Add August 27 worker design handoff
b9ebdfa Restore worker workspace design
a6fac5c Add server-backed role workspaces
9a33715 Add invite-only account registration
3c147c7 Add database-backed app accounts
```

```text
CRM feature CI: 33118388353 success
worker design CI: 33065804102 success
frontend deploy b9ebdfa: 33066080151 success
backend/all deploy a6fac5c: 32965029082 success
```

GitHub — источник истины для кода. Production DB, backups, server env и закрытая
настройка Workstaff хранятся вне Git.

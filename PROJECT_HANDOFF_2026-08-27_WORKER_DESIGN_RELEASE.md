# GPM: полный handoff после восстановления кабинета исполнителя

Дата снимка: 27.08.2026. Часовой пояс: Europe/Moscow.

Это главный источник истины для следующего чата. Более ранние
`PROJECT_HANDOFF_*` и `CONTINUE_PROJECT_PROMPT_*` сохраняют историю, но не
описывают последний frontend-релиз `b9ebdfa`.

Читайте вместе с:

- `CONTINUE_PROJECT_PROMPT_2026-08-27_WORKER_DESIGN_RELEASE.md`;
- `NEW_DEVICE_SETUP_2026-08-26.md`;
- `README.md`;
- `PROJECT_AUDIT_2026-08-25.md`;
- `LEGAL_READINESS_RU.md`;
- `PRODUCTION_DEPLOYMENT.md`;
- `SECRET_ROTATION.md`.

## 1. Точная точка остановки

В production восстановлены прежняя структура, наполнение и визуальная подача
кабинета исполнителя. Демо-показатели не возвращались: сводка, профиль,
назначения и финансы по-прежнему берутся с backend.

Git на момент создания этого документа:

```text
branch: main
HEAD: b9ebdfa0c9c389dd43d3872fb33fd8e9ed89e92e
origin/main: b9ebdfa0c9c389dd43d3872fb33fd8e9ed89e92e
working tree: clean
tracked files before this documentation commit: 248
```

Технические production-коммиты разделены:

```text
frontend: b9ebdfa0c9c389dd43d3872fb33fd8e9ed89e92e
backend:  a6fac5caa834ffe268e97e347063acaf9defdfc0
```

Документационный коммит этого снапшота будет потомком `b9ebdfa` и не требует
повторного production-деплоя.

Публичные адреса:

- приложение: https://app.gpmbot.ru/;
- API: https://app-api.gpmbot.ru/;
- health: https://app-api.gpmbot.ru/health;
- GitHub: https://github.com/tonimasite-dotcom/gpm_platform.

Проверка после последнего релиза:

```text
frontend: HTTP 200
frontend Last-Modified: 27.08.2026 11:09:24 UTC
health: {"status":"ok","storage":"postgres"}
public .env: только GPM_APP_MODE и GPM_APP_API_URL
```

Разрешённый режим не изменился: только закрытое тестирование на полностью
синтетических данных. Публичный URL не означает готовность к реальным ПДн или
коммерческому запуску.

## 2. Что вошло в релиз `b9ebdfa`

### Главная исполнителя

Возвращена компактная структура из прежнего кабинета:

- заголовок `КАБИНЕТ ИСПОЛНИТЕЛЯ`;
- пояснение о заявках, сменах и выплатах;
- три светло-жёлтые карточки: активные заявки, рейтинг, выплаты;
- значения приходят из `/app-api/me/dashboard`.

Активные заявки в карточке — сумма ожидающих откликов и назначенных активных
заказов. Рейтинг берётся из серверного профиля, выплаты — из серверной сводки.

### Профиль исполнителя

Возвращены блоки и компоновка прежнего экрана:

- шапка с именем, username/Telegram и группой приоритета;
- `Основные данные`;
- адрес: город, улица, дом, квартира/офис;
- `Выплаты`: счёт или карта;
- `Проверки`;
- рейтинг, успешные заказы и срывы;
- сохранение профиля на backend.

Dev-переключатели самостоятельного подтверждения паспорта, НПД и штатности не
возвращены. В production отображаются серверные статусы. Паспортные номера и ИНН
не подставляются фиктивно.

### Финансы исполнителя

Возвращена прежняя фиолетовая карточка:

- доступно к выводу;
- число завершённых заказов;
- история начислений;
- состояния `доступно` и `на подтверждении`.

Данные берутся из `/app-api/me/finance`. Кнопка вывода отключена, потому что это
пока расчёт начислений, а не платёжный ledger.

### Заказы исполнителя

Исправлен критичный frontend-дефект: backend уже вычислял
`worker_application_status` и `is_assigned_to_worker` по bearer session, но
Flutter повторно перезаписывал их через `worker-demo-1`.

Теперь в API/production режиме `getOrdersForWorker()` сохраняет серверные поля.
Это возвращает реальные данные во вкладки `Мои` и `История`. В demo-режиме
прежнее локальное обогащение сохраняется.

Основная кнопка действия заказа переведена на жёлтый GPM CTA, табы используют
малиновый акцент общей темы, карточки стали плоскими.

### Визуальная система

Эталон:

- светло-серый фон страницы;
- белые карточки и поля;
- тонкие светло-серые границы;
- малиновый акцент выбора и навигации;
- жёлтые основные CTA;
- компактная нижняя навигация;
- фиолетовый сохранён только для прежнего аватара и финансовой карточки
  исполнителя.

Общие токены находятся в `lib/theme/gpm_theme.dart` и применяются к трём
кабинетам. Не заменять их случайными локальными цветами без сверки с эталоном.

## 3. Проверки и публикация релиза

Локально перед публикацией:

- backend tests: 21, успешно; PostgreSQL integration test пропущен локально по
  штатному условию отсутствия `GPM_TEST_POSTGRES_URL`;
- Dart/Flutter analyze: без замечаний;
- Flutter tests: 3/3, успешно;
- новый regression test:
  `API worker orders preserve server-owned worker metadata`;
- Flutter Web release build: успешно;
- `git diff --check`: чисто.

GitHub CI:

```text
run: 33065804102
commit: b9ebdfa
conclusion: success
backend: PostgreSQL 17 integration included
Flutter: analyze/tests success
```

Production deployment:

```text
run: 33066080151
target: frontend
commit: b9ebdfa
conclusion: success
```

Backend и БД не переключались. Изменений схемы или production-данных не было,
поэтому новый `pg_dump` для этого frontend-релиза не создавался.

## 4. Активная архитектура

```text
External order system -- X-Gpm-App-Token --> FastAPI
                                               |
Flutter Web -- Bearer session -----------------+
                                               |
                                               v
                                         PostgreSQL 17
```

Активные части:

- Flutter entrypoint: `lib/main.dart`;
- активные экраны: `lib/screens/**`;
- API client/state: `lib/services/gpm_api_service.dart`;
- chats: `lib/services/chat_service.dart`;
- theme: `lib/theme/gpm_theme.dart`;
- backend: `app/app_orders_api.py`;
- backend tests: `tests/test_app_orders_api.py`;
- Flutter tests: `test/**`;
- CI: `.github/workflows/ci.yml`;
- deploy: `.github/workflows/deploy-production.yml`.

Backend — FastAPI без ORM, с параметризованным SQL для PostgreSQL/SQLite.
Flutter — единая кодовая база web/mobile/desktop, без router/state-manager;
состояние в основном управляется сервисами, глобальными экземплярами и
`setState`.

Legacy Telegram-бот в `main.py` и `app/handlers/**` отключён переменной
`GPM_ENABLE_LEGACY_BOT`. Не включать его с реальными данными без отдельного
аудита: в legacy остаются отдельная модель данных, HTTP handler и небезопасные
системные вызовы.

## 5. Учётные записи и доступ

Опубликовано и работает:

- DB-backed accounts в PostgreSQL;
- `scrypt` password hashes;
- серверное назначение ролей;
- JWT с проверкой алгоритма и сильного secret;
- серверные sessions и logout revocation;
- lockout после неудачных входов;
- audit log;
- регистрация только по одноразовым invitations;
- три синтетических пользователя: `client`, `worker`, `logist`;
- общий `admin/admin` отключён.

Не готово:

- подтверждение телефона/email;
- смена и восстановление пароля;
- web refresh-session model;
- IP rate limiting;
- полный регламент отзыва доступа.

На нативных платформах сессия сейчас не переживает перезапуск: storage stub
ничего не сохраняет. Web использует `localStorage`. До нативного релиза нужен
secure storage; для web нужен отдельный разбор refresh/session и XSS-модели.

## 6. Роли и рабочий процесс заказов

Клиент:

- создаёт заказ;
- видит только собственные заказы;
- использует серверный профиль и чаты.

Логист:

- видит и обрабатывает заказы;
- публикует заказ;
- принимает или отклоняет отклики;
- назначает исполнителей;
- подтверждает завершение;
- использует dashboard/profile/chats.

Исполнитель:

- видит опубликованные заказы с закрытыми контактами;
- откликается;
- видит ожидающие, назначенные и завершённые заказы;
- завершает назначенный заказ;
- использует серверные dashboard/profile/chats/finance.

Applications и assignments сохраняются на сервере, но пока находятся внутри
JSON заказа. При росте нагрузки и аналитики нужны отдельные таблицы и единая
state machine.

## 7. Чаты и финансы

Чаты хранятся в PostgreSQL. Доступны каналы:

- client–logist;
- worker–logist;
- client–worker;
- support.

Есть сообщения, unread/read, отметка внимания логиста и проверка участника
заказа. До реальных сообщений отдельно оценить правовой статус, retention и
права доступа.

Финансы исполнителя рассчитываются по назначенным заказам в состояниях
`DONE_PENDING` и `CONVERTED`. Это не платёжный контур. Нет:

- ledger;
- эквайринга и выплат;
- чеков НПД;
- отмен, возвратов и сверки;
- подтверждения НПД через официальный сервис ФНС.

## 8. Схема данных

Production PostgreSQL содержит:

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

Применённые миграции:

```text
0001_db_accounts
0002_account_invitations
0003_role_workspaces
```

Последние документированные агрегаты от 26.08.2026:

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

Это исторический безопасный снимок, а не контрольные значения: после тестов
счётчики могли измениться. Не запрашивать и не выводить строки с ПДн или secrets.

## 9. Production и rollback

Backend:

```text
Host: 46.149.71.147
Repository: /opt/gpm/gpm_platform
Service: gpm-app-api.service
EnvironmentFile: /root/gpm-app-env
Backend SHA: a6fac5c
Database: PostgreSQL
```

Frontend:

```text
Host: 186.246.10.163
Web root: /var/www/gpm-app
Server: nginx
Frontend SHA: b9ebdfa
```

Последний известный DB backup перед миграцией кабинетов:

```text
/root/gpm-private-backups/20260826T114039Z-role-workspaces-predeploy
```

Последний документированный backend rollback bundle:

```text
/opt/gpm/backups/20260826_114813
```

Frontend deploy `33066080151` создал новую автоматическую копию в
`/opt/gpm/front-backups`; точное имя каталога не выводилось в Actions summary и
в этом документе не выдумывается. Предыдущая известная копия:

```text
/opt/gpm/front-backups/20260826_114835
```

Workflow хранит rollback кода/venv/frontend, но не делает `pg_dump`. Перед
любыми изменениями схемы или данных создавать отдельный permission-restricted
dump, проверять `pg_restore --list` и записывать путь.

## 10. Секреты

Значения паролей, токенов, hashes и private keys в Git и handoff не записаны.

Закрытые production locations:

```text
/root/gpm-app-env
/root/gpm-app-login.txt
GitHub environment: production
```

Никогда не печатать в чат или лог:

- server env и login file;
- JWT/API secrets;
- пароли пользователей;
- session tokens;
- GitHub secrets;
- SSH private keys.

Исторические credentials из `SECRET_ROTATION.md` считать скомпрометированными
до документированного подтверждения ротации. Чек-лист ротации остаётся открытым.

Для штатного deploy локальный SSH key не нужен: GitHub Actions использует
environment secrets. Код переносится через GitHub, пароли — отдельно через
менеджер паролей или защищённый носитель.

## 11. P0 до реальных пользователей

1. Определить оператора ПДн, реквизиты и договорную роль GPM.
2. Утвердить карту данных, основания, согласия, retention и удаление.
3. Проверить или подать уведомление Роскомнадзору.
4. Подтвердить локализацию БД, логов, файлов и backup в РФ.
5. Заключить поручения обработки с хостером и внешними сервисами.
6. Реализовать подтверждение телефона/email и recovery.
7. Реализовать права субъекта: доступ, исправление, блокировка, удаление.
8. Проверить исторические журналы и закрыть ротацию старых secrets.
9. Провести restore drill и определить PITR/retention backup.
10. Провести E2E-изоляцию минимум двух клиентов и двух исполнителей.

Отдельный срок: закон №289-ФЗ о платформенной экономике вступает в силу
01.10.2026. Правовую модель сделок и платформы проверить с профильным юристом до
реального запуска.

## 12. Другие известные технические долги

- backend-монолит `app/app_orders_api.py`;
- крупный `GpmApiService`;
- дублирование SQL PostgreSQL/SQLite;
- отсутствие pagination и общего request body limit;
- отсутствие IP throttle на auth endpoints;
- слабая валидация полей цен;
- JSON applications/assignments;
- N+1-подобные клиентские запросы в аналитике логиста;
- мёртвые/дублирующиеся Flutter-экраны, включая старую регистрацию;
- нативный application ID `com.example.gpm_platform`;
- закоммиченный legacy `.backup`;
- отсутствие LICENSE/CONTRIBUTING;
- судьба legacy-бота не решена.

Не смешивать эти задачи в один релиз. Сначала устранять пользовательские ошибки
текущего ролевого workflow, затем account P0.

## 13. Точная следующая рабочая точка

После восстановления дизайна владелец должен вручную проверить production на
синтетических данных:

1. Очистить browser cache или сделать hard refresh.
2. Войти как `worker`.
3. Сверить главную, профиль и финансы с утверждёнными скриншотами.
4. Убедиться, что вкладки `Доступные`, `Мои`, `История` показывают правильные
   серверные состояния.
5. Пройти полный поток: client создаёт заказ → logist публикует → worker
   откликается → logist назначает → чаты → worker завершает → logist закрывает
   → worker видит начисление.
6. Проверить сохранение профиля всех трёх ролей.
7. Зафиксировать конкретные UX-ошибки: роль, вкладка, действие, ожидаемое и
   фактическое поведение, скриншот без ПДн.

После ручного E2E рекомендуемый следующий технический этап:

```text
подтверждение телефона/email + восстановление доступа
```

До завершения E2E не начинать широкую переработку архитектуры или платежей.

## 14. Правила продолжения

- Сначала полностью прочитать этот handoff и новый prompt.
- Проверить Git и публичные URL read-only.
- Не повторять миграции и уже успешные deploy runs.
- Любую доработку делать в отдельной feature-ветке.
- Не трогать несвязанные пользовательские изменения.
- Тестировать только на синтетических данных.
- Перед коммитом запускать backend tests, Flutter analyze/tests и
  `git diff --check`.
- После push дождаться зелёного CI.
- Перед production schema/data change создать проверенный DB dump.
- Production публиковать только по явному запросу владельца.
- Не удалять backups и журналы без решения по retention/legal hold.
- Не возвращать демо-цифры или self-verification в production UI.
- Сохранять сервер как источник истины для ролей, ownership и назначений.

## 15. Ключевые коммиты и runs

```text
b9ebdfa Restore worker workspace design
ed5a689 Add August 26 role workspace handoff
a6fac5c Add server-backed role workspaces
9a33715 Add invite-only account registration
3c147c7 Add database-backed app accounts
67e16bb Add August 25 production release handoff
efec81f Validate production runtime before service switch
c88d8e4 Harden production dependency deployment
691e479 Audit project readiness, security, and compliance
```

```text
CI b9ebdfa: 33065804102 success
frontend deploy b9ebdfa: 33066080151 success
previous all deploy a6fac5c: 32965029082 success
previous CI a6fac5c: 32964687097 success
```

GitHub — источник истины для кода и истории. Production DB dumps, server env и
rollback directories находятся отдельно и в Git не входят.

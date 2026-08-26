# GPM: полный handoff после запуска личных кабинетов

Дата снимка: 26.08.2026. Часовой пояс: Europe/Moscow.

Это главный источник истины для следующего чата. Старые `PROJECT_HANDOFF_*`
сохраняют историю, но описывают уже отменённые ограничения и релизы.

Читайте вместе с:

- `CONTINUE_PROJECT_PROMPT_2026-08-26_ROLE_WORKSPACES.md`;
- `NEW_DEVICE_SETUP_2026-08-26.md`;
- `README.md`;
- `PROJECT_AUDIT_2026-08-25.md`;
- `LEGAL_READINESS_RU.md`;
- `PRODUCTION_DEPLOYMENT.md`.

## 1. Где остановились

Личные кабинеты трёх тестовых ролей переведены с production-заглушек на
серверные данные и опубликованы:

- приложение: https://app.gpmbot.ru/;
- API: https://app-api.gpmbot.ru/;
- health: https://app-api.gpmbot.ru/health;
- GitHub: https://github.com/tonimasite-dotcom/gpm_platform.

Рабочий production-коммит:

```text
a6fac5caa834ffe268e97e347063acaf9defdfc0
Add server-backed role workspaces
```

До создания этого документа `main`, `origin/main` и production backend
совпадали на `a6fac5c`. Рабочая копия была чистой. Коммит снапшота будет
документационным потомком. Он не требует повторного деплоя.

Текущий режим: закрытое тестирование на синтетических данных. Наличие публичного
URL не означает готовность к реальным ПДн или открытому коммерческому запуску.

## 2. Что теперь работает

### Доступ и учётные записи

- аккаунты хранятся в PostgreSQL;
- пароли хешируются через `scrypt`;
- роль назначает backend;
- сессии хранятся на сервере и отзываются при выходе;
- есть блокировка после неудачных входов;
- действия входа и регистрации попадают в audit log;
- регистрация работает только по одноразовым приглашениям;
- сохранены три тестовых пользователя: `client`, `worker`, `logist`;
- общий `admin/admin` отключён.

Нет подтверждения телефона/email и восстановления пароля. Это следующий P0.

### Заказы и роли

- клиент создаёт и видит свои заказы;
- логист обрабатывает заказ и управляет заявками;
- исполнитель видит опубликованные заказы без закрытых контактов;
- исполнитель подаёт отклик;
- логист принимает или отклоняет отклик;
- назначенный исполнитель получает нужные данные заказа;
- исполнитель завершает работу;
- логист закрывает заказ;
- ролевые ограничения проверяет backend.

Applications и assignments серверные, но пока находятся внутри JSON заказа, а
не в отдельных нормализованных таблицах.

### Личные кабинеты

Исполнитель:

- реальная сводка: доступные, ожидающие, активные и завершённые заказы;
- ближайший заказ;
- готовность профиля;
- реальные начисления по завершённым заказам;
- серверный профиль и реквизиты выплаты;
- серверные чаты.

Клиент и логист:

- рабочие заказы и ролевые действия;
- серверные профили;
- серверные сводки API;
- серверные чаты.

Фиктивные production-показатели и экраны «готовится/недоступно» удалены.
Пустой экран теперь означает отсутствие реальных данных.

### Чаты

- переписка хранится в PostgreSQL;
- каналы создаются по заказу и назначению;
- есть client–logist, worker–logist, client–worker и support;
- работают сообщения, unread/read и отметка внимания логиста;
- доступ ограничен участниками заказа и логистом.

### Финансы

- баланс исполнителя считается только по назначенным завершённым заказам;
- есть доступная и ожидающая сумма;
- показываются реальные начисления по заказам;
- фиктивный баланс отключён.

Это ещё не платёжный контур. Нет ledger, эквайринга, выплат, чеков, возвратов и
сверки. Реквизиты выплаты пока только профильные данные.

## 3. Активная архитектура

```text
Flutter Web -> FastAPI -> PostgreSQL
                          |
External order system ----+
```

Активные части:

- Flutter: `lib/main.dart`, `lib/screens/**`;
- API-клиент: `lib/services/gpm_api_service.dart`;
- чаты Flutter: `lib/services/chat_service.dart`;
- backend: `app/app_orders_api.py`;
- тесты backend: `tests/test_app_orders_api.py`;
- widget-тесты: `test/**`;
- CI: `.github/workflows/ci.yml`;
- production: `.github/workflows/deploy-production.yml`.

Legacy Telegram-бот в `main.py` и `app/handlers/**` выключен. Не включать его с
реальными данными без отдельного аудита и переработки.

## 4. Схема данных

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

Применённые версии:

```text
0001_db_accounts
0002_account_invitations
0003_role_workspaces
```

Безопасные агрегированные счётчики на момент снимка:

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

`profiles=0` не означает ошибку: профиль создаётся с серверными значениями по
умолчанию и записывается после первого сохранения формы. Счётчики могут меняться
после тестов. Не считать их постоянными контрольными значениями.

## 5. Production

Backend:

```text
Host: 46.149.71.147
Hostname: msk-1-vm-smqt
Repository: /opt/gpm/gpm_platform
Service: gpm-app-api.service
EnvironmentFile: /root/gpm-app-env
Venv: /opt/gpm/venvs/gpm-app-a6fac5caa834ffe268e97e347063acaf9defdfc0
Database: PostgreSQL
```

Frontend:

```text
Host: 186.246.10.163
Hostname: gpm-app-prod
Web root: /var/www/gpm-app
Server: nginx
```

Публичный Flutter `.env` содержит только:

```text
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Секретов во frontend нет и быть не должно.

## 6. Проверки релиза

Коммит `a6fac5c` прошёл:

- локальные backend-тесты: 21, один PostgreSQL-тест пропущен локально;
- GitHub CI backend с PostgreSQL 17: успешно;
- GitHub CI Flutter: успешно;
- `flutter analyze`: без замечаний;
- Flutter widget tests: 2/2;
- production web build: успешно в ASCII-пути;
- CI run: `32964687097`;
- production run: `32965029082`, conclusion `success`;
- публичный frontend: HTTP 200;
- health: `{"status":"ok","storage":"postgres"}`;
- авторизованные profile/dashboard/chats/orders для трёх ролей: успешно;
- finance исполнителя: успешно;
- backend service: active;
- production backend SHA: `a6fac5c`.

Windows Flutter shader compiler не пишет шейдеры в путь с кириллицей. Для
release build используйте ASCII-каталог под `C:\tmp` или Linux CI.

## 7. Резервные копии и откат

Не удалять без решения по retention и legal hold.

Перед последней миграцией кабинетов:

```text
/root/gpm-private-backups/20260826T114039Z-role-workspaces-predeploy
```

Там лежат custom dump PostgreSQL, закрытая копия env и SHA-256 dump.

Последний backend deploy:

```text
/opt/gpm/backups/20260826_114813
```

Последний frontend deploy:

```text
/opt/gpm/front-backups/20260826_114835
```

Предыдущие важные копии:

```text
/root/gpm-private-backups/20260826T083348Z-db-accounts-invite-predeploy
/opt/gpm/backups/20260826_084100
/opt/gpm/front-backups/20260826_084122
/root/gpm-private-backups/20260825_134724
/opt/gpm/backups/20260825_135138
```

Workflow сам сохраняет код/venv и frontend. Перед изменением схемы или данных
отдельно делать `pg_dump`: workflow пока не создаёт dump PostgreSQL.

## 8. Пароли и секреты

В Git и этом снимке нет значений паролей, токенов и private keys.

Production-реквизиты находятся только в закрытом контуре:

```text
/root/gpm-app-env
/root/gpm-app-login.txt
GitHub environment: production
```

Локальные временные SSH-файлы старого устройства не являются частью проекта.
Не переносить их через обычную почту, мессенджер или публичное облако.

На новом устройстве:

- код получить из GitHub;
- пароли — из менеджера паролей или защищённого канала;
- deploy через GitHub Actions не требует копировать private key на устройство;
- прямой SSH использовать только при отдельной необходимости и с проверенным
  host key.

Никогда не печатать в чат или лог:

- `/root/gpm-app-env`;
- `/root/gpm-app-login.txt`;
- JWT/API secrets;
- пароли пользователей;
- GitHub secrets;
- SSH private keys;
- токены сессий.

## 9. Что ещё не готово

### P0 до реальных пользователей

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

### Продукт и backend

- реальная проверка исполнителя и процесс модерации документов;
- отдельные таблицы applications/assignments и единая state machine;
- полноценный ledger, выплаты, чеки НПД, отмены и возвраты;
- подтверждение НПД через официальный сервис ФНС;
- нормализованные организации/тенанты для логистов;
- пагинация, лимиты тела запроса и расширенный rate limiting;
- web refresh-session model;
- адресные подсказки после решения DaData/Яндекс и правовой оценки;
- desktop navigation, deep links, browser history и accessibility;
- единый словарь статусов и названий исполнителей.

### Инфраструктура

- непривилегированный runtime DB user;
- отдельные deploy/runtime users вместо root;
- мониторинг, алерты и контроль свободного места;
- политика совместимости и общего rollback frontend/backend;
- окончательное архивирование либо модернизация legacy-бота.

## 10. Следующая рабочая точка

Сначала владелец проходит полный синтетический сценарий в production:

1. клиент создаёт заказ;
2. логист публикует его;
3. исполнитель откликается;
4. логист назначает исполнителя;
5. участники проверяют чаты;
6. исполнитель завершает заказ;
7. логист закрывает заказ;
8. исполнитель проверяет начисление;
9. каждая роль заполняет и сохраняет профиль.

Фиксировать только конкретные ошибки: роль, вкладка, действие, ожидаемый и
фактический результат, скриншот без ПДн.

После UX-проверки рекомендуемый следующий технический этап — подтверждение
контактов и восстановление доступа. Он закрывает главный остаточный риск
аккаунтов, не затрагивая платежи и документы исполнителей.

## 11. Правила продолжения

- Сначала прочитать этот handoff и prompt целиком.
- Проверить Git и публичные URL без изменений.
- Не повторять уже завершённые миграции и деплой.
- Любую доработку делать в отдельной ветке.
- Не смешивать UX-задачу с правовыми, платёжными и инфраструктурными изменениями.
- Перед коммитом запускать backend tests, Flutter tests/analyze и
  `git diff --check`.
- Перед production-изменением данных или схемы делать отдельный DB dump.
- Production публиковать только по явному запросу владельца.
- Тестировать только на синтетических данных, пока P0 не закрыты.

## 12. Ключевые коммиты

```text
a6fac5c Add server-backed role workspaces
9a33715 Add invite-only account registration
3c147c7 Add database-backed app accounts
67e16bb Add August 25 production release handoff
efec81f Validate production runtime before service switch
c88d8e4 Harden production dependency deployment
691e479 Audit project readiness, security, and compliance
```

На момент снимка в Git 244 tracked-файла. GitHub — источник истины для кода и
истории. Резервные копии БД и серверов находятся отдельно и в Git не входят.

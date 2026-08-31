# GPM Platform: полный снапшот проекта и точка продолжения

Дата: 31.08.2026. Часовой пояс: Europe/Moscow.

Этот файл — главный источник истины для следующего чата. Он объединяет текущее
состояние проекта, production, архитектуру, роли, безопасность, инфраструктуру,
результаты работы 31 августа и незавершённую задачу.

Стартовый промпт нового чата:

```text
CONTINUE_PROJECT_PROMPT_2026-08-31_FULL_PROJECT_SNAPSHOT.md
```

Подробный журнал именно работ 31 августа также сохранён в:

```text
PROJECT_HANDOFF_2026-08-31_CRM_LIVE_DRAFT_EDITOR_PENDING.md
```

## 1. Главная точка продолжения

CRM ownership, публикация назначенным логистом и фильтрация заказов по городу
уже работают в production.

Редактирование заявки перед публикацией полностью реализовано, протестировано и
отправлено в ветку `feature/edit-order-drafts`, но ещё не слито в `main` и не
развёрнуто в production.

Следующее действие — только после явного подтверждения владельца:

1. fast-forward слить `feature/edit-order-drafts` в `main`;
2. отправить `main` в origin;
3. дождаться CI/demo;
4. вручную запустить production workflow с `target=all`;
5. проверить роли и редактирование нового черновика.

До подтверждения ничего не деплоить.

## 2. Git

Состояние перед созданием этого полного снапшота:

```text
current branch: feature/edit-order-drafts
current HEAD:   800fe9820ea4e6946b39f0a2b876feed9dbee30d
origin branch:  800fe9820ea4e6946b39f0a2b876feed9dbee30d
main:           7024d76e89648f99ea94df34a3bd958f8683ab16
origin/main:    7024d76e89648f99ea94df34a3bd958f8683ab16
working tree:   clean
```

`800fe98` — предыдущий handoff. Функциональный код редактора находится в его
родительском коммите `b3f85df`. Коммит, содержащий этот полный снапшот и
обновлённый README, будет следующим коммитом той же feature-ветки; его точный
SHA нужно брать из `git log -1`.

Основная цепочка текущей работы:

```text
411561b Remove Telegram field, make email/cities optional for logist profile
e196a44 Add post-deploy handoff for logist profile release
935649c Restore CRM order publication by logist
8de928f Enforce order ownership and city visibility
e8c4432 Handle CRM order numbers containing slashes
7024d76 Infer CRM order city from address                    <- main/production backend
b3f85df Allow order owners to edit drafts before publishing <- готовая новая функция
800fe98 Add August 31 CRM and draft editor handoff
```

Важные ветки:

```text
main                                    7024d76
release/crm-logist-city-visibility      8de928f
fix/crm-order-id-slash                  e8c4432
fix/crm-city-from-address               7024d76
feature/edit-order-drafts               текущая ветка
feature/invite-registration             9a33715, историческая feature-ветка
feature/worker-profile-moderation       5f5e8af, историческая feature-ветка
release/worker-profile-moderation       659f3d1
```

Не пытаться повторно cherry-pick старую CRM-ветку: нужные CRM-коммиты уже в
`main` через `935649c` и `8de928f`.

## 3. Production

Публичные адреса:

```text
frontend: https://app.gpmbot.ru/
backend:  https://app-api.gpmbot.ru/
health:   https://app-api.gpmbot.ru/health
```

Текущее разнесённое состояние:

```text
production backend code:  7024d76
production frontend code: 8de928f
```

Это нормально: два последних исправления затрагивали только backend.

Production-деплои 31 августа:

```text
run #8  8de928f  CRM ownership/city visibility  success
https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33372844185

run #9  e8c4432  slash in CRM order IDs          success
https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33375456234

run #10 7024d76  infer city from CRM address     success
https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33379568607
```

Последние подтверждённые post-deploy результаты:

```text
/health                  -> status=ok, storage=postgres
frontend                 -> HTTP 200
frontend assets/.env     -> production mode + публичный API URL, без secrets
```

Production разрешён только для закрытого тестирования на синтетических данных.
Реальные ФИО, телефоны, документы, ИНН, адреса, банковские данные и переписку
вводить нельзя до закрытия P0 из `PROJECT_AUDIT_2026-08-25.md` и
`LEGAL_READINESS_RU.md`.

## 4. Активная архитектура

```text
CRM -> server-to-server GPM API -> PostgreSQL -> Flutter web/Android
```

Активные компоненты:

```text
Flutter entrypoint: lib/main.dart
Flutter screens:    lib/screens/**
Flutter API client: lib/services/gpm_api_service.dart
FastAPI backend:    app/app_orders_api.py (`uvicorn app.app_orders_api:app`)
Database models:    app/db/** и schema helpers в активном API
Legacy bot entry:   main.py, по умолчанию завершает работу без явного enable
```

Legacy-контур:

```text
app/handlers/**
app/services/**
старые lib/client/**, lib/worker/**, lib/logist/** и корневые дубли экранов
```

Legacy Telegram-бот не является частью production-потока. Не включать его как
резервный канал. GPM должна работать независимо от Telegram, мессенджеров и
социальных сетей.

Bitrix24 не является ядром заказов. CRM — только внешний источник данных.
Главный источник истины — backend GPM и PostgreSQL.

Подробнее:

```text
INDEPENDENT_PLATFORM_ARCHITECTURE.md
CRM_APP_PUBLICATION.md
BITRIX24_INTEGRATION.md
```

## 5. Роли и права

### Клиент

- видит только свои заказы;
- создаёт заказ в приложении;
- в готовой feature-ветке сначала создаёт `NEW`-черновик;
- может исправить только собственный `NEW`;
- публикует свой заказ;
- работает с откликами, назначением, подтверждением завершения и чатом только в
  рамках собственного заказа.

### Исполнитель

- видит только опубликованные заказы подходящего города;
- не видит точный адрес и чувствительные данные до назначения;
- после назначения видит адрес работ;
- может откликаться только при совпадении города;
- работает со своими назначениями, чатами и начислениями;
- не может редактировать черновики заказов.

### Логист GPM, назначенный CRM

- CRM передаёт его `logist_phone`;
- backend разрешает телефон в ровно один активный серверный аккаунт;
- заявка закрепляется через `logist_account_id`;
- только этот логист видит CRM-черновик, публикует его и обрабатывает отклики;
- в готовой feature-ветке может исправить рабочие поля `NEW` до публикации;
- CRM-номер, источник и назначение менять не может.

### Частный логист или логист другой компании

- не видит CRM-заявки GPM;
- не может их публиковать;
- создаёт собственные заявки только в приложении;
- в готовой feature-ветке использует тот же поток черновик → правка → публикация.

Текущее ограничение модели: отдельной таблицы компаний или флага членства GPM
пока нет. Право на конкретную CRM-заявку обеспечивается строгим назначением по
телефону и `logist_account_id`. Явная company membership — отдельная будущая
задача, если она понадобится.

## 6. Жизненный цикл заказа

Основные статусы, используемые кодом:

```text
NEW          черновик / на модерации
PROCESSED    опубликован
JUNK         отклонён
IN_PROGRESS  в работе
DONE_PENDING ждёт подтверждения завершения
DONE         завершён
```

Названия в интерфейсах разных ролей могут отличаться. Перед изменением state
machine нужно отдельно согласовать единый словарь.

Правила:

- CRM создаёт или обновляет серверный черновик;
- повторный импорт не должен стирать отклики, назначения и жизненный цикл;
- публикация переводит `NEW` в `PROCESSED`;
- редактирование через новый editor допустимо только в `NEW`;
- опубликованный заказ через editor неизменяем и возвращает `409`;
- номер заказа со слешем поддерживается маршрутами `{order_id:path}`.

## 7. CRM ownership и город — уже в production

CRM обязана передать:

```text
logist_phone
order_data.order_number
order_data.completion_date.date
order_data.loaders.loader_count
order_data.info
```

Неизвестный, отсутствующий или неоднозначный `logist_phone` отклоняется. Общей
CRM-очереди логистов нет.

Исполнитель получает заказ только при нормализованном совпадении города с одним
из значений `profile.cities`. Если CRM не передала отдельный город, backend
пытается безопасно определить его из адреса, например `г Москва, ...`.

31 августа пользователь вручную подтвердил:

- другой логист не видит чужую CRM-заявку;
- публикация номера `033/25` работает после исправления slash route;
- исполнитель с городом Москва видит московскую заявку после city fallback.

## 8. Редактор перед публикацией — готов, но не выпущен

Функциональный коммит:

```text
b3f85dfce970e073e2ae8f4aae904443afbdc24e
```

Изменённые файлы:

```text
CRM_APP_PUBLICATION.md
app/app_orders_api.py
lib/screens/client/client_home_screen.dart
lib/screens/client/client_orders_screen.dart
lib/screens/logist/logist_orders_screen.dart
lib/screens/orders/order_draft_edit_screen.dart
lib/services/gpm_api_service.dart
test/gpm_api_service_test.dart
test/order_draft_edit_screen_test.dart
tests/test_app_orders_api.py
```

Backend разрешает владельцу менять рабочие поля только у `NEW`: название,
описание, город, дату/время, адрес, метро, количество работников, часы,
гражданство, режим и описание смены, минимальное время, ставки/цены и
дополнительную информацию.

Системные поля защищены. Смена адреса очищает устаревшие координаты. Дата должна
быть с timezone, минимум через 30 минут и не дальше 366 дней. Изменение пишется
в audit как `order_draft_updated`.

Локальные проверки функционального коммита:

```text
backend tests:  31 passed, 1 PostgreSQL-only skipped locally
Flutter tests:  7 passed
Flutter analyze: No issues found
```

CI функционального коммита:

```text
run #35: success
https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33382173657
```

## 9. Как проверять редактор после будущего деплоя

Старая заявка `033/25` уже опубликована и не подходит. Нужен новый `NEW` с датой
минимум на 30 минут вперёд.

1. Создать в CRM новый заказ для логиста А из GPM.
2. Под логистом А открыть «На модерации».
3. Изменить адрес, дату, людей или ставку; сохранить.
4. Переоткрыть заявку и проверить сохранённые значения.
5. Под логистом Б убедиться, что CRM-заявки нет.
6. Под логистом А опубликовать её.
7. Убедиться, что editor исчез.
8. Проверить видимость у исполнителя подходящего и неподходящего города.
9. Под частным логистом создать, исправить и опубликовать собственный черновик.
10. Под клиентом повторить тот же сценарий.

## 10. Аккаунты и регистрация

Активная авторизация использует PostgreSQL-таблицы аккаунтов, сессий, аудита и
одноразовых приглашений. Пароли хешируются через versioned scrypt. JWT содержит
account/session IDs и проверяется сервером. После пяти ошибок вход блокируется
на 15 минут. Logout отзывает серверную сессию.

Публичная регистрация закрыта. Роль и логин задаёт одноразовое приглашение.
Регистрация логистов как новая продуктовая задача отложена и не должна
начинаться без отдельного запроса.

31 августа создан временный тестовый комплект:

```text
qa-b-20260831
```

Защищённый серверный файл:

```text
/root/gpm-app-invitations-qa-b-20260831.json
```

Он содержит secrets, имеет режим `600` и не должен попадать в Git, чат или
логи. Приглашения действуют три дня; просроченные нужно перевыпустить. Пароли и
коды в снапшот намеренно не включены.

Runbook:

```text
INVITE_REGISTRATION.md
DB_ACCOUNTS_MIGRATION.md
```

## 11. Профили и модерация исполнителя

У логиста:

- Telegram удалён;
- Email необязателен;
- города/районы необязательны;
- обязательным для completion остаётся `display_name`.

У исполнителя:

- Email удалён из формы;
- города обязательны, потому что управляют выдачей заказов;
- доступны признаки ремней и инструментов;
- поток паспорт/НПД-модерации реализован, но до закрытия правовых P0 разрешены
  только синтетические данные и документы.

Приватные файлы исполнителя должны храниться вне web root по пути из
`GPM_APP_PRIVATE_UPLOAD_DIR`, а не в PostgreSQL, Git или Flutter assets.

Подробности:

```text
WORKER_PROFILE_VERIFICATION.md
```

## 12. Чаты, назначения и финансы

Profiles, dashboards, chats, applications и assignments работают через
серверный backend и PostgreSQL. Доступ ограничивается ролью и ownership.

Финансы исполнителя — расчёт начислений по завершённым заказам, а не платёжный
ledger. Реальные платежи, эквайринг, ККТ и автоматические выплаты не включены.

## 13. Дизайн

`DESIGN_FREEZE.md` действует.

Без отдельного согласования нельзя менять:

- палитру;
- типографику;
- навигацию;
- общую компоновку;
- карточки, кнопки и поля;
- утверждённый вид кабинетов трёх ролей.

Разрешены только функциональные состояния в существующем визуальном языке.

## 14. Безопасность и правовые ограничения

Проект пока не готов к реальному публичному пилоту. Основные незакрытые области:

- оператор ПДн и юридические реквизиты;
- политика, основания, согласия и версии документов;
- уведомление РКН и подтверждение локализации;
- contact verification и password recovery;
- полный RBAC-аудит и администрирование доступа;
- права субъекта, удаление и retention;
- регламент backup/restore и проверенный restore drill;
- договорная модель, оферта, платежи и НПД;
- оценка ОРИ для реальных межпользовательских чатов;
- проверка исторических логов и возможного прежнего доступа.

Нельзя включать реальные паспортные данные, платежи, legacy Telegram и внешние
передачи адресов до отдельной технической и правовой готовности.

Главные документы:

```text
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
SECRET_ROTATION.md
PRODUCTION_READINESS.md
```

## 15. Конфигурация и secrets

В репозитории разрешены только placeholders и публичные frontend-настройки.

Production frontend asset содержит только:

```text
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Нельзя печатать или коммитить:

- `GPM_APP_API_TOKEN`;
- JWT secret;
- пароли, хеши и session tokens;
- populated server env;
- GitHub OAuth token;
- SSH private key;
- invitation codes;
- реальные персональные данные.

Реальные backend-переменные находятся в закрытом server environment. В Git их
не переносить. Исторические secrets из `SECRET_ROTATION.md` должны считаться
подлежащими отзыву/ротации.

## 16. Инфраструктура и деплой

Репозиторий:

```text
https://github.com/tonimasite-dotcom/gpm_platform
```

Backend:

```text
host:     46.149.71.147
checkout: /opt/gpm/gpm_platform
service:  gpm-app-api.service
backups:  /opt/gpm/backups
```

Frontend:

```text
host:     186.246.10.163
live:     /var/www/gpm-app
backups:  /opt/gpm/front-backups
```

Проверенный backend ED25519 fingerprint:

```text
SHA256:dAcCgb8rkH+GkWoW+92d7xR8QEwVVyASs2OrdHbBDHc
```

Защищённый локальный deploy key:

```text
C:\tmp\gpm-production-github-actions
```

Не читать и не печатать его содержимое.

Production workflow:

```text
.github/workflows/deploy-production.yml
```

Он запускается вручную только с `main`; варианты `all`, `backend`, `frontend`.
Перед обновлением backend делает Git bundle и versioned venv; frontend
переключается атомарно с rollback. Workflow не создаёт дамп PostgreSQL: перед
схемными или рискованными изменениями дамп нужно делать отдельно и проверять
через `pg_restore --list`.

Если `gh` недоступен, workflow можно запустить GitHub REST API, безопасно взяв
OAuth-токен через `git credential fill` и не выводя значение. HTTP `204`
означает, что dispatch принят.

Перед каждым production-деплоем:

1. назвать точный commit и компоненты;
2. получить явное подтверждение владельца;
3. проверить чистый `main` и совпадение с origin;
4. дождаться CI;
5. после деплоя проверить health/frontend/config и нужные permission-сценарии.

Полный runbook:

```text
PRODUCTION_DEPLOYMENT.md
```

## 17. CI, demo и локальный запуск

Workflows:

```text
.github/workflows/ci.yml
.github/workflows/deploy-demo.yml
.github/workflows/deploy-production.yml
```

Demo:

```text
https://tonimasite-dotcom.github.io/gpm_platform/
```

Он использует demo mode и не является production.

Основные локальные команды:

```powershell
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
python -m unittest discover -s tests -p "test_*.py" -v
```

Версии/ограничения:

```text
Flutter: 3.38.5
Dart SDK constraint: ^3.8.0
Python: >=3.10
FastAPI production dependencies: requirements-api.lock
```

Локальный Chrome против production API запускать строго на порту `8090`:

```powershell
flutter run -d chrome --web-port=8090
```

Иначе запросы блокируются CORS. На Windows web release build нужно выполнять в
ASCII-пути: Flutter impellerc может падать из-за кириллицы в текущем пути. CI на
Linux является авторитетной release-проверкой.

Legacy `requirements.txt` содержит устаревшие зависимости и не используется
production API. Не включать legacy-бот без отдельной модернизации зависимостей.

## 18. Карта ключевых файлов

```text
README.md                                      краткое состояние проекта
app/app_orders_api.py                         активный FastAPI API
lib/main.dart                                 активная Flutter-точка входа
lib/services/gpm_api_service.dart             Flutter API-клиент
lib/screens/**                                активные экраны ролей
tests/test_app_orders_api.py                  backend regression/permission tests
test/**                                       Flutter unit/widget tests
CRM_APP_PUBLICATION.md                        контракт CRM и публикации
INDEPENDENT_PLATFORM_ARCHITECTURE.md          архитектурные ограничения
DESIGN_FREEZE.md                              заморозка дизайна
PRODUCTION_DEPLOYMENT.md                      production runbook
DB_ACCOUNTS_MIGRATION.md                      аккаунты/сессии/audit
INVITE_REGISTRATION.md                        закрытая регистрация
WORKER_PROFILE_VERIFICATION.md                профиль и модерация исполнителя
PROJECT_AUDIT_2026-08-25.md                   технические P0
LEGAL_READINESS_RU.md                         правовые P0
SECRET_ROTATION.md                            правила ротации secrets
NEW_DEVICE_SETUP_2026-08-26.md                настройка новой рабочей машины
```

Более старые `PROJECT_HANDOFF_*` и `CONTINUE_PROJECT_PROMPT_*` — история. Для
нового чата использовать именно этот полный снапшот и соответствующий промпт.

## 19. Что не потерять в следующем чате

- Текущая незавершённая задача — только релиз и проверка editor-фичи.
- `main`/production не содержат `b3f85df`.
- Для editor нужен production deploy `target=all`.
- CRM-заявку может публиковать только назначенный логист GPM.
- Другие логисты работают через приложение и не получают CRM-доступ.
- Старую `033/25` нельзя использовать для проверки редактирования.
- Регистрация логистов отложена.
- Адрес исполнителю до назначения скрыт намеренно.
- Города исполнителя обязательны; города логиста необязательны.
- Не менять дизайн и не включать Telegram.
- Не использовать реальные данные.
- Не деплоить без отдельного подтверждения.

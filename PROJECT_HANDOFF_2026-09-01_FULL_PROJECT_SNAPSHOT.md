# GPM Platform: полный снапшот проекта и точка продолжения

Дата: 01.09.2026. Часовой пояс: Europe/Moscow.

Этот файл — главный и актуальный источник истины для следующего чата. Он
заменяет предыдущий полный снапшот от 31 августа в роли стартового документа,
но не удаляет старые handoff-файлы: они остаются историей решений и релизов.

Стартовый промпт нового чата:

```text
CONTINUE_PROJECT_PROMPT_2026-09-01_FULL_PROJECT_SNAPSHOT.md
```

Подробный журнал последнего релиза и CRM-проверки:

```text
PROJECT_HANDOFF_2026-09-01_EDITOR_RELEASE_AND_CRM_VALIDATION.md
```

## 1. Главная точка продолжения

Редактор черновика перед публикацией уже выпущен в production. Функциональный
коммит `b3f85df` вошёл в `main`; production backend и frontend развёрнуты из
`3f857c5` через успешный workflow `Deploy production` run #11 с `target=all`.

После релиза подтверждены:

- backend health: `status=ok`, `storage=postgres`;
- production frontend: HTTP 200;
- публичный frontend `.env`: только production mode и публичный API URL;
- CI, demo, frontend build/test и backend test/validation;
- атомарный frontend deploy и backend deploy;
- отправка новой синтетической CRM-заявки `001/26` в GPM после исправления
  некорректно заполненного поля CRM.

Текущая незавершённая задача — ручная ролевая проверка уже созданного нового
CRM-черновика `001/26` внутри GPM:

1. назначенный логист открывает заявку в «На модерации»;
2. меняет одно-два рабочих поля через новый editor и сохраняет;
3. повторно открывает заявку и проверяет сохранённые значения;
4. другой логист не должен видеть или редактировать заявку;
5. назначенный логист публикует заявку;
6. после публикации editor исчезает, а прямой PATCH рабочих полей получает
   `409`;
7. исполнитель с городом Москва видит опубликованный заказ без точного адреса;
8. исполнитель другого города заказ не видит;
9. отдельно желательно повторить draft → edit → publish под частным логистом и
   клиентом.

Не создавать новую feature и не делать новый production deploy для этой
проверки: нужный код уже в production.

## 2. Git

Состояние непосредственно перед созданием этого снапшота:

```text
current branch: main
HEAD:           3f857c53d6e39c0edb733c4c316e5d0b860d7f7a
main:           3f857c53d6e39c0edb733c4c316e5d0b860d7f7a
origin/main:    3f857c53d6e39c0edb733c4c316e5d0b860d7f7a
working tree:   clean
```

Коммит, содержащий этот снапшот, журнал, новый промпт и обновлённый README,
будет следующим документационным коммитом `main`. Его точный SHA нужно брать из
`git log -1`. Этот документационный коммит не требует production-деплоя;
production-код остаётся `3f857c5`.

Основная цепочка функциональных релизов:

```text
411561b Remove Telegram field, make email/cities optional for logist profile
935649c Restore CRM order publication by logist
8de928f Enforce order ownership and city visibility
e8c4432 Handle CRM order numbers containing slashes
7024d76 Infer CRM order city from address
b3f85df Allow order owners to edit drafts before publishing
800fe98 Add August 31 CRM and draft editor handoff
3f857c5 Add complete August 31 project snapshot          <- production code
```

Ветка `feature/edit-order-drafts` сохранена в origin и также указывает на
`3f857c5`, но продолжать работу нужно от актуального `main`.

Не повторять cherry-pick старых CRM-веток: их функциональные коммиты уже входят
в `main`.

## 3. Production

Публичные адреса:

```text
frontend: https://app.gpmbot.ru/
backend:  https://app-api.gpmbot.ru/
health:   https://app-api.gpmbot.ru/health
```

Текущая версия обоих компонентов:

```text
production backend:  3f857c5
production frontend: 3f857c5
```

Релиз редактора:

```text
Deploy production run #11
target:     all
head SHA:   3f857c53d6e39c0edb733c4c316e5d0b860d7f7a
conclusion: success
run:        33439488044
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33439488044
```

В run #11 успешно завершились:

- checkout `main`;
- Flutter setup;
- создание публичной production-конфигурации;
- frontend analyze/test/release build;
- backend dependency audit/compile/tests;
- verified SSH setup;
- backend deploy;
- upload frontend artifact;
- атомарный frontend deploy;
- встроенные health/frontend проверки.

Post-deploy вручную подтверждено:

```text
/health                  -> {"status":"ok","storage":"postgres"}
frontend                 -> HTTP 200
frontend assets/.env     -> GPM_APP_MODE=production
                            GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Production разрешён только для закрытого тестирования на синтетических данных.
Реальные персональные, паспортные, банковские данные, адреса и переписку
использовать нельзя до закрытия P0.

## 4. CI и demo релиза

Функциональный CI editor-коммита:

```text
run:        33382173657
head SHA:   b3f85dfce970e073e2ae8f4aae904443afbdc24e
conclusion: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33382173657
```

CI полного релизного SHA:

```text
run:        33399321365
head SHA:   3f857c53d6e39c0edb733c4c316e5d0b860d7f7a
conclusion: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33399321365
```

Demo после обновления `main`:

```text
run:        33438500662
head SHA:   3f857c53d6e39c0edb733c4c316e5d0b860d7f7a
conclusion: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33438500662
```

Локально перед merge редактора:

```text
Flutter tests:   7 passed
Flutter analyze: No issues found
```

Локальные backend-тесты на этой Windows-машине не стартовали из-за отсутствия
пакета `fastapi` в глобальном Python. Это проблема локального окружения, а не
кода; backend tests успешно прошли в CI и production workflow.

## 5. Активная архитектура

```text
CRM -> server-to-server GPM API -> PostgreSQL -> Flutter web/Android
```

Активные компоненты:

```text
Flutter entrypoint: lib/main.dart
Flutter screens:    lib/screens/**
Flutter API client: lib/services/gpm_api_service.dart
FastAPI backend:    app/app_orders_api.py
Production command: uvicorn app.app_orders_api:app
Database:           PostgreSQL
```

Legacy Telegram-контур (`main.py`, `app/handlers/**`, `app/services/**`) не
является частью активного production-потока. Его нельзя включать как резервный
канал. GPM должна работать независимо от Telegram, MAX, других мессенджеров и
социальных сетей.

Bitrix24/CRM — только внешний источник заказов. Источник истины по состоянию
заказа, ownership, назначениям, откликам и чатам — backend GPM и PostgreSQL.

Основные архитектурные документы:

```text
INDEPENDENT_PLATFORM_ARCHITECTURE.md
CRM_APP_PUBLICATION.md
BITRIX24_INTEGRATION.md
```

## 6. Роли и права

### Клиент

- видит только собственные заказы;
- создаёт заявку как `NEW`-черновик;
- меняет рабочие поля только собственного `NEW`;
- публикует собственный черновик;
- не видит CRM-заявки и чужие заказы;
- управляет откликами, назначением и завершением только своего заказа.

### Исполнитель

- видит только `PROCESSED`-заказы подходящего города;
- не видит точный адрес и чувствительные контакты до назначения;
- не редактирует черновики;
- откликается только при совпадении города;
- после назначения получает адрес и работает со своим назначением.

### Назначенный CRM-логист GPM

- CRM передаёт его `logist_phone`;
- backend разрешает телефон ровно в один активный серверный аккаунт;
- заказ закрепляется через `logist_account_id`;
- только этот логист видит CRM-черновик;
- только он меняет рабочие поля `NEW` и публикует заявку;
- CRM-номер, источник и назначение через editor не меняются.

### Другой или частный логист

- не видит чужие CRM-заявки;
- не может редактировать или публиковать их;
- создаёт собственные заявки через приложение;
- использует тот же поток `NEW` → edit → publish для своих заказов.

Отдельной сущности `company` в модели аккаунтов пока нет. Доступ к CRM-заказу
обеспечивается строгой привязкой телефона к `logist_account_id`. Явное company
membership — отдельная будущая задача, если понадобится.

## 7. Жизненный цикл заказа

Основные серверные статусы:

```text
NEW          черновик / на модерации
PROCESSED    опубликован
JUNK         отклонён
IN_PROCESS   в работе
DONE_PENDING ждёт подтверждения завершения
CONVERTED    завершён
```

В старых документах и отдельных UI могут встречаться `IN_PROGRESS`/`DONE`.
Перед рефакторингом state machine нужно отдельно согласовать единый словарь.

Правила:

- CRM создаёт или обновляет серверный черновик;
- повторный импорт не стирает workflow, назначения и отклики;
- редактирование рабочих полей допустимо только в `NEW`;
- публикация переводит `NEW` в `PROCESSED`;
- editor опубликованного заказа недоступен;
- прямой PATCH рабочих полей опубликованного заказа возвращает `409`;
- CRM-номера со слешем поддерживаются маршрутами `{order_id:path}`.

## 8. Редактор черновика — уже в production

Функциональный коммит:

```text
b3f85dfce970e073e2ae8f4aae904443afbdc24e
```

Основные изменённые файлы:

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

Редактируемые рабочие поля:

- название и описание;
- город, дата/время, адрес и метро;
- количество работников и часы;
- гражданство и режим работы;
- описание смены и минимальное время;
- ставки/цены;
- дополнительная информация.

Системные поля защищены. Смена адреса очищает старые координаты. Дата должна
содержать timezone, быть минимум через 30 минут и не дальше 366 дней. Успешное
изменение пишет audit-событие `order_draft_updated`.

## 9. CRM ownership и город

CRM обязана передавать:

```text
logist_phone
order_data.order_number
order_data.completion_date.date
order_data.loaders.loader_count
order_data.info
```

Также текущий контракт проверяет:

```text
order_data.hours     integer 1..24
order_data.min_time  integer 1..24
loader_count         integer 1..100
```

Неизвестный, пустой или неоднозначный `logist_phone` отклоняется. Общей очереди
CRM-заказов для всех логистов нет.

Если отдельное поле города пусто, backend безопасно пытается определить город
из первой части адреса, например `г Москва, ...`.

## 10. CRM-проверка 1 сентября и найденная ошибка данных

Для проверки editor создана новая синтетическая CRM-заявка:

```text
order number: 001/26
CRM order id: 56793
city/address: Москва, синтетические тестовые данные
workers:      2
```

Первая отправка из CRM завершалась общим сообщением «Не удалось опубликовать в
приложении». Диагностика выполнена read-only через сохранённую MobaXterm-сессию
CRM-сервера.

Laravel-log показал фактический ответ GPM:

```text
HTTP 400
order_data.hours must be between 1 and 24
```

После проверки записи CRM было установлено:

```text
duration:         4
min_time:         600          <- ошибочное значение
loader_count:     2
completion_date:  2026-09-03 11:30:00 в БД / 14:30 Europe/Moscow
city:             отдельное поле пусто
address:          заполнен
```

CRM publisher сопоставляет поля так:

```php
'min_time' => (int) ($order->min_time ?? $order->duration ?? 4),
'hours'    => (int) ($order->duration ?? $order->min_time ?? 4),
```

В CRM `min_time` — это минимальное количество часов, хотя русский label
«Минимальный заказ» допускает ошибочное толкование. Значение `600` было ставкой,
ошибочно введённой в поле часов. Из-за него CRM показывала минимальную сумму:

```text
600 рублей × 2 исполнителя × 600 часов = 720 000 рублей
```

Правильное заполнение:

```text
duration:     4 часа
min_time:     4 часа
workers_cost: 600 рублей/час
loader_count: 2
minimum cost: 600 × 2 × 4 = 4 800 рублей
```

После исправления `min_time` пользователь повторил отправку и подтвердил, что
проблема решена. Серверный код для этой ошибки менять не потребовалось.

Важно: значение после исправления не перепроверялось отдельным DB-запросом;
подтверждён пользовательский успешный результат отправки. В новом чате не
возвращаться к диагностике, если заявка `001/26` присутствует в GPM.

## 11. CRM-сервер: безопасная карта диагностики

Это внешняя CRM, а не GPM production backend.

```text
domains:  ts.workstaffcrm.ru, test.workstaffcrm.ru
IPv4:     5.183.191.222
OS:       Debian 10
panel:    FASTPANEL
runtime:  nginx + FASTPANEL PHP 7.4 FPM
MobaXterm saved session: 5.183.191.222 (root)
```

Активный test/ts web-root:

```text
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru
```

Ключевые CRM-файлы интеграции:

```text
app/Services/Order/GpmAppOrderPublisher.php
app/Http/Controllers/Order/ManagerOrderController.php
resources/js/pages/app/orders/logist_orders/index.vue
storage/logs/laravel-YYYY-MM-DD.log
```

Nginx-конфигурация:

```text
/etc/nginx/fastpanel2-sites/gruzpiter/ts.workstaffcrm.ru.conf
```

Controller превращает подробную ошибку publisher в общий HTTP 500 для UI, а
Vue `.catch()` показывает только общий toast. Фактический GPM status/body пишет
`GpmAppOrderPublisher` в Laravel warning-log. Возможное будущее улучшение —
безопасно возвращать оператору нормализованное описание ошибки валидации без
секретов и внутренних деталей. Это не реализовано и требует отдельного запроса.

Никогда не выводить `.env`, integration token, Authorization headers, passwords
или полный payload с персональными данными. Для диагностики читать только
нормализованные status/detail и синтетические поля.

## 12. Точная следующая ручная проверка

Использовать уже отправленную заявку `001/26`.

1. Войти в `https://app.gpmbot.ru/` назначенным логистом.
2. Открыть «На модерации» и найти `001/26`.
3. Убедиться, что дата, 2 исполнителя, Москва и ставка отображаются ожидаемо.
4. Открыть editor.
5. Изменить безопасное поле, например описание или ставку, и сохранить.
6. Переоткрыть editor и проверить сохранённое значение.
7. Войти другим логистом: `001/26` не должна быть видна.
8. Вернуться назначенным логистом и опубликовать заявку.
9. Убедиться, что editor исчез и статус стал опубликованным.
10. Под исполнителем с городом Москва проверить наличие заказа и отсутствие
    точного адреса до назначения.
11. Под исполнителем другого города убедиться, что заказа нет.
12. При возможности проверить собственные черновики частного логиста и клиента.

Если `001/26` не появилась в GPM, сначала проверить свежую запись Laravel-log и
получить только `status`/`detail`; не менять backend вслепую.

## 13. Аккаунты и закрытая регистрация

Авторизация использует PostgreSQL-таблицы аккаунтов, сессий, аудита и
одноразовых приглашений. Пароли хешируются versioned scrypt. JWT содержит
account/session IDs и проверяется сервером. После пяти ошибок вход блокируется
на 15 минут. Logout отзывает серверную сессию.

Публичная регистрация закрыта. Роль и username задаются одноразовым
приглашением. Регистрация логистов как отдельная продуктовая задача отложена.

Исторический временный QA-комплект:

```text
safe name: qa-b-20260831
protected backend file: /root/gpm-app-invitations-qa-b-20260831.json
```

Файл содержит secrets, имеет mode 600 и не должен попадать в Git, чат или логи.
Приглашения были выпущены на три дня и могут истечь. При необходимости создавать
новый комплект по `INVITE_REGISTRATION.md`, не печатая коды.

## 14. Профили и модерация

Логист:

- Telegram удалён;
- email необязателен;
- города/районы необязательны;
- обязательным для completion остаётся `display_name`.

Исполнитель:

- email удалён из формы;
- города обязательны для фильтрации заказов;
- доступны признаки ремней и инструментов;
- паспорт/НПД-поток реализован, но разрешены только синтетические документы.

Приватные вложения исполнителя должны храниться вне web root в
`GPM_APP_PRIVATE_UPLOAD_DIR`, не в Git, Flutter assets или публичном каталоге.

Документ:

```text
WORKER_PROFILE_VERIFICATION.md
```

## 15. Чаты, назначения и финансы

Profiles, dashboards, chats, applications и assignments работают через FastAPI
и PostgreSQL. Доступ ограничивается ролью и ownership.

Финансы исполнителя — расчёт начислений по завершённым заказам, а не платёжный
ledger. Реальные платежи, эквайринг, ККТ и автоматические выплаты не включены.

## 16. Дизайн

`DESIGN_FREEZE.md` действует.

Без отдельного согласования нельзя менять:

- палитру и типографику;
- навигацию и общую компоновку;
- карточки, кнопки и поля;
- утверждённые кабинеты клиента, исполнителя и логиста.

Разрешены функциональные состояния в существующем визуальном языке.

## 17. Безопасность и правовые ограничения

Проект не готов к реальному публичному пилоту. Основные незакрытые области:

- оператор ПДн и юридические реквизиты;
- политика, основания, согласия и версии документов;
- уведомление РКН и подтверждение локализации;
- contact verification и password recovery;
- полный RBAC-аудит и администрирование;
- права субъекта, удаление и retention;
- backup/restore drill;
- договорная модель, оферта, платежи и НПД;
- оценка ОРИ для межпользовательских чатов;
- проверка исторических логов и прежнего доступа.

Нельзя включать реальные паспортные данные, реальные платежи, legacy Telegram
или внешние передачи адресов до отдельной технической и правовой готовности.

Главные документы:

```text
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
SECRET_ROTATION.md
PRODUCTION_READINESS.md
```

## 18. Secrets и конфигурация

В репозитории разрешены только placeholders и публичные frontend-настройки.

Production frontend asset содержит только:

```text
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Нельзя печатать или коммитить:

- `GPM_APP_API_TOKEN`;
- JWT secret;
- populated server env;
- пароли, password hashes и session tokens;
- GitHub OAuth token;
- SSH private keys;
- invitation codes;
- реальные персональные данные.

Исторические secrets из `SECRET_ROTATION.md` считать подлежащими ротации.

## 19. GPM-инфраструктура и деплой

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

Production workflow:

```text
.github/workflows/deploy-production.yml
```

Он запускается вручную только с `main`; targets: `all`, `backend`, `frontend`.
Перед backend deploy создаётся Git bundle и versioned venv. Frontend меняется
атомарно с backup/rollback. Workflow не создаёт PostgreSQL dump.

Локальный deploy key, упомянутый в старом handoff как
`C:\tmp\gpm-production-github-actions`, на текущей Windows-машине отсутствует.
Это не помешало GitHub Actions deploy, потому что workflow использует GitHub
Secrets. Не пытаться извлекать ключи из MobaXterm или GitHub Secrets.

Перед каждым новым production-деплоем:

1. назвать точный commit и компоненты;
2. получить отдельное явное подтверждение владельца;
3. проверить чистый `main` и совпадение с origin;
4. дождаться CI/demo;
5. после deploy проверить health/frontend/config и permission-сценарии.

Полный runbook:

```text
PRODUCTION_DEPLOYMENT.md
```

## 20. Локальная разработка

Версии:

```text
Flutter: 3.38.5
Dart SDK constraint: ^3.8.0
Python: >=3.10
FastAPI production dependencies: requirements-api.lock
```

Основные проверки:

```powershell
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
python -m pip install -r requirements-api.lock
python -m unittest discover -s tests -p "test_*.py" -v
```

Локальный Chrome против production API запускать только на порту `8090`:

```powershell
flutter run -d chrome --web-port=8090
```

На Windows web release build желательно выполнять в ASCII-пути. CI на Linux —
авторитетная release-проверка.

Legacy `requirements.txt` не является production dependency set для FastAPI.

## 21. Карта ключевых файлов

```text
README.md                                      краткий актуальный статус
app/app_orders_api.py                         активный FastAPI API
lib/main.dart                                 Flutter entrypoint
lib/services/gpm_api_service.dart             Flutter API client
lib/screens/orders/order_draft_edit_screen.dart editor черновика
lib/screens/**                                активные экраны ролей
tests/test_app_orders_api.py                  backend permission/regression tests
test/**                                       Flutter unit/widget tests
CRM_APP_PUBLICATION.md                        контракт CRM
INDEPENDENT_PLATFORM_ARCHITECTURE.md          архитектурные ограничения
DESIGN_FREEZE.md                              заморозка дизайна
PRODUCTION_DEPLOYMENT.md                      production runbook
DB_ACCOUNTS_MIGRATION.md                      accounts/sessions/audit
INVITE_REGISTRATION.md                        закрытая регистрация
WORKER_PROFILE_VERIFICATION.md                профиль/модерация исполнителя
PROJECT_AUDIT_2026-08-25.md                   технические P0
LEGAL_READINESS_RU.md                         правовые P0
SECRET_ROTATION.md                            ротация secrets
NEW_DEVICE_SETUP_2026-08-26.md                настройка новой машины
```

## 22. Что не потерять в следующем чате

- Editor уже в `main` и production; не релизить его повторно.
- Production backend и frontend: `3f857c5`.
- Следующий commit после `3f857c5` — только новый документационный снапшот.
- CRM-заявка `001/26` успешно отправлена после исправления `min_time`.
- Точка остановки — ручная проверка editor и ролей внутри GPM.
- Не использовать старую `033/25` для editor: она уже опубликована.
- `min_time` в CRM означает часы, а не ставку и не сумму.
- Допустимы `hours/min_time` от 1 до 24, loader count от 1 до 100.
- CRM UI скрывает backend detail; фактическая ошибка есть в Laravel warning-log.
- CRM ownership доступен только назначенному логисту по `logist_account_id`.
- Другой логист не видит CRM-заказ.
- Исполнитель фильтруется по городу; адрес скрыт до назначения.
- Регистрация логистов отложена.
- Не менять дизайн и не включать Telegram.
- Использовать только синтетические данные.
- Не печатать secrets и не деплоить без отдельного подтверждения.

## 23. Первый порядок действий нового чата

1. Полностью прочитать этот файл.
2. Прочитать
   `PROJECT_HANDOFF_2026-09-01_EDITOR_RELEASE_AND_CRM_VALIDATION.md`.
3. Выполнить только read-only проверку:

```text
git status --short --branch
git log --oneline --decorate -10
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
```

4. Кратко назвать фактический HEAD, production `3f857c5` и незавершённый ручной
   тест `001/26`.
5. Дождаться результата пользователя: видна ли `001/26` назначенному логисту.
6. Не начинать новую feature и не деплоить без нового явного запроса.

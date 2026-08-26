# Полный handoff GPM после production-публикации

> **Исторический снимок.** Актуальная точка продолжения:
> `PROJECT_HANDOFF_2026-08-26_ROLE_WORKSPACES.md`.

Дата снимка: 25.08.2026, часовой пояс Europe/Moscow.

Это главный источник истины для продолжения проекта после инженерного аудита,
исправлений безопасности и публикации frontend/backend. Старые handoff-файлы
нужны только для истории. Читать этот документ вместе с:

- `CONTINUE_PROJECT_PROMPT_2026-08-25_PRODUCTION.md`;
- `PROJECT_AUDIT_2026-08-25.md`;
- `LEGAL_READINESS_RU.md`;
- `README.md`;
- `PRODUCTION_DEPLOYMENT.md`.

## 1. Точка остановки

Проект опубликован и технически работает в production, но разрешённый режим
пока только закрытое тестирование на полностью вымышленных данных.

Публичные адреса:

- приложение: https://app.gpmbot.ru/;
- API: https://app-api.gpmbot.ru/;
- health-check: https://app-api.gpmbot.ru/health;
- GitHub: https://github.com/tonimasite-dotcom/gpm_platform.

Опубликованный код frontend и backend:

```text
efec81f2711c9a02b67dda7b25e28966ccb31dd9
```

Коммит: `Validate production runtime before service switch`.

До добавления этого документа локальный `main`, `origin/main` и production-код
совпадали на `efec81f`, а tracked working tree был чистым. Коммит со снапшотом
будет документационным потомком `efec81f`; из-за одних документов повторно
публиковать production не требуется. В новом чате нужно отдельно показать:

1. текущий HEAD `main` и `origin/main`;
2. production release SHA `efec81f`;
3. являются ли последующие коммиты только документацией.

## 2. Что выполнено 25.08.2026

Проведён полный инженерный аудит проекта, логики, UX, зависимостей,
production-процесса и правовой готовности к использованию в РФ. Основной пакет
исправлений зафиксирован в `691e479`, защита CI/deploy — в `c88d8e4`, финальная
runtime-проверка — в `efec81f`.

В production опубликованы следующие изменения:

- общая публичная пара `admin/admin` удалена и больше не проходит вход;
- созданы три отдельные переходные серверные учётные записи с ролями `client`,
  `worker`, `logist` и разными случайными 48-символьными паролями;
- роль назначается backend, а не принимается на доверии от интерфейса;
- клиент видит только свои заказы, исполнитель до назначения не получает точный
  адрес, координаты, владельца и контакты;
- ручной заказ клиента в API-режиме сохраняется на backend;
- импорт не должен затирать workflow-state; новые заказы не сохраняют полный
  `source_payload`;
- публичные PATCH/POST ограничены, обновления заказов атомарны;
- production требует PostgreSQL, явный CORS, безопасные API/JWT secrets и
  настроенную серверную учётную запись;
- JWT ограничен ожидаемым алгоритмом и минимальной длиной секрета;
- health-check выполняет реальный запрос к БД;
- синхронные DB-операции вынесены из async event loop;
- Flutter получил сетевые timeout, безопасные сообщения об ошибках и возврат к
  входу при отказе сессии;
- публичные тестовые реквизиты и заранее заполненный логин убраны из UI;
- функции, которые всё ещё локальные или фиктивные, честно отключены в API-режиме;
- немецкая внешняя карта с передачей координат отключена;
- исправлены web/PWA metadata, Android INTERNET, контраст, форма заказа и
  нейтральное требование права на работу;
- legacy Telegram-бот заблокирован по умолчанию явным opt-in;
- добавлены backend- и widget-тесты, CI и Dependabot;
- GitHub Actions закреплены на полных SHA, runner — Ubuntu 24.04;
- FastAPI/Starlette/Uvicorn/PyYAML/psycopg2 обновлены и зафиксированы lock-файлом;
- production backend использует версионированный virtualenv с атомарным
  переключением и откатом;
- CORS разрешает точные локальные origin `http://localhost:8090` и
  `http://127.0.0.1:8090`, но не произвольные сайты.

Полный технический перечень и границы исправлений находятся в
`PROJECT_AUDIT_2026-08-25.md`.

## 3. Данные и учётные записи

Перед публикацией выполнен согласованный сброс тестовых заказов:

```text
orders_deleted=0
orders_remaining=0
```

На момент очистки активная таблица `gpm_app_orders` уже была пустой. Таблицы
`crm_app_orders` в production не было. Перед операцией создан проверяемый custom
dump PostgreSQL и копия прежнего env.

Переходные production-логины:

| Роль | Username | Пароль |
|---|---|---|
| Клиент | `client` | только в закрытом хранилище |
| Исполнитель | `worker` | только в закрытом хранилище |
| Логист | `logist` | только в закрытом хранилище |

Пароли нельзя добавлять в Git, handoff, чат, Flutter `.env`, логи или скриншоты.
На сервере они находятся в `/root/gpm-app-env`, а удобная закрытая копия — в
`/root/gpm-app-login.txt`; оба файла должны оставаться `root:root`, mode `600`.
В конце публикации содержимое login-файла было безопасно помещено в локальный
буфер обмена без вывода в журнал. Если буфер потерян, получать реквизиты заново
можно только с явного разрешения владельца и снова напрямую в защищённое
хранилище/буфер, не в ответ чата.

Это временные конфигурационные accounts для закрытого тестирования, а не готовая
регистрация пользователей. Следующая полноценная модель должна хранить accounts
в БД с уникальными пользователями, хешами паролей, восстановлением, блокировкой,
revocation и audit trail.

## 4. Production-инфраструктура

### Backend

```text
Host: 46.149.71.147
Hostname: msk-1-vm-smqt
SSH user deployment: root
Repository: /opt/gpm/gpm_platform
Service: gpm-app-api.service
EnvironmentFile: /root/gpm-app-env
ExecStart: /opt/gpm/gpm_platform/.venv/bin/uvicorn
Active venv target: /opt/gpm/venvs/gpm-app-efec81f2711c9a02b67dda7b25e28966ccb31dd9
Database: PostgreSQL
```

Проверенные версии production:

```text
Python 3.12.3
FastAPI 0.141.1
Starlette 1.6.0
Uvicorn 0.52.4
PyYAML 6.0.3
psycopg2-binary 2.9.12
```

Backend service активен, tracked server checkout чистый, публичный health
возвращает `{"status":"ok","storage":"postgres"}`.

### Frontend

```text
Host: 186.246.10.163
Hostname: gpm-app-prod
SSH user deployment: root
Web root: /var/www/gpm-app
Nginx: active, config test successful
```

SHA-256 `main.dart.js`, совпавший у локального release-артефакта, live-файла и
публичной HTTPS-выдачи:

```text
d091f8b764ba1be1c6dd994170b735a90c1fc0060c0af7eee0a7afc134973805
```

Публичный Flutter asset содержит только:

```text
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Никаких секретов во frontend build нет. Локальная игнорируемая `.env` после
сборки возвращена в режим `api` с тем же URL API.

## 5. Резервные копии последней публикации

Не удалять без отдельного подтверждения владельца и проверки retention/legal
hold:

```text
Database + env before account migration:
/root/gpm-private-backups/20260825_134724

Backend repository + previous venv:
/opt/gpm/backups/20260825_135138

Private backend config before deploy:
/root/gpm-private-backups/20260825_135138

Frontend backup:
/opt/gpm/front-backups/20260825_140152

Previous frontend directory:
/var/www/gpm-app-previous-20260825_140152
```

В backend backup сохранены Git bundle, прежний SHA `e595d15` и прежний
virtualenv. Private backup `20260825_134724` содержит dump таблицы заказов и env
до миграции accounts.

## 6. Проверки последнего релиза

- GitHub Actions CI run `32854996567` для `c88d8e4`: `backend` и `flutter`
  успешно;
- backend unit/API tests на точном production-коде: **14/14**;
- Flutter widget tests на точном production-коде: **2/2**;
- `flutter analyze --no-pub`: **No issues found**;
- Flutter web release build: успешно в ASCII-пути Windows;
- `pip check`: успешно;
- dependency audit обновлённого API lock: известных уязвимостей нет;
- production runtime configuration: успешно;
- публичный frontend: HTTP `200`;
- публичный health: HTTP `200`, PostgreSQL `ok`;
- внешние HTTPS-входы `client`, `worker`, `logist`: успешно;
- внешний вход `admin/admin`: HTTP `401`, отклонён;
- CORS preflight с обоих origin `localhost:8090`: HTTP `200` и точный
  `Access-Control-Allow-Origin`;
- CORS с `https://example.com`: HTTP `400`, allow-origin отсутствует;
- nginx test: успешно;
- локальный `main` и `origin/main` перед снапшотом: `efec81f`, working tree чистый.

Flutter shader compiler на Windows не записывает shader-файлы в рабочий путь с
кириллицей. Проверенный workaround: распаковать чистый `git archive` в короткий
ASCII-путь под `C:\tmp`, создать там только публичную production `.env`, провести
анализ/тесты/build и после публикации удалить временные файлы. В Linux CI эта
проблема не воспроизводится.

## 7. Git и штатная публикация

Основная ветка — `main`. Production workflow:

```text
.github/workflows/deploy-production.yml
```

Штатный следующий деплой:

```text
GitHub -> Actions -> Deploy production -> Run workflow -> all
```

Workflow допускает `all`, `backend`, `frontend`, разрешает production только из
`main`, выполняет тесты, dependency audit, проверенный SSH, backend rollback,
versioned venv и атомарный frontend switch.

GitHub environment `production` уже содержит secrets:

```text
PROD_SSH_PRIVATE_KEY
PROD_SSH_KNOWN_HOSTS
```

Значения secrets никогда не записывать в документы. Локальная deploy-пара ключей
и временные known_hosts тоже не удаляются/не читаются без необходимости и
отдельного подтверждения точных путей.

Последний релиз `efec81f` был опубликован напрямую по SSH тем же безопасным
алгоритмом после успешного CI, потому что `gh` отсутствовал, а анонимный GitHub
API исчерпал rate limit. Это не меняет штатный будущий путь через manual GitHub
Actions. Во время первого прямого запуска shell-проверка имени роли остановила
скрипт до установки зависимостей и restart; действующий сервис не прерывался.
Состояние было проверено, команда исправлена, после чего релиз завершился
успешно с сохранённым откатом к `e595d15`.

## 8. Реальная архитектура и границы готовности

Активные production-контуры:

1. Flutter web: `lib/main.dart`, `lib/screens/**`,
   `lib/services/gpm_api_service.dart`.
2. FastAPI: `app/app_orders_api.py`.
3. PostgreSQL: источник истины для активных заказов.
4. Nginx: HTTPS frontend и API reverse proxy.

Legacy Telegram-бот в `main.py` и `app/handlers/**` выключен и не должен
включаться с реальными данными. В нём остаются устаревшие зависимости и
неприемлемые для текущего режима workflows с чувствительными данными.

Серверно работают авторизация переходных accounts и базовый поток заказов.
Регистрация, реальные профили, проверка исполнителей, отклики, назначения, чат,
финансы/ledger и платежи ещё не являются полноценными серверными сущностями.
Соответствующие фиктивные возможности в production API-режиме должны оставаться
отключёнными, пока не появится backend и тесты.

Подсказки адреса технически рассчитаны на защищённый backend proxy DaData, но
production provider/key не активирован. Ручной ввод работает. Выбор DaData или
Яндекс остаётся открытым продуктовым решением; не включать внешнюю передачу
адресов без решения владельца и правовой оценки получателя/договора/ПДн.

## 9. Правовой статус РФ

`LEGAL_READINESS_RU.md` — инженерная оценка, не юридическое заключение.
Production-доступность не означает разрешение на открытый коммерческий запуск.

До закрытия блокеров разрешено только закрытое тестирование на синтетических
данных. Нельзя вводить реальные ФИО, телефоны, паспорт, ИНН, адреса, координаты,
банковские реквизиты и переписку.

До первого реального пользователя минимум необходимо:

- определить оператора ПДн и реквизиты юрлица/ИП;
- утвердить карту данных, основания, политику, отдельные согласия, retention и
  удаление;
- проверить/подать уведомление Роскомнадзору;
- подтвердить локализацию БД, файлов, логов и backup в РФ;
- заключить поручения обработки с хостером и внешними сервисами;
- утвердить договорную модель, оферту, отмены, возвраты и ответственность;
- реализовать DB-backed accounts, полноценный RBAC, audit log и отзыв доступа;
- проверить исторические access/nginx/application/auth журналы как возможный,
  но не доказанный инцидент доступа;
- подтвердить ротацию исторически раскрытых secrets;
- определить модель НПД/проверки ФНС/чеков и не допустить признаков трудовых
  отношений;
- отдельно оценить требования 54-ФЗ, 38-ФЗ и 289-ФЗ при включении платежей,
  рекламы и платформенных сделок.

## 10. Следующие задачи

### P0 до реального пилота

1. Получить от владельца реквизиты оператора и фактическую бизнес-модель.
2. Спроектировать DB-backed регистрацию/accounts, хеширование, подтверждение
   контактов, recovery, lockout, revocation, RBAC и audit trail.
3. Спроектировать серверные profile/application/assignment/chat/ledger сущности
   и единую state machine заказа.
4. Добавить миграции БД, непривилегированного runtime DB user, backup/PITR и
   проверку восстановления.
5. Провести E2E изоляции минимум двух клиентов и двух исполнителей.
6. Проверить журналы исторического периода и закрыть вопрос ротации secrets.
7. Реализовать права субъекта ПДн, сроки хранения и удаление из обработчиков и
   резервных копий.

### Продукт и UX

1. Владелец визуально проверяет опубликованный релиз и выбирает первый модуль
   отдельной доработки.
2. Решить DaData или Яндекс для адресных подсказок до подключения реальных
   адресов.
3. Согласовать единый словарь статусов и диаграмму переходов.
4. Уточнить терминологию исполнителей вместо универсальных «грузчиков».
5. Доработать desktop navigation, deep links/history и accessibility.
6. Не показывать фиктивные чаты/финансы до появления серверной реализации.

### Инфраструктурный долг

- перейти с root на отдельных ограниченных deploy/runtime users;
- добавить rate limiting, login lockout, pagination и request body limits;
- выбрать безопасную web session model с refresh/revocation;
- добавить hash-проверку Python lock и политику совместимости/rollback двух
  компонентов;
- определить retention backups и мониторинг диска;
- модернизировать либо окончательно архивировать legacy-бот.

## 11. Ключевые файлы

- `README.md` — краткий актуальный статус и локальный запуск;
- `PROJECT_AUDIT_2026-08-25.md` — подробный инженерный аудит;
- `LEGAL_READINESS_RU.md` — правовая матрица РФ;
- `PRODUCTION_DEPLOYMENT.md` — штатная публикация;
- `.github/workflows/ci.yml` — CI;
- `.github/workflows/deploy-production.yml` — production CI/CD;
- `.github/dependabot.yml` — dependency updates;
- `app/app_orders_api.py` — активный backend;
- `tests/test_app_orders_api.py` — backend regression suite;
- `lib/main.dart` — активная Flutter entry point;
- `lib/screens/auth/login_screen.dart` — выбор роли и вход;
- `lib/screens/client/client_create_order_screen.dart` — создание заказа;
- `lib/services/gpm_api_service.dart` — API/session/data layer;
- `test/login_screen_test.dart` — Flutter auth widget tests;
- `requirements-api.txt` — прямые production API dependencies;
- `requirements-api.lock` — транзитивный lock;
- `SECRET_ROTATION.md` — перечень ротации без новых secret values;
- старые `PROJECT_HANDOFF_*` — только исторический контекст.

В release-коммите `efec81f` Git содержит 239 tracked-файлов. Полный код,
история и документы хранятся в GitHub; отдельный ZIP не является источником
истины и не нужен для продолжения.

## 12. Правила безопасного продолжения

- Сначала выполнять только read-only проверку Git и публичных URL.
- Не повторять аудит, очистку заказов, миграцию accounts или публикацию без
  новой причины/задачи.
- Не запускать production deployment без явного запроса владельца.
- Не показывать и не копировать в чат secrets, SSH private key, server env или
  пароли accounts.
- Не помещать секреты в Flutter `.env`: web asset всегда публичен.
- Не удалять production backups и журналы без отдельного решения по retention и
  возможному legal hold.
- Любое изменение: отдельная ветка, минимальный diff, тесты, проверка CI, затем
  согласованное слияние/публикация.
- Не утверждать, что приложение готово к реальным данным или коммерческому
  запуску, пока P0 и legal blockers не закрыты документально и технически.

## 13. Как начать следующий чат

1. Полностью прочитать этот handoff и prompt-файл.
2. Выполнить `git status --short`, `git branch --show-current`, `git fetch`,
   сравнить `HEAD` и `origin/main`.
3. Проверить `https://app.gpmbot.ru/` и `/health` только read-only.
4. Кратко сообщить владельцу фактический Git/production/legal статус.
5. Спросить, какой отдельный продуктовый модуль дорабатываем первым, либо
   предложить начать с DB-backed accounts/регистрации как главного P0.

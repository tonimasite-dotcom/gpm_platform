# GPM: полный handoff текущего production и CRM recovery

Дата снимка: 28.08.2026. Часовой пояс: Europe/Moscow.

Это главный источник истины для следующего чата. Он заменяет прежние handoff как
операционную точку продолжения, но не удаляет их историческую ценность.

Читайте вместе с:

```text
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

## 1. Точная точка остановки

Последняя задача завершена и опубликована в production:

- исполнитель редактирует профиль;
- паспорт с фотографией отправляется логисту на модерацию;
- самозанятость/ИНН отправляется логисту на модерацию;
- такелажные ремни и собственные инструменты выбираются `Да/Нет`;
- логист видит очередь, защищённое вложение, подтверждает или отклоняет заявку;
- Email удалён только из формы профиля исполнителя и больше не отправляется при
  сохранении этого профиля;
- существующее серверное значение Email не стирается;
- кабинеты клиента и логиста не менялись;
- дизайн и цвета сохранены;
- владелец вручную подтвердил: «Все работает».

Production и GitHub сейчас опираются на один кодовый SHA:

```text
main = origin/main = 597a9d298f9d11814fe2d7e62f79fba70ef25994
production frontend = 597a9d298f9d11814fe2d7e62f79fba70ef25994
production backend = 597a9d298f9d11814fe2d7e62f79fba70ef25994
```

Документационный commit этого снапшота будет потомком `597a9d2` и сам по себе не
требует production deployment.

## 2. Последние коммиты и ветки

```text
597a9d2 Remove email from worker profile
659f3d1 Add worker profile verification moderation
92624b7 Add August 27 worker design handoff
b9ebdfa Restore worker workspace design
a6fac5c Add server-backed role workspaces
9a33715 Add invite-only account registration
3c147c7 Add database-backed app accounts
```

Актуальные рабочие ветки:

```text
main                                597a9d2
fix/worker-profile-remove-email     597a9d2
release/worker-profile-moderation   659f3d1
feature/worker-profile-moderation   5f5e8af
feature/crm-logist-publication      e117e69
```

CRM-ветка не является предком текущего `main`. Общий предок:

```text
92624b7e5ce77983a604f5be9a536c0b0b259cff
main имеет 2 собственных commit после общего предка
CRM-ветка имеет 3 собственных commit после общего предка
```

Поэтому нельзя делать вид, что CRM-код уже входит в production. После починки
авторизации `30b2bca` нужно переносить на свежую ветку от текущего `main` и
повторно проверять конфликты, тесты и поведение.

## 3. Production

Публичные адреса:

```text
frontend: https://app.gpmbot.ru/
backend health: https://app-api.gpmbot.ru/health
backend API: https://app-api.gpmbot.ru
```

Проверено после последнего deploy:

```text
frontend HTTP: 200
health: {"status":"ok","storage":"postgres"}
backend service: active
backend branch: main
backend SHA: 597a9d298f9d11814fe2d7e62f79fba70ef25994
```

Публичный Flutter asset содержит только:

```text
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Production не показывает публичный переключатель ролей. Переключатель
`Клиент / Исполнитель / Логист` допустим только в demo; в production роль берётся
из серверной учётной записи после входа.

Серверная опора:

```text
backend host: 46.149.71.147
backend hostname: msk-1-vm-smqt
service: gpm-app-api.service
repository: /opt/gpm/gpm_platform
env: /root/gpm-app-env
frontend host: 186.246.10.163
frontend web root: /var/www/gpm-app
database: PostgreSQL
```

Не помещать в документы содержимое env, database URL, логины, пароли, hashes,
session/integration tokens или private SSH keys.

## 4. Последние проверки и deploy runs

Worker moderation release:

```text
release commit: 659f3d1
CI: 33151898786 success
production deploy: 33153939250 success
```

Удаление Email:

```text
commit: 597a9d2
CI: 33155632768 success
demo deploy: 33156051767 success
production deploy: 33156246217 success
Flutter analyze: No issues found
Flutter tests: 5 passed
```

Production workflow `Deploy production` запускается вручную только из `main`.
Цель `all` проверяет Flutter, backend, зависимости, backend tests, создаёт
серверные rollback-каталоги, перезапускает API, проверяет health и атомарно
заменяет frontend. Он не создаёт PostgreSQL dump автоматически.

## 5. Профиль исполнителя и модерация

Активные frontend-файлы:

```text
lib/screens/worker/worker_profile_screen.dart
lib/screens/logist/logist_profile_screen.dart
lib/services/gpm_api_service.dart
test/worker_profile_screen_test.dart
test/gpm_api_service_test.dart
```

Backend и тесты:

```text
app/app_orders_api.py
tests/test_app_orders_api.py
WORKER_PROFILE_VERIFICATION.md
```

Основные endpoints:

```text
GET   /app-api/me/profile
PATCH /app-api/me/profile
GET   /app-api/me/verifications
POST  /app-api/me/verifications/{verification_type}
GET   /app-api/logist/worker-verifications
PATCH /app-api/logist/worker-verifications/{submission_id}
GET   /app-api/logist/worker-verifications/{submission_id}/attachment
```

Типы заявок:

```text
identity — паспортные данные + JPEG/PNG основного разворота
npd      — заявка на подтверждение самозанятости по ИНН
```

Статусы: `pending`, `approved`, `rejected`. При отклонении логист обязан указать
причину. Изменение ФИО, даты рождения или гражданства после отправки identity
сбрасывает подтверждение и требует повторной модерации.

Фото не хранится в Git, Flutter assets или PostgreSQL. Оно сохраняется backend в:

```text
/root/gpm-private-worker-verifications
mode: 700
owner: root:root
```

Production env содержит ровно одну настройку пути:

```text
GPM_APP_PRIVATE_UPLOAD_DIR=/root/gpm-private-worker-verifications
```

Разрешены JPEG/PNG до 8 МБ. Вложения доступны только через bearer endpoint
логисту. Заявки лежат в таблице:

```text
gpm_app_worker_verifications
schema migration: 0004_worker_verifications
```

Таблица в production существует.

## 6. Backups для worker verification release

Перед первой миграцией созданы и проверены:

```text
env backup:
/root/gpm-app-env.before-worker-verification-20260828T074609Z

PostgreSQL custom dump:
/root/gpm-private-backups/20260828-worker-verifications-predeploy-659f3d1/gpm.dump
size at snapshot: 30321 bytes
mode: 600
pg_restore --list: success
```

Оба файла существуют на момент снапшота. Не удалять их до утверждения retention
и закрытия rollback window. Workflow также создаёт Git/venv rollback-каталоги в
`/opt/gpm/backups`, а frontend-копии — в `/opt/gpm/front-backups`.

## 7. Самостоятельная архитектура

Активная схема:

```text
External CRM/order system -> FastAPI -> PostgreSQL -> Flutter Web/Android
Flutter authenticated UI  -> FastAPI -> PostgreSQL
```

GPM самостоятельно владеет:

- учётными записями, сессиями, ролями и audit;
- профилями и приглашениями;
- заказами после приёма от внешней системы;
- модерацией, публикацией, откликами и назначениями;
- чатами и уведомлениями;
- расчётом начислений исполнителя;
- проверками исполнителя.

Telegram, другие мессенджеры и соцсети не являются транспортом production.
Legacy bot в `main.py` должен оставаться выключенным до отдельного аудита или
архивирования. Не использовать `/api/telegram/` для CRM.

## 8. Дизайн

Действует `DESIGN_FREEZE.md`:

- серый фон, белые поверхности;
- малиновый активный цвет;
- жёлтые CTA там, где они уже утверждены;
- текущая нижняя навигация, карточки, поля, типографика и отступы;
- кабинеты клиента, исполнителя и логиста визуально согласованы.

Функции можно добавлять только внутри существующего визуального языка. Цвета,
компоновку и навигацию не менять без явного решения владельца.

## 9. Workstaff CRM → GPM: незавершённая линия

Ветка:

```text
origin/feature/crm-logist-publication = e117e699c414cd3c5cb5cf3c30ef6371a23accf7
30b2bca Restore CRM order publication by logist
a5a9220 Add August 28 CRM recovery handoff
e117e69 Add CRM token mismatch delta handoff
```

Эта ветка не слита в `main` и не развернута. Её документы можно прочитать без
переключения ветки:

```text
git show origin/feature/crm-logist-publication:PROJECT_HANDOFF_2026-08-28_CRM_PUBLICATION_RECOVERY.md
git show origin/feature/crm-logist-publication:CONTINUE_PROJECT_PROMPT_2026-08-28_CRM_PUBLICATION_RECOVERY.md
git show origin/feature/crm-logist-publication:PROJECT_HANDOFF_2026-08-28_CRM_TOKEN_MISMATCH_DELTA.md
```

Архитектура потока:

```text
https://ts.workstaffcrm.ru
  -> POST https://app-api.gpmbot.ru/app-api/orders
  -> X-Gpm-App-Token: server-side secret
  -> GPM PostgreSQL
  -> NEW у логиста
  -> Опубликовать
  -> PROCESSED у исполнителя
```

Историческая реализация:

```text
cfcf847 Add CRM app order publication API
3785502 Integrate CRM order publishing
e77ef62 Scope CRM moderation to publishing logist
54010fb Remove demo CRM import button
30b2bca Restore CRM order publication by logist
```

`54010fb` удалил только demo-кнопку `Из CRM`. Server-to-server endpoint не
удалён. Исторический token из Git считается раскрытым и не должен
восстанавливаться.

## 10. Доказанный диагноз CRM

В production journal были успешные публикации 5, 7, 11, 12 и 18 августа.
Последний доказанный успех:

```text
2026-08-18T10:36:41+00:00 200 OK
```

25 августа были четыре `401`. После основного CRM snapshot владелец создал
синтетическую заявку в Workstaff и нажал публикацию. GPM journal показал:

```text
2026-08-27T22:20:32+00:00 401 Unauthorized
```

Запрос до GPM доходит, поэтому кнопка, publisher, DNS и URL существуют. Ошибка
возникает до обработки payload на server-to-server авторизации.

Workstaff server:

```text
host: 5.183.191.222
hostname: sad0a47f6.fastvps-server.com
root: /var/www/gruzpiter/data/www/ts.workstaffcrm.ru
env: /var/www/gruzpiter/data/www/ts.workstaffcrm.ru/.env
publisher: app/Services/Order/GpmAppOrderPublisher.php
controller: app/Http/Controllers/Order/ManagerOrderController.php
UI: resources/js/pages/app/orders/logist_orders/index.vue
```

Publisher читает `GPM_APP_API_URL`, `GPM_APP_API_TOKEN` и посылает
`X-GPM-App-Token`. URL на Workstaff правильный:

```text
https://app-api.gpmbot.ru
```

Сравнивались только длина и первые 12 hex SHA-256, без вывода token:

```text
Workstaff: length 64, fingerprint c3b10d89a775
GPM:       length 64, fingerprint bcc12c793afd
```

Доказанный диагноз:

```text
Workstaff GPM_APP_API_TOKEN != GPM backend GPM_APP_API_TOKEN
```

`.env` Workstaff и GPM token при диагностике не менялись. Попытка прямого SSH с
GPM на Workstaff не прошла; на GPM root лишь добавился host key Workstaff в
`known_hosts`. Повторять межсерверную передачу не нужно.

## 11. Точная безопасная процедура CRM recovery

Эта работа ещё не выполнена. Она требует явного подтверждения владельца в новом
чате, потому что меняет два production env и перезапускает GPM API.

1. Локально создать новый случайный 64-символьный hex token и положить его только
   в clipboard, не печатая значение.
2. На Workstaff скрыто запросить вставку token, проверить длину, сделать
   timestamped `cp -a` backup `.env`, атомарно заменить только
   `GPM_APP_API_TOKEN`, сохранить owner/mode и выполнить
   `php artisan config:clear`.
3. На GPM backend скрыто запросить тот же token, сделать timestamped backup
   `/root/gpm-app-env`, атомарно заменить только `GPM_APP_API_TOKEN`, сохранить
   `root:root` и mode `600`, перезапустить `gpm-app-api.service`, проверить
   `active` и `/health`.
4. На обеих сторонах вывести только длину и короткий SHA-256 fingerprint.
5. Fingerprints должны совпасть.
6. Повторить публикацию полностью синтетической заявки Workstaff.
7. Проверить безопасный агрегат journal; требуемый результат — `200 OK`.
8. Только после `200` проверять payload и появление `NEW` у логиста.

Порядок:

```text
Workstaff env -> Laravel config clear -> GPM env -> GPM service restart
```

Rollback только парный: вернуть оба timestamped env backup, очистить Laravel
cache, перезапустить GPM service, проверить health и fingerprints. Нельзя
откатывать одну сторону.

После успешного `200` создать свежую CRM feature-ветку от текущего `main`,
перенести функциональный commit `30b2bca`, разрешить конфликты с worker profile,
прогнать весь CI и только затем отдельно предложить production deploy.

## 12. Что делает `30b2bca`

- убирает frontend-фильтрацию CRM-заявок по старому demo localStorage;
- маршрутизирует `NEW` по server-backed телефону профиля логиста;
- сопоставляет телефоны с `+7` и `8`;
- помещает заявку без `logist_phone` в общую очередь;
- называет действие `Опубликовать`;
- скрывает `NEW` от worker, но показывает `PROCESSED`;
- не меняет дизайн и цвета.

Исторические проверки commit:

```text
backend tests: 23 passed, 1 PostgreSQL integration skipped locally
Flutter analyze: no issues
Flutter tests: 3 passed
Flutter release web build: success
CI 33118388353: success
```

Эти проверки нужно повторить после переноса на текущий `main`.

## 13. Адресные сервисы

Текущий production provider — DaData. Он настроен server-side в
`/root/gpm-app-env`; синтетический адрес и координаты ранее проверены. Backup:

```text
/root/gpm-app-env.before-dadata-20260827
```

Яндекс был подготовлен, но выключен в исторической локальной ветке
`feature/address-provider-switch` с опорным commit `f06e540`. Эта ветка не
опубликована на origin и отсутствует в текущем клоне; считать её доступной нельзя.
Решение и инструкции сохранены в CRM snapshot commit `a5a9220`:

```text
ADDRESS_PROVIDER_DECISION.md
DADATA_ADDRESS_SETUP.md
YANDEX_ADDRESS_SETUP.md
```

Не включать Яндекс и не смешивать адресную ветку с CRM recovery.

## 14. PostgreSQL и данные

Backend создаёт/использует таблицы и миграции для:

- orders;
- schema migrations;
- accounts;
- invitations;
- sessions;
- audit;
- profiles;
- worker verifications;
- chat threads/messages/reads.

Applications/assignments пока являются server-owned данными внутри JSON заказа,
а не полностью нормализованными таблицами. Финансы исполнителя — расчёт
начислений по завершённым заказам, а не платёжный ledger.

Не выполнять schema/data change без отдельного проверенного PostgreSQL dump.
Не выводить строки с ПДн. Не удалять production records, backups или logs без
отдельного решения по retention/legal hold.

## 15. Учётные записи и регистрация

- роли: `client`, `worker`, `logist`;
- серверные accounts/sessions/audit находятся в PostgreSQL;
- пароль хранится только как versioned `scrypt` hash;
- действует lockout и logout revocation;
- публичной регистрации нет;
- регистрация закрытая, по одноразовым приглашениям;
- recovery и подтверждение телефона/email не завершены;
- роль не выбирается пользователем после входа.

Никогда не возвращать общий `admin/admin` или browser-side выбор production-роли.

## 16. Разрешённый режим и P0

До закрытия правовых и инфраструктурных P0 разрешено только закрытое тестирование
на полностью синтетических данных. Нельзя загружать реальные:

- ФИО, телефоны, паспорт и ИНН;
- адреса и координаты;
- банковские реквизиты;
- переписку и документы.

Основные незакрытые P0:

1. Определить оператора ПДн, реквизиты и договорную роль GPM.
2. Утвердить карту данных, основания, согласия, retention и deletion.
3. Проверить/подать уведомление Роскомнадзору.
4. Подтвердить локализацию всех DB/files/logs/backups в РФ.
5. Заключить поручения обработки с хостером, CRM и адресным сервисом.
6. Добавить подтверждение контактов и recovery.
7. Реализовать права субъекта: доступ, исправление, блокировка, удаление.
8. Закрыть ротацию всех исторических secrets.
9. Провести restore drill/PITR и утвердить backup retention.
10. Выполнить полноценный multi-user E2E isolation audit.
11. Утвердить режим passport verification и НПД через официальный сервис ФНС.
12. Повторно оценить модель по закону №289-ФЗ до реальных сделок/платежей.

## 17. Известный технический долг

- legacy Telegram dependencies и старые экраны остаются в repository;
- часть applications/assignments хранится в JSON заказа;
- нет полноценного payment ledger и реальных платежей;
- нет contact verification/recovery;
- нет утверждённой процедуры удаления verification files и backups;
- нужны accessibility/deep-link/browser-history проверки;
- нужен полный state dictionary и concurrency E2E;
- старые handoff содержат устаревшие production SHA и должны читаться только как
  история;
- CRM branch необходимо переносить на свежий `main`, а не deploy как есть.

## 18. Правила секретов

- Не читать и не печатать populated env целиком.
- Не выводить пароли, hashes, tokens, API keys, database URL, private keys.
- Допустимы только длина, наличие и короткий SHA-256 fingerprint секрета.
- Не помещать secrets в Git, Markdown, Flutter assets, browser storage или logs.
- Публичный Flutter `.env` содержит только mode и API URL.
- Исторические секреты из Git не восстанавливать, а ротировать.
- SSH private key в `C:\tmp` не является частью проекта и не должен копироваться
  в snapshot или новый чат.

## 19. Безопасная стартовая проверка нового чата

Сначала выполнить только read-only:

```text
git status --short --branch
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git rev-parse origin/feature/crm-logist-publication
git log --all --decorate --oneline -12
```

Публично проверить:

```text
https://app.gpmbot.ru/
https://app-api.gpmbot.ru/health
https://app.gpmbot.ru/assets/.env
```

Сообщить владельцу:

1. ветку, HEAD, `origin/main`, clean/dirty;
2. production frontend/backend SHA и health;
3. что worker profile moderation и удаление Email уже в production;
4. что CRM token mismatch остаётся незакрытым;
5. что `30b2bca` не входит в `main`;
6. один рекомендуемый следующий шаг.

Затем остановиться и дождаться выбора владельца. Не начинать ротацию token,
production deploy или широкую переработку автоматически.

## 20. Рекомендуемый следующий шаг

Если владелец продолжает CRM recovery, получить его явное подтверждение на
совместную безопасную ротацию `GPM_APP_API_TOKEN` на Workstaff и GPM. Затем
выполнить процедуру из раздела 11 до доказанного `200 OK`.

Если владелец выбирает другой продуктовый этап, оставить CRM-ветку и env без
изменений и создать новую feature-ветку от актуального `origin/main`.

## 21. Нельзя повторять

- Не повторять worker verification schema migration и уже успешные deploy runs.
- Не возвращать Email в профиль исполнителя.
- Не возвращать demo role switcher в production.
- Не менять дизайн и цвета.
- Не включать Telegram/legacy bot.
- Не включать Яндекс автоматически.
- Не deploy `e117e69` или `30b2bca` как текущий production branch.
- Не проверять CRM payload до исправления `401`.
- Не использовать реальные паспортные данные даже для теста.

## 22. Ключевые ссылки

```text
repository: https://github.com/tonimasite-dotcom/gpm_platform
production: https://app.gpmbot.ru/
health: https://app-api.gpmbot.ru/health
Workstaff test: https://ts.workstaffcrm.ru/
```

```text
CI worker moderation: 33151898786
deploy worker moderation: 33153939250
CI remove Email: 33155632768
demo remove Email: 33156051767
production remove Email: 33156246217
CRM feature CI: 33118388353
CRM main snapshot CI: 33121084115
CRM delta snapshot CI: 33124421262
```

GitHub — источник истины для кода и истории. Production env, database dumps,
private verification files, SSH keys и rollback directories в Git не входят.

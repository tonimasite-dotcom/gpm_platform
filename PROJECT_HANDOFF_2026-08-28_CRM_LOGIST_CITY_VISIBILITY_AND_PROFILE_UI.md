# GPM: полный handoff CRM, изоляции заказов и профиля логиста

Дата снимка: 28.08.2026. Часовой пояс: Europe/Moscow.

Это главный источник истины для следующего чата. Он дополняет и заменяет как
операционную точку продолжения файл
`PROJECT_HANDOFF_2026-08-28_CURRENT_PRODUCTION_AND_CRM_RECOVERY.md`.
Старый файл сохраняется как подробная история production, worker verification,
инфраструктуры и первоначальной диагностики CRM.

Связанный стартовый промт:

```text
CONTINUE_PROJECT_PROMPT_2026-08-28_CRM_LOGIST_CITY_VISIBILITY_AND_PROFILE_UI.md
```

## 1. Точная точка остановки

Последняя полностью завершённая функциональная работа находится в отдельной
ветке:

```text
branch: feature/crm-logist-city-visibility
HEAD:   a4433992298fffccbd8b09b863e82fbffb3807ff
remote: origin/feature/crm-logist-city-visibility на том же SHA
working tree на момент начала снапшота: clean
```

Ветка содержит два commit поверх текущего `origin/main`:

```text
5913e64 Restore CRM order publication by logist
a443399 Enforce order ownership and city visibility
```

Незавершённая пользовательская задача, на которой остановились:

> В профиле логиста убрать поле Telegram. Email оставить, но сделать
> необязательным. «Города и районы» оставить, но пока тоже сделать
> необязательным.

По этой задаче выполнена только read-only инспекция. Код профиля логиста ещё не
изменялся. Следующий чат должен продолжить именно с реализации этой задачи.

Регистрацию логистов пользователь явно попросил пока отложить. Не смешивать её
с текущей задачей и не начинать без нового запроса.

## 2. Git и production

Текущее состояние Git до добавления этого снапшота:

```text
main = origin/main = d5fb364a8e8db2b3abba6aabb9106e70f4bc6832
feature HEAD       = a4433992298fffccbd8b09b863e82fbffb3807ff
```

`d5fb364` содержит документацию. Последний развёрнутый боевой код остаётся:

```text
production frontend code: 597a9d298f9d11814fe2d7e62f79fba70ef25994
production backend code:  597a9d298f9d11814fe2d7e62f79fba70ef25994
```

CRM/ownership/city feature из `5913e64` + `a443399`:

- не слита в `main`;
- не развёрнута в production;
- опубликована только в feature-ветке;
- не должна разворачиваться без отдельного явного подтверждения владельца.

Read-only production-проверка при создании этого handoff:

```text
https://app.gpmbot.ru/                -> HTTP 200
https://app-api.gpmbot.ru/health      -> {"status":"ok","storage":"postgres"}
```

Production-серверы и пути:

```text
backend host: 46.149.71.147
backend hostname: msk-1-vm-smqt
backend service: gpm-app-api.service
backend repository: /opt/gpm/gpm_platform
backend env: /root/gpm-app-env
frontend host: 186.246.10.163
frontend root: /var/www/gpm-app
database: PostgreSQL
private verification storage: /root/gpm-private-worker-verifications
```

Не выводить и не сохранять содержимое env, database URL, логины, пароли,
session/integration tokens, private keys или реальные персональные данные.

## 3. CRM recovery завершён

Старый handoff фиксировал несовпадение CRM-токенов и `401 Unauthorized`. После
его создания токен был безопасно синхронно ротирован на Workstaff и GPM.

Финальное подтверждённое состояние без раскрытия секрета:

```text
Workstaff token length: 64
GPM token length:       64
final fingerprint:      be2eaccb8509
```

Проверки после ротации:

```text
GPM API service: active
GPM health: 200 / ok / postgres
synthetic order: GPM-SYNTH-TOKEN-20260828T112219Z
CRM POST result: 200 OK
stored status: NEW
```

Backups ротации:

```text
Workstaff:
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/.env.before-gpm-token-rotation-20260828T112010Z

GPM:
/root/gpm-app-env.before-gpm-token-rotation-20260828T112012Z
```

Во время первой попытки из-за ошибочного shell quoting промежуточное значение
токена попало в терминальный вывод. Оно было немедленно выведено из эксплуатации
повторной ротацией. Финальный активный токен в чат, Git и документы не выводился.
Не восстанавливать промежуточное или историческое значение.

Временный SSH-ключ и временные скрипты были удалены. Старый временный доступ к
Workstaff после очистки был проверен и больше не работал.

## 4. Что реализовано в feature-ветке

### 4.1 CRM только для назначенного логиста

CRM передаёт `logist_phone` в `POST /app-api/orders`. Backend:

1. нормализует российские форматы `+7` и `8` до последних 10 цифр;
2. требует корректный телефон;
3. ищет ровно один активный GPM-аккаунт с ролью `logist` и таким телефоном в
   серверном профиле;
4. отклоняет отсутствующий, неизвестный или неоднозначный телефон;
5. сохраняет стабильный `logist_account_id` в заказе.

Только назначенный логист видит CRM-заказ, публикует его, рассматривает отклики,
видит его в dashboard и получает доступ к связанным чатам. Общей CRM-очереди
больше нет. Для старых заказов без `logist_account_id` сохранён ограниченный
fallback по непустому совпадающему телефону.

В CRM-модальном окне «Опубликовать в приложение» нужно указывать телефон из
профиля целевого логиста GPM. Для синтетического теста обсуждался номер вида
`+7 000 000-12-34`; `1234` использовать нельзя, потому что новая строгая логика
его отклонит.

Перед будущим deploy нужно убедиться, что у каждого существующего логиста в GPM
указан актуальный уникальный телефон. Общего административного списка телефонов
в UI пока нет: телефон находится в нижней вкладке логиста «Профиль».

### 4.2 Клиент как самостоятельный заказчик

Клиент:

- видит только заказы, созданные своим account ID;
- самостоятельно создаёт и сразу публикует собственный заказ;
- видит отклики только по своему заказу;
- может принять или отклонить отклик;
- может принять выполненную работу из `DONE_PENDING` в `CONVERTED`;
- не видит CRM-заказы других пользователей;
- не получает ложный чат «клиент—логист» для самостоятельного заказа без
  назначенного логиста.

Реальная банковская оплата в этой feature не реализована. Это отдельный
платёжный контур и его нельзя заявлять как готовый.

### 4.3 Исполнитель видит заказы только своих городов

Для discovery заказа требуется:

```text
order.status == PROCESSED
normalized(order.city) входит в normalized(worker.profile.cities)
```

Исполнитель может хранить несколько городов. Нормализация нечувствительна к
регистру, пробелам, `ё/е`, а также префиксам `город`, `г.` и `г`.

Ограничение применяется и к списку заказов, и к прямому POST отклика, поэтому
обойти его ручным API-запросом нельзя. Уже назначенный исполнителю активный или
завершённый заказ остаётся видимым независимо от последующего изменения списка
городов.

Важно: пользователь попросил сделать «Города и районы» необязательным только в
профиле логиста. Для исполнителя список городов остаётся функционально важным и
не должен становиться необязательным в рамках текущей задачи.

### 4.4 Чаты и dashboard

- логистские dashboard-счётчики считают только доступные конкретному логисту
  заказы;
- логист не может читать или отправлять сообщения в чатах чужого заказа;
- client-owned заказ без назначенного логиста не создаёт лишний `clientLogist`;
- client/worker чат создаётся после назначения исполнителя;
- server-side проверки выполняются для чтения, отправки, attention и support.

## 5. Изменённые feature-файлы

Отличия `origin/main...a443399`:

```text
CRM_APP_PUBLICATION.md
INDEPENDENT_PLATFORM_ARCHITECTURE.md
README.md
app/app_orders_api.py
lib/screens/client/client_home_screen.dart
lib/screens/client/client_orders_screen.dart
lib/screens/logist/logist_orders_screen.dart
tests/test_app_orders_api.py
```

Ключевые новые/изменённые backend-функции:

```text
normalized_city_identity
worker_profile_cities
worker_can_discover_order
logist_owns_order
resolve_active_logist_account_id
orders_for_user
validate_order_patch
apply_to_order_atomically
decide_order_application_atomically
account_dashboard
_ensure_order_chat_threads
_chat_thread_access
publish_order_payload
```

## 6. Проверки feature-ветки

Локально выполнено перед commit `a443399`:

```text
python -m unittest tests.test_app_orders_api
26 tests passed, 1 PostgreSQL test skipped locally

flutter analyze
No issues found

flutter test --no-pub
5 tests passed

flutter build web --release --output C:\tmp\gpm-crm-logist-city-web
success, Wasm dry run succeeded

git diff --check
success
```

После push:

```text
GitHub Actions workflow: CI
branch: feature/crm-logist-city-visibility
badge status: passing
```

GitHub CLI на этом устройстве не установлен, а неавторизованный GitHub REST API
на момент проверки исчерпал общий rate limit, поэтому ID run в handoff не
зафиксирован. Публичный branch-specific badge вернул `CI - passing`.

## 7. Незавершённая задача: профиль логиста

Активный файл:

```text
lib/screens/logist/logist_profile_screen.dart
```

Read-only инспекция показала:

- `_telegramController` объявлен, загружается, сохраняется, dispose-ится и
  привязан к видимому `TextFormField`;
- Email сейчас имеет обязательный validator
  `_required(value, 'Укажите email')`;
- «Города и районы» сейчас имеет обязательный validator
  `_required(value, 'Укажите зону работы')`;
- backend `_profile_completion` для `logist` сейчас требует
  `("display_name", "email", "cities")`.

Рекомендуемая точная реализация без изменения дизайна:

1. Удалить Telegram-поле из UI логиста.
2. Удалить `_telegramController`, его load/dispose и ключ `telegram` из patch при
   сохранении профиля. Не выполнять массовое удаление старых серверных значений
   без отдельного запроса.
3. Оставить Email видимым, но убрать required-validator. Допустимо уточнить label
   как `Email (необязательно)` в текущем визуальном стиле.
4. Оставить «Города и районы» видимым, но убрать required-validator. Допустимо
   уточнить label как `Города и районы (необязательно)`.
5. Изменить backend profile completion логиста так, чтобы необязательные Email и
   города не понижали заполненность. Разумный обязательный набор для текущей
   CRM-модели: `("display_name", "phone")`.
6. Не менять обязательность `cities` у worker.
7. Добавить или обновить тесты профиля логиста и backend completion.
8. Запустить formatter, backend tests, `flutter analyze`, Flutter tests, release
   web build и `git diff --check`.
9. Сделать отдельный commit в текущей feature-ветке и push; дождаться green CI.
10. Не сливать в `main` и не разворачивать production без отдельного подтверждения.

## 8. Production worker verification и закрытый режим

Уже развёрнуто на commit `597a9d2`:

- редактирование профиля исполнителя;
- паспортная модерация с приватным JPEG/PNG вложением;
- НПД/ИНН-модерация;
- очередь логиста с approve/reject и обязательной причиной отказа;
- сброс identity verification после изменения ФИО, даты рождения или
  гражданства;
- удаление Email только из UI профиля исполнителя без стирания существующего
  серверного значения;
- отсутствие публичного production role switcher.

Private attachments:

```text
/root/gpm-private-worker-verifications
owner/mode: root:root / 700
GPM_APP_PRIVATE_UPLOAD_DIR=/root/gpm-private-worker-verifications
JPEG/PNG, до 8 МБ
```

Проверенные backups worker verification release:

```text
/root/gpm-app-env.before-worker-verification-20260828T074609Z
/root/gpm-private-backups/20260828-worker-verifications-predeploy-659f3d1/gpm.dump
```

Не удалять их до отдельного решения по retention и rollback window. Production
deploy workflow не создаёт PostgreSQL dump автоматически.

## 9. Архитектура и дизайн

Активная схема:

```text
Workstaff CRM -- server-to-server --> FastAPI --> PostgreSQL --> GPM Flutter
GPM authenticated clients ---------> FastAPI --> PostgreSQL
```

GPM самостоятельно владеет accounts, roles, sessions, profiles, orders,
applications, assignments, statuses, chats, finance records и verification.
Telegram, другие мессенджеры и соцсети не являются production-транспортом.
Legacy bot и `/api/telegram/` не включать.

Действует `DESIGN_FREEZE.md`. Нельзя менять палитру, навигацию, компоновку,
типографику, карточки и общий визуальный язык без отдельного решения владельца.
Текущая задача профиля логиста является функциональным изменением существующих
полей и не разрешает редизайн.

## 10. Безопасность и P0

Проект остаётся закрытым тестом только на синтетических данных. Не загружать
реальные паспорта, ИНН, телефоны, адреса, банковские данные или переписку до
закрытия юридических и инфраструктурных P0.

Открытые направления включают:

- оператор ПДн, документы, согласия и уведомление РКН;
- локализация всех хранилищ и договоры обработки;
- contact verification и account recovery;
- права субъекта, retention и deletion;
- регулярная secret rotation;
- restore drill/PITR и проверенный DB backup workflow;
- полный E2E isolation;
- официальная НПД-проверка;
- отдельная платёжная архитектура;
- повторная юридическая оценка до реальных сделок.

## 11. Обязательные правила следующего чата

- Сначала выполнить только read-only проверку branch/HEAD/origin/status.
- Не печатать реальные secrets и populated env.
- Не восстанавливать токены из Git или истории терминала.
- Не возвращать Email в профиль исполнителя.
- Не делать города необязательными у исполнителя.
- Не возвращать demo role switcher в production.
- Не включать legacy Telegram bot.
- Не менять дизайн и цвета.
- Не начинать отложенную регистрацию логистов.
- Сохранять несвязанные пользовательские изменения.
- Перед commit выполнять все пропорциональные проверки.
- После push ждать green CI.
- Production менять только по отдельному явному запросу владельца.

## 12. Первый ответ следующего чата

После read-only проверки кратко сообщить:

1. текущую ветку и HEAD;
2. соответствие remote и чистоту working tree;
3. что production остаётся на боевом коде `597a9d2`, а новая feature ещё не
   развёрнута;
4. что CRM recovery уже завершён успешным `200 OK`, старый диагноз token mismatch
   исторический;
5. что следующая задача — убрать Telegram и сделать Email/города необязательными
   только в профиле логиста;
6. что регистрация логистов отложена.

После этого продолжить уже авторизованную задачу профиля логиста без повторного
запроса подтверждения, если read-only проверка не выявила расхождений.

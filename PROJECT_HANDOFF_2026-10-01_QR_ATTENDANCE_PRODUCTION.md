# GPM Platform: полный снапшот и точка продолжения

Дата: 01.10.2026. Часовой пояс: Europe/Moscow.

Это новый главный источник истины для следующей сессии. Он дополняет и
заменяет как стартовый документ
`PROJECT_HANDOFF_2026-09-18_ACTOR_ORDER_NUMBERING.md`. Старые handoff-файлы
не удалять: это история принятых решений.

Готовый стартовый промпт нового чата:

```text
CONTINUE_PROJECT_PROMPT_2026-10-01_QR_ATTENDANCE_PRODUCTION.md
```

---

## 1. Точная точка остановки

Продуктовый код, с которым закончена сессия:

```text
branch:              main
product release:     71db271 Add one-minute QR attendance tracking
origin/main:         71db271 (до документационного коммита этого снапшота)
production backend:  71db271
production frontend: 71db271
deploy run:           36920664797, target=all, success
backend health:       {"status":"ok","storage":"postgres"}, HTTP 200
guest attendance:    https://app-api.gpmbot.ru/attendance, HTTP 200
frontend:             https://app.gpmbot.ru/, HTTP 200
```

Коммит, содержащий этот файл и новый continuation prompt, является только
документационным и отдельно на production не деплоится. Его фактический hash
нужно получить через `git log -1 --oneline` в новом чате.

После продуктового коммита в рабочем дереве оставались четыре старых
line-ending-only изменения:

```text
linux/flutter/generated_plugin_registrant.cc
linux/flutter/generated_plugins.cmake
windows/flutter/generated_plugin_registrant.cc
windows/flutter/generated_plugins.cmake
```

`git diff --ignore-space-at-eol --exit-code -- <эти файлы>` возвращал `0`.
Это не содержательные изменения онлайн-табеля. Они намеренно не вошли в
`71db271`; не сбрасывать и не коммитить их автоматически, пока не выяснено,
нужны ли они пользователю.

---

## 2. Что сделано в сессии 01.10

### 2.1. Исправлены пустые номера в заголовках карточек

Пользователь показал реальные карточки с заголовком `Заявка №` без номера,
хотя сам серверный `id` уже имел новый формат. Причина: actor-order
нормализовался до выделения номера и сохранял короткий заголовок
`"Заявка № "`.

Коммит:

```text
1c9b26f Fix generated order titles
production backend run 36896273264, success
```

Что изменено:

- новые actor-заказы получают `title = "Заявка № <server number>"` вместе с
  серверной заменой `id`/`external_order_id`;
- `ensure_order_display_title()` чинит старые затронутые записи на чтении,
  без рискованного изменения реальной БД;
- исправление покрыто backend-тестом.

Заголовки чатов отдельно не менялись: обычный чат заказа использует title
заказа, поэтому теперь показывает `Заявка № C…` / `Заявка № L…`; служебный
чат по-прежнему называется `Поддержка GPM`.

### 2.2. Добавлен маркер времени публикации заявки

Пользователь попросил показывать на всех заявках автоматически проставленные
дату и время публикации.

Коммит:

```text
f5218eb Show order publication timestamps
production frontend run 36901538422, success
```

Реализация:

- общий `OrderPublishedAtMarker` в `lib/utils/order_display.dart`;
- источник времени — серверное поле первого сохранения `created_at`;
- формат: `Опубликовано ДД.ММ.ГГГГ ЧЧ:ММ`, в локальном часовом поясе;
- маркер добавлен в карточки клиента, логиста и исполнителя;
- для legacy-записей без валидного `created_at` маркер скрывается, выдуманное
  время не показывается;
- Flutter unit/widget-тесты добавлены в `test/order_display_test.dart`.

### 2.3. Реализован и задеплоен онлайн-табель прихода/ухода

Согласованная бизнес-логика:

1. Назначенный исполнитель приходит на заказ и в своём приложении выпускает
   уникальный QR для действия `приход`.
2. Если заявку создал клиент, QR сканирует именно этот авторизованный клиент
   в приложении GPM и после preview вручную подтверждает присутствие.
3. Если заявку создал логист либо она пришла из CRM, логист на объекте не
   требуется. Представитель заказчика на месте открывает публичный QR,
   подтверждает присутствие и получает одноразовый шестизначный код. Код
   сообщает исполнителю, а исполнитель вводит его в своём приложении.
4. При уходе повторяется тот же процесс, но сервер уже создаёт действие
   `уход`.
5. Один challenge действует ровно 60 секунд и только для одного действия.
   Новый QR для того же действия немедленно делает предыдущий недействительным.
6. В guest-сценарии шестизначный код действует только оставшееся время
   исходного 60-секундного challenge; новый таймер после подтверждения не
   начинается.

Коммит и production:

```text
71db271 Add one-minute QR attendance tracking
production run 36920664797, target=all, success
```

---

## 3. Онлайн-табель: серверная реализация

Главный файл: `app/app_orders_api.py`.

### 3.1. Новая схема БД

Миграционный marker:

```text
0006_order_attendance
```

Аддитивно создаются PostgreSQL/SQLite-совместимые таблицы:

```text
gpm_app_order_attendance
gpm_app_attendance_challenges
```

Первая хранит одну строку табеля на пару `(order_id, worker_account_id)`:
время прихода/ухода, время подтверждения и идентификатор подтверждавшего.
Вторая хранит одноразовые challenges: действие, hashes секретов, режим
проверки, срок, подтверждение представителя и факт использования.

Сырые QR token, восьмизначный резервный код и шестизначный код представителя
в БД не сохраняются — сохраняются SHA-256 hashes. Время и действие определяет
только сервер.

### 3.2. Режимы подтверждения

`authenticated_client`:

- только для заказа с `created_by_role == client`;
- client обязан быть именно владельцем заказа;
- сначала вызывается preview с номером заказа, именем исполнителя и действием;
- клиент явно подтверждает, что исполнитель находится рядом;
- подтверждение сразу записывает приход/уход.

`guest_code`:

- для заказов логиста и CRM;
- представитель на объекте не обязан иметь аккаунт GPM;
- GET QR-страницы ничего не записывает, действие требует явного POST;
- после подтверждения представитель получает одноразовый код из 6 цифр;
- завершить действие этим кодом может только тот назначенный исполнитель,
  для которого выпущен challenge.

Резервный путь при проблемах с камерой:

- исполнитель видит случайный 8-символьный request code;
- клиент вводит его внутри приложения;
- guest-представитель открывает `/attendance` и вводит его в публичную форму.

### 3.3. API и публичные routes

Авторизованные endpoints:

```text
GET  /app-api/me/order-attendance/{order_id:path}
POST /app-api/me/order-attendance/{order_id:path}/challenge
POST /app-api/me/attendance/preview
POST /app-api/me/attendance/confirm
POST /app-api/me/attendance/complete
```

Публичный guest flow:

```text
GET  /attendance
GET  /attendance/confirm/{token}
POST /attendance/confirm/{token}
POST /attendance/confirm-code
POST /attendance/confirm-request-code
```

Production URL QR формируется от `https://app-api.gpmbot.ru`; override:
`GPM_APP_PUBLIC_API_URL`.

Публичные страницы отдаются с `no-store` и CSP/security headers. Для
client-created заказа публичная страница не подтверждает действие и просит
использовать приложение GPM.

### 3.4. Права, состояния и аудит

- Challenge создаёт только назначенный worker.
- Worker видит только свою строку табеля.
- Client видит табель только собственного заказа и может подтверждать только
  client-created заказ.
- Logist видит табель только принадлежащего ему заказа, но не подменяет
  присутствующего представителя в guest-сценарии.
- Закрытые `CONVERTED`/`JUNK` заказы не принимают новые challenges.
- Состояния строки: `not_started` → `checked_in` → `completed`.
- Повторное использование challenge возвращает конфликт.
- Каждое завершённое действие пишет audit event `attendance_check_in` либо
  `attendance_check_out`.

Текущий MVP сознательно не блокирует обычную кнопку завершения заказа при
отсутствии отметки ухода. Это отдельное продуктовое решение, его не добавляли
без согласования.

---

## 4. Онлайн-табель: Flutter

Основной новый файл:

```text
lib/screens/attendance/order_attendance.dart
```

Компоненты:

- `OrderAttendancePanel` — табель клиента/логиста: имена, статусы, приход,
  уход, длительность; у клиента также scan/manual confirm;
- `WorkerAttendancePanel` — текущий статус worker и кнопка
  `Отметить приход/уход`;
- `AttendanceChallengeScreen` — QR, точный countdown, резервный 8-символьный
  код и ввод 6-значного кода guest-представителя;
- `AttendanceScannerScreen` — QR-only scanner через `mobile_scanner`;
- перед client-confirm всегда показывается preview и предупреждение
  подтверждать только присутствующего рядом исполнителя.

Интеграция:

```text
lib/screens/client/client_orders_screen.dart
lib/screens/logist/logist_orders_screen.dart
lib/screens/worker/worker_orders_screen.dart
lib/services/gpm_api_service.dart
```

Зависимости:

```yaml
mobile_scanner: ^7.4.2
qr_flutter: ^4.1.0
```

Platform config:

- Android: `android.permission.CAMERA`;
- iOS: расширен `NSCameraUsageDescription`;
- macOS generated registrant содержит `MobileScannerPlugin`.

Фото исполнителя в табель не добавлялось: в текущей нормальной server-profile
модели нет согласованного поля profile photo. Показывается display name либо
username.

---

## 5. Нумерация заказов и значение номера

Формат остаётся:

```text
L#/C#-ДДММГГ-#
```

Пример `L1-180926-2`:

- `L` — заявку создал логист (`C` означает клиента);
- первая цифра — постоянный actor code этого аккаунта, выданный по порядку
  регистрации;
- `180926` — дата **публикации**, 18.09.2026, по московскому календарному
  дню, а не дата выполнения работ;
- последняя `2` — второй заказ этого конкретного actor, опубликованный в этот
  день.

Последний счётчик начинается заново с `1` каждый московский день отдельно
для каждого actor. Поэтому `L1-011026-1` и `L1-180926-2` не противоречат друг
другу: это разные дни публикации. Дата/время публикации теперь отдельно
видна на карточке через server `created_at`.

Сервер всегда игнорирует присланный приложением номер для новых actor-заказов.
Это защищает от старых APK. CRM/integration-заказы сохраняют обязательный
внешний номер. Старые сохранённые `APP-...` не переименовываются задним числом.

---

## 6. Проверки перед релизом 71db271

Локально успешно:

```text
python unittest: 61 tests, OK, 1 skipped
flutter test:     42 tests, all passed
flutter analyze:  No issues found
flutter build web --release --no-pub --base-href /: success
Wasm dry run: success
git diff --check: clean (кроме предупреждений CRLF у старых generated files)
```

Backend-тесты проверяют в том числе:

- клиентский check-in/check-out;
- TTL ровно 60 секунд, включая границу expiration;
- новый challenge уникален и инвалидирует предыдущий;
- повторное использование запрещено;
- guest получает шестизначный код, но табель не меняется до ввода worker;
- чужой worker не может завершить действие.

Flutter-тесты проверяют parsing QR/custom payload и guest challenge UI с
QR, минутным таймером, request code и полем шестизначного кода.

Android APK в этой сессии локально не собран: Android SDK отсутствует по
стандартным путям, `adb` отсутствует. SDK не устанавливался без отдельного
разрешения. Старые установленные APK автоматически не обновились и не содержат
новый UI; веб/PWA production обновлён. Release keystore по прежнему решению
пользователя не делаем без отдельного запроса.

---

## 7. Production и способ деплоя

Репозиторий и инфраструктура:

```text
repository: https://github.com/tonimasite-dotcom/gpm_platform
workflow:   .github/workflows/deploy-production.yml
backend:    46.149.71.147, /opt/gpm/gpm_platform, gpm-app-api.service
frontend:   186.246.10.163, /var/www/gpm-app
```

Production deploy только вручную через `workflow_dispatch` с `main`, targets:
`all`, `backend`, `frontend`. Backend и frontend имеют rollback в workflow.
`app/backfill_actor_codes.py` продолжает идемпотентно запускаться при каждом
backend deploy.

Прямого SSH-доступа к production у ассистента нет. Серверный SSH key хранится
только в GitHub Actions secret `PROD_SSH_PRIVATE_KEY`. Разовые production
операции делать через безопасный шаг workflow, а не попытками прямого SSH.

В текущем PowerShell `gh` CLI не найден. Run `36920664797` был запущен через
GitHub REST API с credential, полученным через `git credential fill`; token не
печатался и не сохранялся в файлы. В новой сессии сначала проверить, доступен
ли `gh`; если нет, можно повторить безопасный REST dispatch только после
подтверждения пользователя.

Не деплоить повторно `71db271` без новых изменений или факта дефекта.

---

## 8. Ручная приёмка после текущего релиза

Пользователь подтвердил, что исправленные номера/заголовки и маркер публикации
выглядят хорошо. Онлайн-табель после production deploy ещё не проходил полную
ручную приёмку двумя сторонами.

Следующий рекомендуемый smoke checklist:

1. Client-created заказ, назначенный worker: worker показывает QR прихода,
   владелец-client сканирует, сверяет номер/имя/action и подтверждает.
2. Убедиться, что табель обоих показывает время прихода.
3. Выпустить новый QR ухода и повторить; проверить время ухода и длительность.
4. Logist/CRM-created заказ: представитель без login открывает QR, подтверждает
   и видит 6 цифр; assigned worker вводит код; проверить табель логиста/worker.
5. Убедиться, что QR старше минуты и заменённый QR отвергаются.
6. Проверить fallback без камеры: 8-символьный код в client app и на
   публичной `/attendance` странице.
7. Проверить мобильный browser/PWA camera permission. Для нативного APK сначала
   понадобится отдельная актуальная Android-сборка и установка.

Не закрытые старые пункты ручной приёмки из 09–16.09:

- отсутствие красной плашки в четырёх типах чатов;
- корректные метки гражданства;
- обновлённая форма заказа и два поля веса;
- финансы и главная worker;
- splash Android на реальном телефоне.

---

## 9. Открытый backlog и принятые ограничения

Порядок кабинетов остаётся тем же:

1. **P1-11** — citizenship filter ошибочно скрывает РФ-заказы до загрузки
   worker profile cache.
2. **P1-10** — отклонённый отклик worker пропадает из всех вкладок.
3. **P1-8** — API-форма создания не загружает тип/контакты client; цена всегда
   по ставке физлица, также блокируется «logist создаёт заказ за client».
4. **P2-18** — чистка деталей заказа; нужен ввод пользователя по полям и
   порядку для ролей.
5. **P2** — confirm для destructive actions; moderation worker спрятана в
   профиле logist; мёртвая support-кнопка client; скрывать обработанные
   отклики у logist.
6. **P3** — рейтинг 4.7 обрезается до 4; валидация client profile; legacy
   `lib/client`, `lib/worker`, `lib/logist`.

Парковано до ответов пользователя:

- **P0-3, оценка «С нареканиями»**: направление `complaint`, ориентир −1 без
  срыва; ещё нужны окончательное значение и решение server endpoint vs demo.
- **Messenger v2**: значение «прочитано» в group chat (хотя бы один vs все) и
  polling interval vs WebSocket.

Отдельные решения:

- Android release keystore / Google Play сейчас не делать.
- `feature/crm-logist-city-visibility` и
  `release/crm-logist-city-visibility` не мержить: функциональность давно в
  main другими коммитами, ветки stale.
- `DESIGN_FREEZE.md` действует; визуальную систему не менять без согласования.
- Реальные персональные/паспортные/банковские данные всё ещё запрещены до
  закрытия legal/infrastructure P0. Проект — закрытое тестирование.

---

## 10. Активная архитектура и важные файлы

```text
CRM -> server-to-server GPM API -> PostgreSQL -> Flutter web/Android

Flutter entrypoint: lib/main.dart
Role screens:       lib/screens/**
Attendance UI:      lib/screens/attendance/order_attendance.dart
Flutter API client: lib/services/gpm_api_service.dart
Chat client:        lib/services/chat_service.dart
Display helpers:    lib/utils/order_display.dart
FastAPI backend:    app/app_orders_api.py
Actor backfill:     app/backfill_actor_codes.py
Production command: uvicorn app.app_orders_api:app
Database:           PostgreSQL production, SQLite tests
```

Backend — единственный источник истины. Старые верхнеуровневые каталоги
`lib/client`, `lib/worker`, `lib/logist` — legacy, не использовать для новых
правок.

---

## 11. Как продолжать в новом чате

1. Полностью прочитать этот файл и continuation prompt.
2. Сделать только read-only audit: `git status --short --branch`,
   `git log -8 --oneline`, проверить четыре line-ending-only файла. Не
   сбрасывать их.
3. Назвать текущий документационный HEAD и подтвердить product release
   `71db271` + green run `36920664797`.
4. Первым практическим следующим шагом предложить ручную приёмку онлайн-табеля
   из раздела 8 либо, если пользователь сразу выбирает разработку, идти по
   согласованному backlog с P1-11.
5. Не менять код, не коммитить и не деплоить без новой конкретной задачи.
6. Для любой реализации: изучить текущий код, сохранить чужие изменения,
   добавить regression tests, прогнать backend + Flutter tests/analyze и
   запросить подтверждение перед production deploy.
7. Если нужна работа в установленном APK, сначала согласовать установку
   Android SDK/сборку; существующий APK не содержит онлайн-табель.

Не повторять уже завершённые деплои `1c9b26f`, `f5218eb`, `71db271` без
нового изменения или подтверждённого дефекта.

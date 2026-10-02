# Промпт для продолжения GPM Platform

Скопируй всё содержимое этого файла первым сообщением в новый чат.

---

Продолжаем проект **GPM Platform**: Flutter web/Android + FastAPI backend +
PostgreSQL + импорт заказов из CRM.

Сначала полностью прочитай в корне репозитория:

```text
PROJECT_HANDOFF_2026-10-01_QR_ATTENDANCE_PRODUCTION.md
```

Это главный источник истины, актуализированный 02.10.2026. Старые handoff-файлы нужны только
как история.

## Где остановились

- Production backend: `71db271`, общий workflow run `36920664797`, `success`.
- Production frontend: `d55d891 Add worker referral bonus promotion`, frontend
  workflow run `36992623441`, `success`.
- Проверено после deploy:
  `https://app-api.gpmbot.ru/health` → PostgreSQL/HTTP 200,
  `https://app-api.gpmbot.ru/attendance` → 200,
  `https://app.gpmbot.ru/` → 200.
- Документационный HEAD может быть новее `d55d891`: это коммит снапшота, его
  нужно назвать после `git log -1` и не деплоить отдельно.
- После push `d55d891` рабочее дерево было чистым, локальный `main` совпадал с
  `origin/main`.

## Что уже сделано

1. `1c9b26f`: исправлены карточки `Заявка №` без номера; сервер формирует title
   из server-owned номера и чинит затронутые записи на чтении. Backend deploy
   run `36896273264`, green.
2. `f5218eb`: на карточках всех ролей добавлен маркер
   `Опубликовано ДД.ММ.ГГГГ ЧЧ:ММ` из server `created_at`. Frontend deploy run
   `36901538422`, green.
3. `71db271`: production MVP онлайн-табеля.
4. `d55d891`: в кабинете исполнителя добавлена акция «Приведи друга» — карточка
   с подарком, 3 500 ₽ за 5 смен и 5 000 ₽ за 10 смен, адаптивное окно и
   Telegram-контакты `@GPMHRDaria` / `@GpmHREkaterina`. Frontend deploy run
   `36992623441`, green.

Онлайн-табель:

- assigned worker выпускает уникальный QR отдельно для прихода и ухода;
- challenge живёт ровно 60 секунд, одноразовый, новый QR инвалидирует старый;
- client-created заказ подтверждает только client-владелец после preview;
- logist/CRM заказ подтверждает представитель на объекте через публичный QR,
  получает 6 цифр, assigned worker вводит их в приложение;
- есть fallback с 8-символьным request code;
- табель показывает worker, приход, уход, статус и длительность;
- server хранит только hashes секретов, проверяет роли и пишет audit events;
- таблицы: `gpm_app_order_attendance`,
  `gpm_app_attendance_challenges`, migration `0006_order_attendance`;
- UI: `lib/screens/attendance/order_attendance.dart`;
- API/backend: `app/app_orders_api.py`, client methods в
  `lib/services/gpm_api_service.dart`.

Перед последним релизом прошли: 61 backend test (1 skipped), 44 Flutter tests,
`flutter analyze`, web release build и Wasm dry run.

Android SDK на текущей машине отсутствовал, поэтому новый APK не собирался.
Старые APK автоматически не обновлены и не имеют нового UI. Web/PWA production
обновлён. Release keystore/Google Play по решению пользователя не делать без
отдельного запроса.

## Важные значения и решения

Номер `L1-180926-2` означает: actor — logist №1, публикация 18.09.2026,
вторая публикация этого logist в тот московский день. Суточный счётчик
сбрасывается отдельно для каждого actor. Дата в номере — дата публикации, не
дата работ. Для client используется `C`.

Обычный чат заказа называется по title заказа (`Заявка № L…/C…`), support —
`Поддержка GPM`.

Прямого SSH к production нет: он есть только у GitHub Actions. Deploy — через
`.github/workflows/deploy-production.yml`. В последней сессии `gh` CLI в PATH
не был найден; workflow запускался безопасным GitHub REST dispatch через
`git credential fill`, без вывода token. Любой новый deploy — только после
явного подтверждения пользователя.

## Первый ответ и дальнейшие действия

1. Сделай read-only audit:
   `git status --short --branch` и `git log -8 --oneline`. Назови фактический
   HEAD.
2. Подтверди production: backend `71db271`, run `36920664797`; frontend
   `d55d891`, run `36992623441`; оба green. Не запускай повторный deploy.
3. Предложи начать с ручной приёмки табеля:
   - client-created check-in/check-out;
   - logist/CRM guest QR → 6 digits → worker;
   - expired/replaced QR;
   - fallback 8-character code.
4. Если пользователь выбирает новую разработку, backlog:
   `P1-11 → P1-10 → P1-8 → P2-18 → P2 → P3`.
5. P0-3 «С нареканиями» и messenger v2 паркованы до ответов пользователя.
6. Stale CRM branches
   `feature/crm-logist-city-visibility` /
   `release/crm-logist-city-visibility` не мержить.
7. Основную CRM никогда не трогать без отдельного предварительного явного
   согласования пользователя. Задача по GPM, работа с импортированными
   CRM-заявками или упоминание CRM не являются разрешением. Без такого
   согласования не менять код, конфигурацию, схему/данные БД, интеграционные
   скрипты или интерфейс основной CRM и не выполнять её deploy. В каждый новый
   handoff-снапшот и continuation prompt обязательно переносить это правило и
   отдельно записывать, затрагивалась ли основная CRM. В сессии 01.10.2026
   основная CRM не изменялась и не деплоилась.
8. Не менять код GPM, не коммитить и не деплоить, пока пользователь не даст новую
   конкретную задачу. Спроси, начинаем ли с ручной приёмки онлайн-табеля или с
   P1-11.

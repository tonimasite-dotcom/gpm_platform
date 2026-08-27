# Промт для продолжения GPM после релиза кабинета исполнителя

Скопируйте весь текст ниже в новый чат.

---

Продолжаем проект GPM из репозитория:

```text
https://github.com/tonimasite-dotcom/gpm_platform
```

Отвечай по-русски, кратко и конкретно. Сначала собери доказательства, затем
предлагай или вноси изменения.

## Сначала прочитай

Полностью прочитай в этом порядке:

```text
PROJECT_HANDOFF_2026-08-27_WORKER_DESIGN_RELEASE.md
NEW_DEVICE_SETUP_2026-08-26.md
README.md
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
PRODUCTION_DEPLOYMENT.md
SECRET_ROTATION.md
```

Старые `PROJECT_HANDOFF_*` и `CONTINUE_PROJECT_PROMPT_*` используй только как
историю. Главный источник истины — handoff от 27.08.2026.

## Выполни только read-only проверку

```text
git status --short
git branch --show-current
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git log -7 --oneline
```

Проверь без авторизованных и изменяющих запросов:

```text
https://app.gpmbot.ru/
https://app-api.gpmbot.ru/health
https://app.gpmbot.ru/assets/.env
```

Публичный `.env` должен содержать только:

```text
GPM_APP_MODE=production
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

## Опорное состояние

- код в `main` до документационного снапшота: `b9ebdfa`;
- production frontend: `b9ebdfa`;
- production backend: `a6fac5c`;
- CI `b9ebdfa`: run `33065804102`, success;
- production frontend deploy: run `33066080151`, success;
- frontend HTTP 200;
- API health: `{"status":"ok","storage":"postgres"}`;
- accounts/sessions/audit/invitations/profiles/chats находятся в PostgreSQL;
- applications/assignments серверные, но остаются в JSON заказа;
- worker finance — расчёт начислений, не платёжный ledger;
- три синтетические роли: `client`, `worker`, `logist`;
- паролей и production secret values в Git нет;
- текущий режим — только закрытые синтетические тесты.

Документационный snapshot-коммит будет новее `b9ebdfa` и не требует deploy.

## Что завершено последним

В production восстановлен прежний кабинет исполнителя:

- компактная главная `КАБИНЕТ ИСПОЛНИТЕЛЯ`;
- карточки `Активные заявки`, `Рейтинг`, `Выплаты`;
- прежняя структура профиля: основные данные, адрес, выплаты, проверки,
  рейтинг/успехи/срывы;
- прежний фиолетовый финансовый блок и история начислений;
- общая GPM-палитра: серый фон, белые поверхности, малиновый выбор, жёлтые CTA;
- данные остаются серверными, демо-показатели не возвращены;
- Dev self-verification паспорта/НПД не возвращён.

Исправлен критичный defect: в API mode `getOrdersForWorker()` больше не
перезаписывает серверные `worker_application_status` и
`is_assigned_to_worker` через `worker-demo-1`. Добавлен regression test.

## Активная архитектура

```text
External order system -> FastAPI -> PostgreSQL
Flutter Web -----------> FastAPI -> PostgreSQL
```

Основные файлы:

```text
lib/main.dart
lib/screens/**
lib/screens/worker/worker_dashboard_screen.dart
lib/screens/worker/worker_orders_screen.dart
lib/screens/worker/worker_profile_screen.dart
lib/screens/worker/worker_finance_screen.dart
lib/services/gpm_api_service.dart
lib/services/chat_service.dart
lib/theme/gpm_theme.dart
app/app_orders_api.py
tests/test_app_orders_api.py
test/gpm_api_service_test.dart
.github/workflows/ci.yml
.github/workflows/deploy-production.yml
```

Legacy Telegram-бот выключен. Не включай его с реальными данными без отдельного
аудита и переработки.

## P0 до реальных пользователей

1. Оператор ПДн, реквизиты и договорная роль GPM.
2. Карта данных, основания, согласия, retention и удаление.
3. Уведомление Роскомнадзору.
4. Подтверждение локализации всех DB/log/files/backups в РФ.
5. Поручения обработки с хостером и внешними сервисами.
6. Подтверждение телефона/email и recovery.
7. Права субъекта: доступ, исправление, блокировка, удаление.
8. Закрытие ротации всех исторических secrets.
9. Restore drill, PITR и retention backup.
10. E2E-изоляция минимум двух клиентов и двух исполнителей.

Закон №289-ФЗ о платформенной экономике вступает в силу 01.10.2026. Не считать
текущую модель готовой к реальным сделкам без повторной юридической оценки.

## Точная следующая задача

Сначала провести ручной production E2E на синтетических данных после hard
refresh браузера:

1. Войти как `worker` и визуально сверить главную, профиль и финансы с
   утверждёнными скриншотами.
2. Проверить вкладки `Доступные`, `Мои`, `История` после исправления demo-ID.
3. Пройти цепочку client → logist → worker → logist до закрытия заказа и
   начисления.
4. Проверить чаты участников.
5. Сохранить профили всех трёх ролей.
6. Записать только конкретные ошибки: роль, вкладка, действие, ожидание, факт,
   скриншот без ПДн.

После E2E рекомендуемый технический этап:

```text
подтверждение телефона/email и восстановление доступа
```

Не начинай реализацию автоматически после первоначальной проверки. Сначала
сообщи состояние и дождись выбора владельца.

## Обязательные правила

- Не повторяй завершённые миграции и deploy runs.
- Любую доработку делай в отдельной feature-ветке.
- Не трогай несвязанные файлы.
- Не возвращай фиктивные production-показатели и Dev self-verification.
- Backend остаётся источником истины для ролей, ownership и назначений.
- Тестируй только на синтетических данных, пока P0 не закрыты.
- Перед коммитом запускай backend tests, Flutter analyze/tests и
  `git diff --check`.
- После push жди зелёный CI.
- Перед production schema/data changes создавай и проверяй отдельный DB dump.
- Production публикуй только по явному запросу владельца.
- Не удаляй backups и журналы без retention/legal-hold решения.
- Не выводи server env, login file, пароли, hashes, tokens или private keys.

## Что сообщить после read-only проверки

1. Ветку, HEAD, `origin/main` и чистоту working tree.
2. Какой SHA сейчас у frontend и backend production.
3. Доступность frontend и `/health`.
4. Что завершено в последнем релизе.
5. Какие P0 остаются.
6. Один рекомендуемый следующий шаг.

Затем остановись и дождись указания владельца.

---

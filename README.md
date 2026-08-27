# GPM Platform

Прототип платформы GPM: Flutter web/Android-клиент, FastAPI API и PostgreSQL.

> **Текущий статус:** только закрытое тестирование на синтетических данных.
> Нельзя вводить реальные ФИО, паспортные/банковские данные, адреса и переписку.
> Публичный пилот допустим только после закрытия P0 из
> `PROJECT_AUDIT_2026-08-25.md` и `LEGAL_READINESS_RU.md`.
>
> Текущий production frontend: `b9ebdfa`, опубликован 27.08.2026.
> Текущий production backend: `a6fac5c`, опубликован 26.08.2026.
> Полная точка продолжения:
> `PROJECT_HANDOFF_2026-08-28_CRM_PUBLICATION_RECOVERY.md`.
> Промт нового чата:
> `CONTINUE_PROJECT_PROMPT_2026-08-28_CRM_PUBLICATION_RECOVERY.md`.
> Настройка нового устройства: `NEW_DEVICE_SETUP_2026-08-26.md`.

## Архитектура

Единственным источником истины для production должен быть backend GPM:

```text
CRM (order data only) -> GPM backend -> PostgreSQL -> GPM applications
```

Bitrix24 не является ядром потока заказов. Legacy Telegram-бот в `main.py` по
умолчанию выключен и не является частью активной архитектуры. Публикация
заявок, назначения, статусы и чаты должны работать полностью внутри GPM без
Telegram, других мессенджеров и социальных сетей. Правило зафиксировано в
`INDEPENDENT_PLATFORM_ARCHITECTURE.md`, контракт импорта заявок — в
`CRM_APP_PUBLICATION.md`.

Активная backend-авторизация использует таблицы accounts/sessions/audit. При
первом запуске совместимой миграции существующие три конфигурационные роли
однократно импортируются с `scrypt`-хешированием паролей. Порядок безопасного
перехода и отката описан в `DB_ACCOUNTS_MIGRATION.md`. Публичная регистрация и
recovery не открыты. Закрытая регистрация по одноразовым приглашениям описана в
`INVITE_REGISTRATION.md`.

Production также использует серверные profiles, dashboards, chats и
ролевые applications/assignments. Финансы исполнителя считаются по завершённым
заказам. Это учёт начислений, а не платёжный ledger.

В `app/config.yml` хранятся только placeholders. Реальные значения задаются
переменными окружения сервера либо в игнорируемом `app/config.local.yml`.
Исторические секреты из `SECRET_ROTATION.md` должны быть отозваны и заменены.

## Режимы Flutter

Публичный asset `.env` не является хранилищем секретов. Допустимы только режим
и URL API:

```text
GPM_APP_MODE=demo
```

или:

```text
GPM_APP_MODE=api
GPM_APP_API_URL=http://localhost:8081
```

`production` эквивалентен API-режиму с более строгой конфигурацией. В asset
нельзя помещать токены, пароли и ключи внешних сервисов.

## Demo

The demo is intended to be continuously available through GitHub Pages:

```text
https://tonimasite-dotcom.github.io/gpm_platform/
```

Деплой выполняет `.github/workflows/deploy-demo.yml`; workflow всегда создаёт
явную конфигурацию `GPM_APP_MODE=demo` и не принимает произвольный секретный
`.env`.

Публикация:

1. Изменения попадают в `main`.
2. GitHub Actions выполняет `pub get`, анализ, widget-тесты и release-сборку.
3. Артефакт `build/web` публикуется в GitHub Pages.

В настройках репозитория Pages source должен быть `GitHub Actions`.

## Локальная проверка

Требуются Flutter `3.38.5` и Python `>=3.10`.

```powershell
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
python -m pip install -r requirements-api.lock
python -m unittest discover -s tests -p "test_*.py" -v
```

На Windows release web-сборку лучше выводить в ASCII-путь: shader compiler
Flutter может не записать артефакт в каталог с кириллицей.

## Перед реальным пилотом

Технические блокеры и результаты проверок описаны в
`PROJECT_AUDIT_2026-08-25.md`, правовая матрица — в `LEGAL_READINESS_RU.md`.
DB-backed accounts/sessions/audit, invite registration и серверные кабинеты уже
опубликованы. До первого реального пользователя всё ещё обязательны
подтверждение контактов/recovery, оператор и документы ПДн, verification,
проверка исторических журналов, восстановление из backup и остальные P0.

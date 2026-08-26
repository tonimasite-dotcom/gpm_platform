# Промт для продолжения GPM в новом чате

> **Не использовать для нового продолжения.** Актуальный промт:
> `CONTINUE_PROJECT_PROMPT_2026-08-26_ROLE_WORKSPACES.md`.

Скопируйте текст ниже в новый чат целиком.

---

Продолжаем проект GPM из существующего локального репозитория:

```text
C:\Users\Юра\Desktop\gpm_platform\gpm_platform
```

GitHub:

```text
https://github.com/tonimasite-dotcom/gpm_platform
```

Сначала полностью прочитай главный актуальный handoff:

```text
PROJECT_HANDOFF_2026-08-25_PRODUCTION_RELEASE.md
```

Затем прочитай связанные актуальные документы:

```text
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
README.md
PRODUCTION_DEPLOYMENT.md
```

Старые `PROJECT_HANDOFF_*` и `CONTINUE_PROJECT_PROMPT_2026-08-21.md` используй
только как историю. Они содержат уже отменённое состояние с общим
`admin/admin` и не должны определять дальнейшие действия.

После чтения сначала выполни только read-only проверки:

```text
git status --short
git branch --show-current
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git log -5 --oneline
```

Потом read-only проверь:

```text
https://app.gpmbot.ru/
https://app-api.gpmbot.ru/health
```

Не меняй код, сервер, данные, GitHub или production, пока не сообщишь мне
фактическое состояние и я не выберу следующую задачу.

Опорная точка:

- опубликованный frontend/backend release:
  `efec81f2711c9a02b67dda7b25e28966ccb31dd9`;
- коммит со снапшотом будет более новым документационным потомком, поэтому не
  считай расхождение только на handoff-файлы причиной для redeploy;
- frontend: https://app.gpmbot.ru/;
- API: https://app-api.gpmbot.ru/;
- health: `{"status":"ok","storage":"postgres"}`;
- production — только закрытое тестирование на синтетических данных;
- тестовых заказов в PostgreSQL: `0`;
- отдельные переходные username: `client`, `worker`, `logist`;
- у каждой роли свой случайный надёжный пароль;
- `admin/admin` намеренно отключён и должен получать `401`;
- пароли находятся только на сервере в `/root/gpm-app-env` и закрытой копии
  `/root/gpm-app-login.txt`, не в Git;
- не выводи server env, пароли, токены, private key или GitHub secrets в чат;
- если реквизиты потребуется восстановить, сначала запроси явное разрешение и
  копируй их напрямую в защищённый буфер/хранилище без вывода в журнал;
- localhost CORS для `localhost:8090` и `127.0.0.1:8090` опубликован;
- backend использует PostgreSQL и versioned venv;
- штатный будущий deploy: GitHub Actions `Deploy production`, target `all`;
- не запускай deploy без моего явного запроса;
- не удаляй backups и журналы.

Последние подтверждённые проверки:

- backend tests: 14/14;
- Flutter widget tests: 2/2;
- Flutter analyze: без замечаний;
- release web build: успешно;
- CI jobs backend/flutter: успешно;
- все три входа через публичный HTTPS: успешно;
- `admin/admin`: отклонён;
- публичный JS совпал с release-артефактом по SHA-256;
- nginx и backend service активны;
- CORS с посторонним origin отклоняется.

Важные незавершённые вопросы:

1. Это ещё не приложение для реальных пользователей и ПДн. До пилота закрыть
   P0 и правовые блокеры из audit/legal документов.
2. Нужны DB-backed регистрация/accounts, RBAC, audit trail, recovery,
   блокировка и revocation вместо трёх конфигурационных accounts.
3. Нужны серверные profiles, applications, assignments, chat и ledger/payment,
   миграции, backup/PITR и E2E изоляции.
4. Владелец должен предоставить реквизиты оператора ПДн, бизнес-модель,
   договорную схему, сроки хранения и сведения по инфраструктуре/получателям.
5. Нужно решить DaData или Яндекс до включения реальных адресных подсказок.
6. Нужны единый словарь статусов, desktop/deep-link UX и accessibility audit.
7. Legacy Telegram-бот должен оставаться выключенным.

Правила работы:

- отвечай по-русски и веди работу понятными короткими этапами;
- не повторяй уже завершённый аудит, сброс заказов и production-публикацию;
- не используй реальные персональные данные для тестов;
- сначала диагностируй и показывай доказательства, затем меняй;
- изменения делай в отдельной ветке, не затрагивая чужие/несвязанные файлы;
- перед коммитом запускай подходящие backend/Flutter тесты, analyze,
  `git diff --check` и проверку workflow YAML;
- production публикуй только по моему явному запросу и с резервной копией,
  health/login/CORS проверками и готовым rollback;
- не называй production юридически готовым к открытому коммерческому запуску.

После проверок ответь мне:

1. текущая ветка, HEAD, `origin/main` и чистота working tree;
2. что сейчас реально работает онлайн;
3. какой release фактически работает в production;
4. что остаётся P0 до реальных пользователей;
5. какой один следующий безопасный продуктовый шаг ты рекомендуешь.

Затем остановись и дождись выбора следующей отдельной доработки.

---

# Промт для продолжения GPM

Скопируйте текст ниже в новый чат целиком.

---

Продолжаем GPM из репозитория:

```text
https://github.com/tonimasite-dotcom/gpm_platform
```

Сначала полностью прочитай:

```text
PROJECT_HANDOFF_2026-08-26_ROLE_WORKSPACES.md
NEW_DEVICE_SETUP_2026-08-26.md
README.md
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
PRODUCTION_DEPLOYMENT.md
```

Старые `PROJECT_HANDOFF_*` и `CONTINUE_PROJECT_PROMPT_*` используй только как
историю.

Сначала выполни только read-only проверки:

```text
git status --short
git branch --show-current
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git log -7 --oneline
```

Проверь без изменений:

```text
https://app.gpmbot.ru/
https://app-api.gpmbot.ru/health
```

Опорная точка:

- production frontend/backend: `a6fac5caa834ffe268e97e347063acaf9defdfc0`;
- production run: `32965029082`, success;
- CI run: `32964687097`, backend и Flutter success;
- backend service active, PostgreSQL health ok;
- личные кабинеты трёх ролей работают на серверных данных;
- DB accounts/sessions/audit, lockout, logout revocation и invite-only
  registration опубликованы;
- серверные profiles, dashboards, applications/assignments, chats и финансы
  исполнителя опубликованы;
- applications/assignments пока лежат в JSON заказа;
- финансы — расчёт начислений, не платёжный ledger;
- verification, подтверждение контактов и recovery не завершены;
- текущий режим — только закрытое тестирование на синтетических данных;
- username тестовых ролей: `client`, `worker`, `logist`;
- пароли и secrets в Git отсутствуют;
- не выводи в чат server env, login file, токены, hashes или private keys;
- документационный snapshot-коммит будет новее `a6fac5c` и не требует deploy.

Где остановились:

1. Убраны production-заглушки кабинета исполнителя.
2. Опубликованы реальные сводка, профиль, чаты и начисления.
3. Профили клиента и логиста подключены к backend.
4. Полный ролевой workflow заказов проходит backend-тест.
5. Production smoke-тест трёх ролей успешен.
6. Следующий шаг — ручной синтетический E2E всех вкладок и фиксация конкретных
   UX-ошибок.

После UX-проверки рекомендуемый технический этап: подтверждение телефона/email
и восстановление доступа.

Не считай проект готовым к реальным ПДн. До этого остаются оператор ПДн,
политика/согласия, уведомление РКН, договорная модель, права субъекта, recovery,
verification, restore drill, ротация исторических secrets и другие P0 из
handoff/legal документов.

Правила:

- отвечай по-русски, коротко и конкретно;
- не повторяй завершённые миграции и деплой;
- сначала покажи доказательства, потом меняй;
- используй отдельную feature-ветку;
- не трогай несвязанные файлы;
- тестируй только на синтетических данных;
- перед коммитом запускай backend tests, Flutter analyze/tests и
  `git diff --check`;
- перед изменением production БД создавай проверенный dump;
- production публикуй только по явному запросу владельца;
- не удаляй backups и журналы без решения по retention/legal hold.

После проверки сообщи:

1. ветку, HEAD, `origin/main` и чистоту working tree;
2. какой commit сейчас в production;
3. что реально работает онлайн;
4. что остаётся P0;
5. какой один следующий шаг рекомендуешь.

Затем остановись и дождись выбора задачи.

---

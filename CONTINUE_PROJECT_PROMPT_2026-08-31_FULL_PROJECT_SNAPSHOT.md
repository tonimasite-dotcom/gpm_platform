Продолжаем GPM Platform: Flutter web/Android, FastAPI и PostgreSQL,
`tonimasite-dotcom/gpm_platform`.

Первым делом полностью прочитай
`PROJECT_HANDOFF_2026-08-31_FULL_PROJECT_SNAPSHOT.md` в корне репозитория. Это
главный и актуальный источник истины. Для подробного журнала работ 31 августа
можно дополнительно открыть
`PROJECT_HANDOFF_2026-08-31_CRM_LIVE_DRAFT_EDITOR_PENDING.md`.

После чтения сделай только read-only проверку:

```text
git status --short --branch
git log --oneline --decorate -10
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
```

Ожидаемая точка:

- production backend и `main`: `7024d76`;
- production frontend: `8de928f`;
- CRM ownership, slash IDs и определение города из адреса уже выпущены и
  проверены;
- CRM-заявку видит и публикует только назначенный логист GPM;
- другой/частный логист CRM-заявку не видит и создаёт свои заказы в приложении;
- исполнитель видит опубликованный заказ только по своему городу;
- адрес скрыт от исполнителя до назначения;
- editor перед публикацией готов в `feature/edit-order-drafts`;
- функциональный коммит editor: `b3f85df`;
- локальные тесты и CI run `33382173657` успешны;
- editor ещё не в `main` и не в production;
- регистрация логистов отложена.

Не сливай и не деплой editor без отдельного явного подтверждения владельца.
Если подтверждение будет дано, сначала проверь чистый Git и CI, затем сделай
fast-forward merge в `main`, дождись CI/demo и отдельно запусти production
workflow с `target=all`. После деплоя выполни post-deploy и ролевую проверку из
раздела 9 полного снапшота.

Соблюдай `DESIGN_FREEZE.md`. Не включай legacy Telegram. Не печатай secrets,
populated env, токены, SSH-ключ, пароли и приглашения. Не используй реальные
персональные данные. Локальный Chrome против production API запускай только на
порту `8090`.

В первом ответе кратко назови фактическую ветку/HEAD, `main`, production и
незавершённый шаг. Затем дождись запроса владельца.

Продолжаем GPM Platform: Flutter web/Android, FastAPI, PostgreSQL и CRM.
Репозиторий: `tonimasite-dotcom/gpm_platform`.

Сначала полностью прочитай:

```text
PROJECT_HANDOFF_2026-09-01_FULL_PROJECT_SNAPSHOT.md
PROJECT_HANDOFF_2026-09-02_POST_RELEASE_FULL_BACKUP.md
```

Второй файл — актуальное пост-релизное продолжение первого. Промежуточный
`PROJECT_HANDOFF_2026-09-02_SESSION_CONTINUATION_SNAPSHOT.md` хранит историю до
релиза, но не является текущей точкой состояния.

Затем выполни только read-only Git-проверку:

```text
git status --short --branch
git log --oneline --decorate -10
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
```

Ожидается:

- ветка `main`;
- функциональный production commit `8d7e283` уже входит в `main`;
- поверх него может находиться более новый документационный backup-коммит;
- `main` синхронизирован с `origin/main`;
- рабочее дерево чистое.

Production backend и frontend развёрнуты из:

```text
8d7e283d93e1ab87ace43a0181959594c716a510
```

Релизы:

```text
CI run #39:          33629007587 -> success
Demo run #49:        33629255446 -> success
Production run #13:  33629518564 -> attempt #2 success, target=all
```

Attempt #1 production run упал до изменения сервера на внешнем
`git fetch origin main`; attempt #2 успешно развернул оба компонента.
Post-deploy подтверждены PostgreSQL health, frontend HTTP 200 и безопасный
публичный `.env`.

В production уже доступны:

- досрочное завершение поиска при наличии хотя бы одного подтверждённого
  исполнителя GPM;
- один канонический чат на заявку;
- исправление chat IDs с CRM-номерами вида `001/26`;
- заголовок `Заявка № 001/26`;
- support-сигнал в том же чате без второго thread;
- «Набор исполнителей завершен» вместо счётчика у откликнувшегося исполнителя;
- выбор и server-side фильтрация `РФ / Не РФ`.

Не повторяй commit, merge или deploy. Следующая точка — ручная проверка после
hard refresh на синтетических аккаунтах:

1. для `001/26` у исполнителя один чат с правильным заголовком;
2. чат открывается без `Bad state: Not Found`;
3. сообщения видят исполнитель и назначенный логист;
4. откликнувшийся исполнитель не видит `1/2`, а видит завершённый набор;
5. RF-заказ виден только RF-исполнителю совпадающего города;
6. non-RF заказ — только non-RF исполнителю совпадающего города;
7. досрочное закрытие набора сохраняет назначенного исполнителя и блокирует
   новые отклики.

При проблеме сначала запиши роль, order ID, экран и точный текст. Не удаляй
старые chat rows и не меняй production вручную. Любое исправление делать новой
feature от актуального `main`.

Соблюдай `DESIGN_FREEZE.md`, не включай legacy Telegram, не используй реальные
персональные данные и не выводи secrets. Новый production deploy допустим
только после отдельной явной команды владельца.

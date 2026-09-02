Продолжаем GPM Platform: Flutter web/Android, FastAPI, PostgreSQL и CRM.
Репозиторий: `tonimasite-dotcom/gpm_platform`.

Сначала полностью прочитай два файла в таком порядке:

```text
PROJECT_HANDOFF_2026-09-01_FULL_PROJECT_SNAPSHOT.md
PROJECT_HANDOFF_2026-09-02_SESSION_CONTINUATION_SNAPSHOT.md
```

Второй документ — обязательное продолжение первого и содержит факты сессии
2 сентября.

Затем выполни только read-only проверку:

```text
git status --short --branch
git log --oneline --decorate -10
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
git diff --stat
git diff --check
```

Ожидаемое состояние на момент создания handoff:

```text
branch:       feature/unified-order-chat-citizenship
HEAD:         05118c40ef8b0b16c664071ec4967dc3d5e2a0e6
main:         05118c40ef8b0b16c664071ec4967dc3d5e2a0e6
origin/main:  05118c40ef8b0b16c664071ec4967dc3d5e2a0e6
working tree: dirty intentionally
```

Production backend/frontend уже развёрнуты из `05118c4`. Успешный production
run #12: `33610459820`, `target=all`. Health возвращает
`status=ok, storage=postgres`, frontend отвечает HTTP 200.

Commit `05118c4` реализует уже выпущенное досрочное закрытие набора: назначенный
логист после подтверждения хотя бы одного исполнителя может перевести
`PROCESSED` в `IN_PROCESS`, сохранить подтверждённых исполнителей и отклонить
оставшиеся pending-отклики.

Текущая feature ещё НЕ закоммичена и НЕ выпущена. В рабочем дереве готовы:

- исправление `Bad state: Not Found` для chat ID с CRM-номером `001/26`;
- `{thread_id:path}` для всех chat endpoints;
- один канонический чат на заявку;
- заголовок CRM-чата `Заявка № 001/26`;
- старые дублирующие chat rows скрыты, но не удалены;
- support помечает тот же чат, не создавая второй;
- после отклика исполнитель видит «Набор исполнителей завершен» вместо
  внутреннего счётчика мест;
- выбор гражданства `РФ / Не РФ`;
- server-side фильтрация доступных заказов по городу и гражданству;
- совместимость с legacy `every/any` и CRM-маркерами.

Локальные проверки уже прошли:

```text
flutter test --no-pub                    -> 11 passed
python -m unittest tests.test_app_orders_api -> 36 passed, 1 skipped
flutter analyze --no-pub                 -> No issues found
git diff --check                         -> exit 0
```

Не восстанавливай и не перезаписывай dirty working tree: это готовая
реализация. Сначала просмотри diff. Не создавай новую feature.

Commit/push/deploy выполняй только по явной команде владельца. Предлагаемое
сообщение commit:

```text
Unify order chats and restore citizenship filtering
```

После будущего релиза вручную проверь на синтетических данных:

1. для `001/26` у исполнителя и логиста один чат с одинаковым ID;
2. заголовок `Заявка № 001/26`;
3. чат открывается без Not Found и сообщения проходят в обе стороны;
4. support не создаёт отдельный чат;
5. откликнувшийся исполнитель видит «Набор исполнителей завершен»;
6. RF-заказ видит только RF-исполнитель совпадающего города;
7. non-RF заказ видит только non-RF исполнитель совпадающего города;
8. отдельно желательно проверить выпущенное досрочное закрытие набора.

Соблюдай `DESIGN_FREEZE.md`, не включай legacy Telegram, не используй реальные
персональные данные и не печатай secrets. Production deploy допустим только
после отдельного явного подтверждения.

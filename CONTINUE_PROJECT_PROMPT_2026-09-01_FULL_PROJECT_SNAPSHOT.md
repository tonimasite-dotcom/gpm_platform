Продолжаем GPM Platform: Flutter web/Android, FastAPI, PostgreSQL и интеграция с
CRM, репозиторий `tonimasite-dotcom/gpm_platform`.

Первым делом полностью прочитай:

```text
PROJECT_HANDOFF_2026-09-01_FULL_PROJECT_SNAPSHOT.md
```

Это главный актуальный источник истины. Затем прочитай журнал последнего релиза:

```text
PROJECT_HANDOFF_2026-09-01_EDITOR_RELEASE_AND_CRM_VALIDATION.md
```

После чтения сделай только read-only проверку:

```text
git status --short --branch
git log --oneline --decorate -10
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
```

Ожидаемое состояние:

- editor-коммит `b3f85df` уже вошёл в `main`;
- production backend и frontend развёрнуты из `3f857c5`;
- production run #11 `33439488044` с `target=all` успешен;
- CI `33399321365` и demo `33438500662` успешны;
- `/health` возвращает `status=ok`, `storage=postgres`;
- CRM ownership, slash IDs, city fallback и editor уже в production;
- новый документационный commit может быть новее `3f857c5`, но повторно
  деплоить документацию не нужно;
- синтетическая CRM-заявка `001/26` успешно отправлена в GPM после исправления
  `min_time` с ошибочных 600 часов на корректное значение;
- точка остановки — ручная проверка editor и ролей для `001/26` внутри GPM.

Первое действие после проверки Git: спроси владельца, видна ли `001/26`
назначенному логисту в разделе «На модерации». Если видна, последовательно
проведи ручной сценарий:

1. назначенный логист редактирует одно поле и сохраняет;
2. после переоткрытия значение сохранено;
3. другой логист заявку не видит;
4. назначенный логист публикует;
5. editor после публикации исчезает;
6. исполнитель Москвы видит заказ, но не точный адрес;
7. исполнитель другого города заказ не видит;
8. при возможности частный логист и клиент проверяют собственные черновики.

Не создавай новую feature и не делай новый production deploy для editor: он уже
выпущен. Новый deploy, изменение CRM или исправление production допускаются
только после отдельного явного подтверждения владельца.

Если CRM снова покажет общий отказ публикации, не угадывай причину. Безопасно
получи только HTTP status/detail из Laravel warning-log CRM. Карта CRM:

```text
MobaXterm session: 5.183.191.222 (root)
web-root: /var/www/gruzpiter/data/www/ts.workstaffcrm.ru
publisher: app/Services/Order/GpmAppOrderPublisher.php
log: storage/logs/laravel-YYYY-MM-DD.log
```

В CRM `duration` и `min_time` — часы, допустимые GPM значения 1..24. Ставку
нельзя вводить в `min_time`. `loader_count` должен быть 1..100.

Соблюдай `DESIGN_FREEZE.md`. Не включай legacy Telegram. Не используй реальные
персональные данные. Не печатай populated env, tokens, пароли, invitation codes,
SSH keys или Authorization headers. Локальный Chrome против production API
запускай только на порту 8090.

В первом ответе кратко назови фактическую ветку/HEAD, production `3f857c5` и
незавершённый ручной тест `001/26`, затем продолжай с результата владельца.

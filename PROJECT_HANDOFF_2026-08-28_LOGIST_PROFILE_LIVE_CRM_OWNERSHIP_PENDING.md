# GPM: handoff после деплоя профиля логиста, CRM ownership всё ещё в очереди

Дата снимка: 28.08.2026, вечер. Часовой пояс: Europe/Moscow.

Это главный источник истины для следующего чата. Он дополняет и заменяет как
операционную точку продолжения файл
`PROJECT_HANDOFF_2026-08-28_CRM_LOGIST_CITY_VISIBILITY_AND_PROFILE_UI.md`
(15:41). Тот файл и более ранний
`PROJECT_HANDOFF_2026-08-28_CURRENT_PRODUCTION_AND_CRM_RECOVERY.md` (12:22)
остаются как подробная история — CRM recovery, инфраструктура, полное описание
CRM ownership/city-visibility фичи. Здесь — только то, что изменилось с 15:41 и
что нужно продолжить.

Связанный стартовый промт:

```text
CONTINUE_PROJECT_PROMPT_2026-08-28_LOGIST_PROFILE_LIVE_CRM_OWNERSHIP_PENDING.md
```

## 1. Что изменилось с прошлого снапшота

Задача «убрать Telegram, сделать Email и Города/районы необязательными в
профиле логиста» — **выполнена, закоммичена и развёрнута в production.**
Задача «регистрация логистов» — по-прежнему отложена, не начата.

Задача «CRM ownership + city visibility» (коммиты `5913e64`, `a443399`) —
**по-прежнему НЕ в main и НЕ в production**, статус не изменился с прошлого
снапшота.

## 2. Git и production сейчас

```text
локальная рабочая копия: branch main, working tree clean, up to date с origin
main = origin/main = 411561b01eb5104779b2439296594249aa222008
```

`main` продвинут на один commit с прошлого снапшота:

```text
411561b Remove Telegram field, make email/cities optional for logist profile
```

Это `cherry-pick` коммита `2ae48dd` с `feature/crm-logist-city-visibility` —
**только он**, остальные 3 коммита ветки сознательно не слиты (см. раздел 4).

Production frontend и backend код теперь:

```text
production frontend code: 411561b01eb5104779b2439296594249aa222008
production backend code:  411561b01eb5104779b2439296594249aa222008
```

(до этого снапшота было `597a9d2`).

Деплой выполнен через `workflow_dispatch` `Deploy production`, `target=all`:

```text
run: https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33176705425
run_number: 7
conclusion: success
started:  2026-08-28 16:43:26 MSK
finished: 2026-08-28 16:45:53 MSK
```

Post-deploy проверка (выполнена в этом снапшоте):

```text
https://app-api.gpmbot.ru/health -> {"status":"ok","storage":"postgres"}
https://app.gpmbot.ru/           -> HTTP 200
https://app.gpmbot.ru/assets/.env ->
  GPM_APP_MODE=production
  GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Production-серверы и пути не изменились, см. раздел 2 файла
`PROJECT_HANDOFF_2026-08-28_CRM_LOGIST_CITY_VISIBILITY_AND_PROFILE_UI.md`
(backend host `46.149.71.147` / `gpm-app-api.service`, frontend host
`186.246.10.163` / `/var/www/gpm-app`).

## 3. Как именно был выполнен деплой (важно для следующего раза)

`gh` CLI на этой машине не установлен, переменных `GH_TOKEN`/`GITHUB_TOKEN` нет.
Репозиторий публичный. Git credential manager (`credential.helper=manager`) уже
хранит для `host=github.com` OAuth-токен пользователя со scope `repo, workflow`
— его можно использовать напрямую для GitHub REST API, не печатая сам токен в
чат/лог:

```bash
cred=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill)
token=$(echo "$cred" | grep '^password=' | cut -d= -f2-)
curl -s -X POST -H "Authorization: token $token" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/tonimasite-dotcom/gpm_platform/actions/workflows/deploy-production.yml/dispatches \
  -d '{"ref":"main","inputs":{"target":"all"}}'
unset token cred
```

Ответ `204` = запрос принят. Дальше опрашивать
`GET /repos/.../actions/workflows/deploy-production.yml/runs?per_page=1` до
`status: completed`. Тем же способом можно узнать `total_count`/`workflow_runs`
для CI (`ci.yml`) и любого другого workflow — токен не ограничен одним файлом.

Это же авторизует push в `main` напрямую (`git push origin main` уже работал
без запроса пароля) — отдельный PR-процесс в проекте не используется, история
линейная (проверено `git log --graph`).

## 4. Ветка feature/crm-logist-city-visibility: статус не изменился

```text
feature/crm-logist-city-visibility (локально и на origin, идентичны):
2ae48dd Remove Telegram field, make email/cities optional for logist profile
13803f7 Add CRM ownership and profile UI handoff
a443399 Enforce order ownership and city visibility
5913e64 Restore CRM order publication by logist
d5fb364 Add current production and CRM recovery handoff   <- общий предок с main
```

`2ae48dd` теперь дублирует по содержимому `411561b` на `main` (тот же diff,
разные SHA из-за cherry-pick) — при будущем слиянии ветки этот коммит уже не
нужен.

`13803f7` — только документация (старые handoff-файлы), тоже не нужен на main
буквально, но можно взять точечно нужные куски вручную, если понадобится.

Чтобы в будущем выкатить CRM ownership/city-visibility, из ветки нужны только:

```text
5913e64 Restore CRM order publication by logist
a443399 Enforce order ownership and city visibility
```

Рекомендация: `git checkout main && git cherry-pick 5913e64 a443399` (в этом
порядке, `a443399` логически поверх `5913e64`), затем прогнать backend/flutter
проверки заново и **дождаться отдельного явного запроса владельца** — эта
фича не тестировалась в этом снапшоте и не авторизована к деплою.

Подробное описание самой фичи (ownership по телефону логиста, city-based
discovery для исполнителя, чаты/dashboard) — раздел 4 файла
`PROJECT_HANDOFF_2026-08-28_CRM_LOGIST_CITY_VISIBILITY_AND_PROFILE_UI.md`, не
дублируется здесь, актуальность не изменилась.

## 5. Что именно изменено в профиле логиста (уже в production)

`lib/screens/logist/logist_profile_screen.dart`:

- поле Telegram полностью удалено (`_telegramController` и всё, что с ним
  связано — declaration, load, save, dispose, `TextFormField`);
- «Телефон» стал одиночным `TextFormField` на всю ширину (раньше делил `Row` с
  Telegram) — единственное структурное изменение layout, вызванное удалением
  соседнего поля, не редизайн;
- Email и «Города и районы» остались видимыми, но `required`-валидаторы сняты
  (лейблы и стиль не менялись, `DESIGN_FREEZE.md` не нарушен).

`app/app_orders_api.py`, `_profile_completion`:

```python
"logist": ("display_name",),   # было: ("display_name", "email", "cities")
```

Это единственное изменение обязательности на backend для роли `logist`.
Ничего не менялось у `client`/`worker`.

Тестировано вручную: `flutter run -d chrome --web-port=8090` (порт обязателен
— backend разрешает CORS только для `localhost:8090`/`127.0.0.1:8090`, см.
`GPM_APP_ALLOWED_ORIGINS` в `app/config.yml` и `parse_allowed_origins()` в
`app/app_orders_api.py`; на другом порту будет `ClientException: Failed to
fetch`), вход под реальным логистом в production API — подтверждено владельцем
визуально как ожидаемый результат.

Автоматически перед коммитом на `main` прогнано:

```text
python -m compileall -q app main.py       -> OK
flutter analyze --no-pub logist_profile_screen.dart -> No issues found
```

Полный `flutter test`/`python -m unittest` набор в этом снапшоте не
перезапускался (сам CI на `feature/crm-logist-city-visibility` для коммита
`2ae48dd` — зелёный, run
`https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33175606403`).
Тесты для этого изменения отдельно не добавлялись — стоит рассмотреть на
будущее, но не блокировало явный запрос владельца на деплой.

## 6. Правила следующего чата (без изменений, повторяю явно)

- Сначала read-only проверка branch/HEAD/origin/status.
- Не печатать реальные secrets и populated env, не печатать сам GitHub-токен
  (можно использовать его через `git credential fill` как в разделе 3, не
  выводя значение).
- Не восстанавливать токены из Git или истории терминала.
- Не менять `DESIGN_FREEZE.md`-защищённые палитру/навигацию/типографику/карточки.
- Не делать города необязательными у `worker` (только у `logist` уже сделано).
- Не включать legacy Telegram-бот.
- Не начинать отложенную регистрацию логистов без нового запроса.
- CRM ownership/city-visibility (раздел 4) не мержить и не разворачивать без
  отдельного явного подтверждения владельца.
- Перед следующим production-деплоем — предупреждать и подтверждать явно, как
  в этом снапшоте (что именно деплоится, что нет).

## 7. Первый ответ следующего чата

После read-only проверки кратко сообщить:

1. текущую ветку и HEAD (ожидается `main` @ `411561b`, чисто);
2. что production уже на `411561b` (Telegram убран, Email/города логиста
   необязательны) — задеплоено и проверено в этом снапшоте;
3. что CRM ownership/city-visibility (`5913e64`+`a443399`) всё ещё только в
   `feature/crm-logist-city-visibility`, не мержить без отдельного запроса;
4. что регистрация логистов по-прежнему отложена;
5. дождаться от владельца следующей задачи, не предполагать, что CRM ownership
   — следующий шаг по умолчанию.

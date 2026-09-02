# GPM Platform: полный backup после релиза единого чата и гражданства

Дата: 02.09.2026. Часовой пояс: Europe/Moscow.

Этот документ — актуальное пост-релизное продолжение следующих источников:

```text
PROJECT_HANDOFF_2026-09-01_FULL_PROJECT_SNAPSHOT.md
PROJECT_HANDOFF_2026-09-02_SESSION_CONTINUATION_SNAPSHOT.md
```

При продолжении проекта сначала прочитать базовый полный снапшот 1 сентября,
затем этот backup. Промежуточный снапшот сессии сохраняется как история
состояния до релиза.

Новый стартовый промпт:

```text
CONTINUE_PROJECT_PROMPT_2026-09-02_POST_RELEASE_FULL_BACKUP.md
```

## 1. Итоговое состояние

Оба функциональных этапа сессии 2 сентября выпущены в production:

1. досрочное завершение поиска исполнителей логистом;
2. единый чат заявки, исправление CRM chat ID с `/`, представление
   откликнувшегося исполнителя и фильтрация по гражданству.

Текущая production-версия backend и frontend:

```text
8d7e283d93e1ab87ace43a0181959594c716a510
```

## 2. Git

Состояние перед созданием документационного backup-коммита:

```text
branch:       main
HEAD:         8d7e283d93e1ab87ace43a0181959594c716a510
main:         8d7e283d93e1ab87ace43a0181959594c716a510
origin/main:  8d7e283d93e1ab87ace43a0181959594c716a510
feature:      8d7e283d93e1ab87ace43a0181959594c716a510
working tree: clean
```

Функциональные коммиты:

```text
05118c4 Allow logists to close recruitment early
8d7e283 Unify order chats and restore citizenship filtering
```

Ветка `feature/unified-order-chat-citizenship` сохранена локально и в origin,
но продолжать работу нужно от актуального `main`.

Этот backup, новый prompt и обновление README будут отдельным
документационным коммитом поверх `8d7e283`. Его точный SHA нужно брать из
`git log -1`. Повторно деплоить документационный коммит не требуется:
production-код остаётся `8d7e283`.

## 3. Что вошло в `8d7e283`

### Исправление чата CRM-заявки

Chat ID включает order ID:

```text
chat-001/26-workerLogist
```

Все chat endpoints теперь используют `{thread_id:path}`:

```text
GET   /app-api/me/chats/{thread_id:path}
POST  /app-api/me/chats/{thread_id:path}/messages
POST  /app-api/me/chats/{thread_id:path}/support
PATCH /app-api/me/chats/{thread_id:path}/attention
```

Это устраняет `Bad state: Not Found` при открытии чата заявки `001/26`.

### Один чат на заявку

Для заказа создаётся и выдаётся один канонический чат:

- клиентский заказ: тип `clientWorker`;
- CRM/external заказ или заказ логиста: тип `workerLogist`;
- назначенные участники работают в одном thread;
- support выставляет `requires_attention` в этом же чате;
- отдельный support thread больше не создаётся.

Старые дублирующие rows не удалены и история не уничтожена. Backend скрывает и
не открывает неканонические threads. Автоматического слияния старых сообщений
не выполнялось; возможная миграция истории — отдельная будущая задача.

Для CRM/external заявки заголовок вычисляется динамически:

```text
Заявка № 001/26
```

### Представление откликнувшегося исполнителя

Если у исполнителя уже есть `worker_application_status` либо он назначен, его
карточка и детали заказа не показывают внутренний прогресс комплектации.

Вместо `1/2` показывается:

```text
Набор исполнителей завершен
```

Поиск остальных исполнителей у логиста при этом может продолжаться.

### Гражданство

В форму возвращён выбор:

```text
РФ
Не РФ
```

Историческая логика была найдена в commit `b3d240e`. Новая реализация добавляет
полную server-side проверку и явное значение `Не РФ`.

Backend нормализует:

```text
yes / ru / rf / russian        -> РФ
no / non_ru / non-rf / foreign -> Не РФ
every / any / пусто            -> без ограничения
```

Поддержаны CRM-маркеры `Только РФ` и `Только не РФ`.

Выдача доступного заказа исполнителю требует совпадения:

1. статуса `PROCESSED`;
2. города профиля;
3. гражданства профиля.

Прямой API-отклик повторно проходит ту же проверку. Уже назначенный
исполнитель сохраняет доступ к заказу независимо от последующего изменения
профиля.

## 4. Досрочное завершение набора из `05118c4`

Назначенный логист может завершить поиск до заполнения всех мест, если в GPM
подтверждён хотя бы один исполнитель.

Backend:

- переводит `PROCESSED` в `IN_PROCESS`;
- сохраняет подтверждённых исполнителей;
- отклоняет pending-отклики с `decision_reason=recruitment_closed`;
- прекращает новые отклики;
- сохраняет audit trail закрытия набора.

Это позволяет логисту добрать остальных людей во внешних каналах, не ломая
работу найденного через GPM исполнителя внутри заявки.

## 5. Проверки до merge

Локально перед commit:

```text
flutter test --no-pub                         -> 11 passed
python -m unittest tests.test_app_orders_api  -> 36 passed, 1 skipped
flutter analyze --no-pub                      -> No issues found
git diff --check                              -> exit 0
```

Пропущен только тест, требующий `GPM_TEST_POSTGRES_URL`; PostgreSQL-проверки
выполнены CI/production workflow.

CI feature-коммита:

```text
workflow:   CI
run number: 39
run id:     33629007587
head SHA:   8d7e283d93e1ab87ace43a0181959594c716a510
conclusion: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33629007587
```

## 6. Merge и demo

Feature была fast-forward включена в `main`, затем `main` отправлен в GitHub.

Demo:

```text
workflow:   Deploy demo
run number: 49
run id:     33629255446
head SHA:   8d7e283d93e1ab87ace43a0181959594c716a510
conclusion: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33629255446
```

## 7. Production release

```text
workflow:   Deploy production
run number: 13
run id:     33629518564
target:     all
head SHA:   8d7e283d93e1ab87ace43a0181959594c716a510
final:      attempt #2 success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33629518564
```

Attempt #1 завершился failure на backend step до изменения production:

```text
git fetch origin main
fatal: could not read Username for 'https://github.com'
fatal: expected flush after ref listing
```

Frontend deploy был пропущен после ошибки backend. Это был внешний сбой чтения
публичного GitHub remote, а не ошибка приложения. Тот же run был безопасно
перезапущен. Attempt #2 завершился `success`.

Post-deploy 02.09.2026 примерно в 16:34 MSK:

```text
https://app-api.gpmbot.ru/health -> {"status":"ok","storage":"postgres"}
https://app.gpmbot.ru/           -> HTTP 200
frontend Last-Modified           -> 02.09.2026 16:26 MSK
assets/.env                      -> GPM_APP_MODE=production
                                    GPM_APP_API_URL=https://app-api.gpmbot.ru
```

В публичном `.env` нет секретов.

## 8. Основные изменённые файлы релиза

```text
app/app_orders_api.py
lib/screens/chats/chat_conversation_screen.dart
lib/screens/chats/chat_threads_screen.dart
lib/screens/client/client_create_order_screen.dart
lib/screens/logist/logist_orders_screen.dart
lib/screens/orders/order_draft_edit_screen.dart
lib/screens/worker/worker_orders_screen.dart
lib/services/chat_service.dart
lib/services/gpm_api_service.dart
test/client_create_order_screen_test.dart
test/gpm_api_service_test.dart
test/order_draft_edit_screen_test.dart
test/worker_orders_screen_test.dart
tests/test_app_orders_api.py
README.md
```

## 9. Что проверить вручную сейчас

Перед проверкой сделать жёсткое обновление страницы, чтобы браузер получил
новый Flutter bundle.

### Чат заявки `001/26`

1. Войти назначенным исполнителем.
2. Открыть раздел чатов.
3. Убедиться, что для `001/26` виден ровно один чат.
4. Проверить заголовок `Заявка № 001/26`.
5. Открыть чат: ошибки `Bad state: Not Found` быть не должно.
6. Отправить синтетическое сообщение исполнителем.
7. Убедиться, что назначенный логист видит его в том же чате и может ответить.
8. При проверке поддержки убедиться, что второй чат не создаётся.

### Представление исполнителя

1. Открыть заявку, на которую исполнитель уже откликнулся.
2. Убедиться, что нет внутреннего счётчика `1/2`.
3. Проверить текст «Набор исполнителей завершен».
4. Убедиться, что рабочие действия внутри назначенной заявки доступны.

### Гражданство

1. Создать синтетический черновик `РФ`, опубликовать.
2. Проверить видимость RF-исполнителю совпадающего города.
3. Проверить отсутствие у non-RF исполнителя того же города.
4. Повторить наоборот для заявки `Не РФ`.
5. Не использовать реальные персональные данные.

### Досрочное закрытие набора

1. Создать заказ более чем на одного исполнителя.
2. Подтвердить одного исполнителя GPM.
3. Завершить поиск логистом.
4. Проверить переход в работу и сохранение назначенного исполнителя.
5. Проверить отсутствие новых откликов и отклонение pending.

## 10. Точка продолжения

Код уже закоммичен, отправлен и развёрнут. Не нужно повторять merge или deploy.
Следующее действие — получить от пользователя результаты ручной проверки
четырёх сценариев из раздела 9.

Если будет обнаружена проблема:

- сначала зафиксировать роль, order ID, экран и точный текст;
- проверить, сделал ли браузер hard refresh;
- не удалять старые chat rows;
- не менять production вручную в обход workflow;
- исправление делать новой feature от актуального `main`.

## 11. Ограничения

- Только синтетические данные до закрытия P0.
- Не вводить реальные ФИО, документы, банковские данные, адреса и переписку.
- Не печатать secrets, populated env, токены, пароли, invitation codes, SSH
  keys или Authorization headers.
- Не включать legacy Telegram bot.
- Соблюдать `DESIGN_FREEZE.md`.
- Не мигрировать старую историю chat threads без отдельного решения.
- Локальный Chrome против production API запускать только на порту `8090`.
- Следующий production deploy — только для нового функционального изменения и
  после явной команды владельца.

## 12. Цепочка актуальных коммитов

```text
a9a12b5  Add September 1 editor release snapshot
05118c4  Allow logists to close recruitment early
8d7e283  Unify order chats and restore citizenship filtering <- production code
next     post-release documentation backup                   <- no redeploy needed
```

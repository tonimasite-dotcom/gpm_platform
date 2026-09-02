# GPM Platform: полный снапшот проекта и точка продолжения

Дата: 02.09.2026. Часовой пояс: Europe/Moscow.

Это новый главный источник истины для продолжения проекта. Он объединяет
актуальные сведения из полного снапшота 1 сентября и пост-релизного backup
2 сентября. Старые handoff-файлы не удаляются и остаются историей.

Стартовый промпт нового чата:

```text
CONTINUE_PROJECT_PROMPT_2026-09-02_FULL_PROJECT_SNAPSHOT.md
```

## 1. Где остановились

Production backend и frontend успешно развёрнуты из функционального commit:

```text
8d7e283d93e1ab87ace43a0181959594c716a510
```

В production уже доступны:

- CRM ownership и редактор `NEW`-черновика;
- досрочное завершение поиска при наличии хотя бы одного подтверждённого
  исполнителя GPM;
- один канонический чат на заявку;
- поддержка CRM-номеров со слешем, включая `001/26`;
- заголовок CRM-чата `Заявка № 001/26`;
- support-сигнал в том же чате без отдельного канала;
- скрытие внутреннего счётчика комплектации после отклика исполнителя;
- выбор и серверная фильтрация `РФ / Не РФ`.

Текущая точка продолжения — ручная production-проверка этих новых сценариев
после жёсткого обновления браузера. Повторять commit, merge или deploy не нужно.

## 2. Git

Состояние до создания этого нового master-снапшота:

```text
branch:       main
HEAD:         1a2a2580010152833cc02e6759607b5615bfa618
main:         1a2a2580010152833cc02e6759607b5615bfa618
origin/main:  1a2a2580010152833cc02e6759607b5615bfa618
working tree: clean
```

Актуальная цепочка:

```text
3f857c5 Add complete August 31 project snapshot
a9a12b5 Add September 1 editor release snapshot
05118c4 Allow logists to close recruitment early
8d7e283 Unify order chats and restore citizenship filtering <- production code
1a2a258 Add September 2 post-release backup
next     this full project snapshot                         <- docs only
```

Сохранённые feature-ветки:

```text
feature/close-order-recruitment
feature/unified-order-chat-citizenship
```

Продолжать нужно от `main`. Документационный commit этого файла будет новее
production SHA; повторный production deploy для документации не требуется.

## 3. Production, CI и demo

Публичные адреса:

```text
frontend: https://app.gpmbot.ru/
backend:  https://app-api.gpmbot.ru/
health:   https://app-api.gpmbot.ru/health
```

Последний функциональный CI:

```text
CI run #39
id:         33629007587
head SHA:   8d7e283d93e1ab87ace43a0181959594c716a510
conclusion: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33629007587
```

Функциональный demo:

```text
Deploy demo run #49
id:         33629255446
head SHA:   8d7e283d93e1ab87ace43a0181959594c716a510
conclusion: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33629255446
```

Production:

```text
Deploy production run #13
id:         33629518564
target:     all
head SHA:   8d7e283d93e1ab87ace43a0181959594c716a510
attempt #1: failure до изменения production на внешнем git fetch
attempt #2: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33629518564
```

Attempt #1 не смог прочитать публичный GitHub remote. Backend и frontend тогда
не изменились. Безопасный rerun того же workflow успешно развернул оба
компонента.

Post-deploy подтверждено:

```text
/health      -> {"status":"ok","storage":"postgres"}
frontend     -> HTTP 200
assets/.env  -> GPM_APP_MODE=production
                GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Документационный commit `1a2a258` прошёл Deploy demo run #50:

```text
id:         33637335612
conclusion: success
URL:        https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/33637335612
```

Повторного production-деплоя документации не выполнялось.

## 4. Активная архитектура

```text
CRM -> server-to-server GPM API -> PostgreSQL -> Flutter web/Android
```

```text
Flutter entrypoint: lib/main.dart
Flutter screens:    lib/screens/**
Flutter API client: lib/services/gpm_api_service.dart
FastAPI backend:    app/app_orders_api.py
Production command: uvicorn app.app_orders_api:app
Database:           PostgreSQL
```

Backend GPM и PostgreSQL — источник истины по заказам, ownership, откликам,
назначениям, чатам и статусам. CRM — только внешний источник заявок.

Legacy Telegram (`main.py`, `app/handlers/**`, `app/services/**`) не относится к
активному production-потоку и не должен включаться как резервный канал. GPM
должна работать независимо от мессенджеров и социальных сетей.

Основные документы:

```text
INDEPENDENT_PLATFORM_ARCHITECTURE.md
CRM_APP_PUBLICATION.md
BITRIX24_INTEGRATION.md
PRODUCTION_DEPLOYMENT.md
DESIGN_FREEZE.md
```

## 5. Роли и права

### Клиент

- видит только собственные заказы;
- создаёт `NEW`-черновики;
- редактирует и публикует только собственный `NEW`;
- не видит CRM-заявки и чужие заказы;
- управляет откликами и завершением собственного заказа.

### Исполнитель

- обнаруживает только `PROCESSED` подходящего города и гражданства;
- до назначения не получает точный адрес и чувствительные контакты;
- не редактирует черновики;
- откликается только после повторной server-side проверки;
- после назначения сохраняет доступ к заказу, адресу, чату и завершению работ.

### Назначенный CRM-логист

- CRM передаёт `logist_phone`;
- телефон должен разрешаться ровно в один активный GPM-аккаунт;
- заказ закрепляется через `logist_account_id`;
- только назначенный логист видит, редактирует и публикует CRM-черновик;
- номер, источник и назначение через editor не меняются;
- после подтверждения хотя бы одного исполнителя может досрочно закрыть набор.

Другой логист не видит чужую CRM-заявку. Частный логист создаёт и обслуживает
собственные заявки. Явной сущности company membership пока нет; это отдельная
будущая задача.

## 6. Жизненный цикл заказа

```text
NEW          черновик / на модерации
PROCESSED    опубликован и принимает отклики
JUNK         отклонён
IN_PROCESS   набор закрыт, заказ в работе
DONE_PENDING ждёт подтверждения завершения
CONVERTED    завершён
```

Правила:

- редактирование рабочих полей возможно только в `NEW`;
- публикация переводит `NEW` в `PROCESSED`;
- PATCH опубликованных рабочих полей возвращает `409`;
- повторный CRM-import не стирает workflow, отклики и назначения;
- CRM order IDs со слешем используют `{order_id:path}`;
- досрочное закрытие требует хотя бы одного assigned worker;
- pending-отклики при закрытии отклоняются;
- назначенные исполнители продолжают работу внутри заявки.

## 7. CRM-контракт и заявка `001/26`

Обязательные данные CRM:

```text
logist_phone
order_data.order_number
order_data.completion_date.date
order_data.loaders.loader_count
order_data.info
```

Ограничения:

```text
order_data.hours     integer 1..24
order_data.min_time  integer 1..24
loader_count         integer 1..100
```

Если отдельный город пуст, backend пытается определить его из первой части
адреса. Неизвестный или неоднозначный телефон логиста отклоняется.

Синтетическая заявка `001/26`, CRM order id `56793`, сначала не отправлялась
из-за ошибочного `min_time=600`. В CRM `min_time` — часы, а ставка должна быть в
`workers_cost`. После замены на корректное значение пользователь подтвердил
успешную отправку.

Пользователь также подтвердил для `001/26`:

- назначенный логист видит заявку;
- заявка редактируется;
- после одобрения публикуется;
- исполнитель соответствующего региона может откликнуться.

К диагностике `min_time` без новой ошибки возвращаться не нужно.

## 8. Редактор черновика

Редактируются название, описание, город, дата/время, адрес, метро, количество
исполнителей, часы, гражданство, режим работы, смена, ставки/цены и
дополнительная информация.

Системные поля защищены. Изменение адреса очищает старые координаты. Дата должна
иметь timezone, быть минимум через 30 минут и не дальше 366 дней. Изменение
пишет audit event `order_draft_updated`.

## 9. Досрочное закрытие набора

Выпущено commit `05118c4`. Назначенный логист может закрыть поиск при одном или
более подтверждённом исполнителе, даже если мест больше.

Backend переводит заказ в `IN_PROCESS`, сохраняет assigned workers, отклоняет
pending с `decision_reason=recruitment_closed` и пишет audit trail. Люди,
найденные логистом вне GPM, не создаются в системе искусственно.

## 10. Единый чат заявки

Chat IDs с `/` поддерживаются маршрутами `{thread_id:path}` для conversation,
messages, support и attention.

Канонический thread:

- клиентский заказ — существующий тип `clientWorker`;
- CRM/external или заказ логиста — `workerLogist`;
- support ставит `requires_attention` в этом же чате;
- заголовок CRM-чата — `Заявка № {external_order_id}`.

Старые дублирующие rows не удалены, но скрыты и недоступны. Их сообщения не
сливались автоматически; возможная миграция истории требует отдельного
решения.

После собственного отклика исполнитель видит «Набор исполнителей завершен», а
не внутренний счётчик найденных людей.

## 11. Гражданство

Форма создания предлагает `РФ / Не РФ`. Editor сохраняет совместимость со
старыми `every/any` через вариант без ограничения.

```text
yes/ru/rf/russian         -> РФ
no/non_ru/non-rf/foreign  -> Не РФ
every/any/пусто           -> без ограничения
```

Поддержаны CRM-маркеры `Только РФ` и `Только не РФ`. RF-заказ доступен только
при `profile.nationality == true`, non-RF — при `false`. Проверка действует и
при прямом API-отклике. Назначение имеет приоритет над discovery-фильтром.

## 12. Аккаунты, профили и финансы

Авторизация использует PostgreSQL accounts/sessions/audit/invitations,
versioned scrypt и серверные сессии. После пяти ошибок вход блокируется на 15
минут. Публичная регистрация закрыта; роль задаётся одноразовым приглашением.

Исполнитель выбирает города и гражданство; доступны признаки ремней и
инструментов. Паспорт/НПД-поток реализован только для синтетических документов.
Приватные вложения хранятся вне web root в `GPM_APP_PRIVATE_UPLOAD_DIR`.

Финансы — расчёт начислений по завершённым заказам, не платёжный ledger.
Эквайринг, ККТ и автоматические выплаты не включены.

## 13. CRM-сервер и безопасная диагностика

```text
domains:  ts.workstaffcrm.ru, test.workstaffcrm.ru
IPv4:     5.183.191.222
web-root: /var/www/gruzpiter/data/www/ts.workstaffcrm.ru
```

```text
app/Services/Order/GpmAppOrderPublisher.php
app/Http/Controllers/Order/ManagerOrderController.php
resources/js/pages/app/orders/logist_orders/index.vue
storage/logs/laravel-YYYY-MM-DD.log
```

UI CRM скрывает detail backend и показывает общий toast. Причину читать только
из нормализованного status/detail в Laravel warning-log. Никогда не выводить
CRM `.env`, integration token, Authorization headers или реальные payloads.

## 14. Инфраструктура и deploy

```text
repository: https://github.com/tonimasite-dotcom/gpm_platform
backend:    46.149.71.147
checkout:   /opt/gpm/gpm_platform
service:    gpm-app-api.service
backups:    /opt/gpm/backups
frontend:   186.246.10.163
live:       /var/www/gpm-app
backups:    /opt/gpm/front-backups
workflow:   .github/workflows/deploy-production.yml
```

Production workflow запускается вручную только с `main`, targets: `all`,
`backend`, `frontend`. Backend создаёт Git bundle и versioned venv. Frontend
развёртывается атомарно с backup/rollback. PostgreSQL dump workflow не создаёт.

Каждый новый deploy требует явной команды владельца, чистого синхронного main,
успешных CI/demo и post-deploy health/frontend/config проверок.

## 15. Локальная разработка и тесты

```text
Flutter: 3.38.5
Dart SDK constraint: ^3.8.0
Python: >=3.10
FastAPI dependencies: requirements-api.lock
```

```powershell
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
python -m unittest discover -s tests -p "test_*.py" -v
```

Последний функциональный результат: 11 Flutter tests, 36 backend tests с одним
PostgreSQL-only skip, analyze без ошибок. Локальный Chrome против production
API запускать только на порту `8090`.

## 16. Безопасность и правовая готовность

Проект разрешён только для закрытого тестирования на синтетических данных.
Публичный реальный пилот заблокирован до закрытия P0:

- оператор ПДн, реквизиты, политики, согласия и РКН;
- contact verification и recovery;
- полный RBAC/admin audit;
- права субъекта, retention и удаление;
- backup/restore drill;
- договорная модель, платежи, НПД и возможная оценка ОРИ для чатов;
- проверка исторических логов и прежнего доступа.

Нельзя использовать реальные ФИО, документы, банковские данные, адреса и
переписку. Нельзя выводить или коммитить tokens, populated env, passwords,
hashes, invitation codes, SSH keys и Authorization headers. Legacy secrets из
`SECRET_ROTATION.md` считать подлежащими ротации.

Главные документы:

```text
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
SECRET_ROTATION.md
PRODUCTION_READINESS.md
WORKER_PROFILE_VERIFICATION.md
INVITE_REGISTRATION.md
DB_ACCOUNTS_MIGRATION.md
```

## 17. Дизайн

`DESIGN_FREEZE.md` действует. Без согласования нельзя менять палитру,
типографику, навигацию, общую компоновку, карточки, кнопки и утверждённые
кабинеты. Допустимы функциональные состояния в существующем визуальном языке.

## 18. Карта ключевых файлов

```text
README.md                                      краткий статус
app/app_orders_api.py                         активный FastAPI
lib/main.dart                                 Flutter entrypoint
lib/services/gpm_api_service.dart             API client
lib/services/chat_service.dart                chat client/demo
lib/screens/orders/order_draft_edit_screen.dart editor
lib/screens/chats/**                          чаты
lib/screens/client/**                         кабинет клиента
lib/screens/worker/**                         кабинет исполнителя
lib/screens/logist/**                         кабинет логиста
tests/test_app_orders_api.py                  backend regressions
test/**                                       Flutter tests
CRM_APP_PUBLICATION.md                        CRM-контракт
INDEPENDENT_PLATFORM_ARCHITECTURE.md          архитектурные правила
PRODUCTION_DEPLOYMENT.md                      deploy runbook
DESIGN_FREEZE.md                              ограничения дизайна
```

## 19. Что проверить в новом чате

Сначала сделать hard refresh production frontend.

1. У исполнителя для `001/26` ровно один чат.
2. Заголовок — `Заявка № 001/26`.
3. Чат открывается без `Bad state: Not Found`.
4. Синтетические сообщения видны исполнителю и назначенному логисту.
5. Support не создаёт второй thread.
6. Откликнувшийся исполнитель видит «Набор исполнителей завершен», не `1/2`.
7. RF-заказ видит только RF-исполнитель совпадающего города.
8. Non-RF заказ видит только non-RF исполнитель совпадающего города.
9. Досрочное закрытие набора сохраняет назначенного исполнителя, отклоняет
   pending и блокирует новые отклики.

Зафиксировать роль, order ID, экран и точный текст любого отклонения. Старые
chat rows не удалять. Production вручную не менять.

## 20. Порядок продолжения

1. Полностью прочитать этот файл.
2. Выполнить read-only Git-проверку.
3. В первом ответе назвать фактические branch/HEAD и production `8d7e283`.
4. Получить результаты ручной проверки пользователя.
5. Если всё работает — зафиксировать подтверждение без нового deploy.
6. Если есть дефект — создать новую feature от актуального `main`, добавить
   регрессию, пройти CI/demo и запрашивать deploy отдельно.

Не повторять уже завершённые merge/deploy и не возвращаться к исправленной
ошибке CRM `min_time=600` без новых фактов.

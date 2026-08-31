# GPM: релиз editor и проверка новой CRM-заявки

Дата: 01.09.2026. Часовой пояс: Europe/Moscow.

Этот журнал фиксирует работу после полного снапшота 31 августа: merge editor в
`main`, CI/demo, production deploy, post-deploy и диагностику первой новой
CRM-заявки. Общий источник истины:

```text
PROJECT_HANDOFF_2026-09-01_FULL_PROJECT_SNAPSHOT.md
```

## 1. Исходная точка

В начале работы текущая локальная копия была на устаревшей ветке
`feature/crm-logist-publication`. После `git fetch origin --prune` обнаружена
актуальная ветка `origin/feature/edit-order-drafts` на `3f857c5`.

Перед merge подтверждено:

- `origin/main` — `7024d76`;
- feature опережала `origin/main` ровно на три коммита;
- расхождения истории не было;
- `b3f85df` — функциональный editor-коммит;
- CI `33382173657` для `b3f85df` — success;
- Flutter tests — 7 passed;
- Flutter analyze — no issues.

Глобальный Python на Windows не содержал `fastapi`, поэтому локальный backend
unittest не импортировался. Авторитетные backend tests прошли в CI.

## 2. Merge и push

Выполнено два fast-forward:

```text
local main 92624b7 -> origin/main 7024d76
main       7024d76 -> feature/edit-order-drafts 3f857c5
```

Merge-коммит не создавался. Затем:

```text
git push origin main
7024d76..3f857c5 main -> main
```

Во время локального Flutter test были перегенерированы пять platform registrant
файлов только из-за line endings. Diff содержательно был пуст. Эти изменения
были точечно убраны перед merge; пользовательские изменения не затрагивались.

## 3. CI и demo

```text
CI
run:        33399321365
head SHA:   3f857c5
conclusion: success

Deploy demo
run:        33438500662
head SHA:   3f857c5
conclusion: success
```

## 4. Production deploy

После явного разрешения владельца запущен:

```text
workflow:   Deploy production
run number: 11
run id:     33439488044
ref:        main
target:     all
head SHA:   3f857c5
conclusion: success
```

Первый REST dispatch через Windows `curl` вернул HTTP 400 из-за формирования
JSON и не запустил workflow. Второй запрос через PowerShell `Invoke-WebRequest`
с `application/json` был принят с HTTP 204. GitHub credential находился только
в памяти процесса и не выводился.

Все шаги production job `Deploy all` успешны:

```text
Checkout main
Set up Flutter
Create public production config
Validate and build frontend
Validate backend
Configure verified SSH access
Deploy backend
Upload frontend artifact
Deploy frontend atomically
```

## 5. Post-deploy

```text
https://app-api.gpmbot.ru/health
-> status=ok, storage=postgres

https://app.gpmbot.ru/
-> HTTP 200

https://app.gpmbot.ru/assets/.env
-> GPM_APP_MODE=production
-> GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Локальный key `C:\tmp\gpm-production-github-actions`, указанный в старом
handoff, отсутствовал. Поэтому отдельный server-side автоматический role smoke
не запускался. Production workflow выполнил backend/frontend validation и
deploy через GitHub Secrets.

## 6. Новая CRM-заявка

Пользователь создал синтетическую заявку:

```text
CRM order id: 56793
order number: 001/26
date in CRM:  03.09.2026 14:30 Europe/Moscow
workers:      2
address:      Москва, синтетический тестовый адрес
```

При нажатии «Опубликовать в приложении» CRM показывала только общий toast:

```text
Не удалось опубликовать в приложении
```

## 7. Read-only диагностика CRM

Использована сохранённая MobaXterm-сессия:

```text
5.183.191.222 (root)
```

Подтверждено:

```text
host:       sad0a47f6.fastvps-server.com
OS:         Debian 10
panel:      FASTPANEL
runtime:    nginx + fp2-php74-fpm
web-root:   /var/www/gruzpiter/data/www/ts.workstaffcrm.ru
```

Ключевые файлы:

```text
app/Http/Controllers/Order/ManagerOrderController.php
app/Services/Order/GpmAppOrderPublisher.php
resources/js/pages/app/orders/logist_orders/index.vue
storage/logs/laravel-2026-08-31.log
```

Controller вызывает:

```php
(new GpmAppOrderPublisher())->publish($order, $logistPhone)
```

При false controller возвращает общий HTTP 500, а Vue `.catch()` показывает
общий toast. Publisher пишет исходные `status` и `body` ответа GPM в warning-log.

Laravel-log для повторных попыток `001/26` показал:

```text
production.WARNING: GPM app order publish failed
status: 400
detail: order_data.hours must be between 1 and 24
```

## 8. Причина

Read-only запрос к Eloquent для order id `56793` показал до исправления:

```text
order_number:    001/26
duration:        4
min_time:        600
loader_count:    2
completion_date: 2026-09-03 11:30:00 database timezone
city_filled:     false
address_filled:  true
```

CRM publisher:

```php
'min_time' => (int) ($order->min_time ?? $order->duration ?? 4),
'hours'    => (int) ($order->duration ?? $order->min_time ?? 4),
```

`min_time` активно используется CRM как число часов: в расчётах цены,
`addHours()`, deadline и label «Минимальный заказ». Ставка `600` была ошибочно
введена в поле минимальных часов. Поэтому интерфейс считал 720 000 рублей:

```text
600 рублей × 2 человека × 600 часов
```

Правильно:

```text
duration=4
min_time=4
workers_cost=600
loader_count=2
minimum cost=4 800 рублей
```

После исправления пользователь подтвердил успешную отправку заявки в GPM.

## 9. Что не менялось

- код GPM после production run #11;
- код CRM;
- CRM database напрямую;
- production env и tokens;
- nginx/PHP configuration;
- реальные пользовательские данные.

Ошибка была ошибкой заполнения тестовой заявки, а не regression editor-релиза.

## 10. Точка остановки

Заявка `001/26` отправлена в GPM. Дальше проверить вручную:

1. назначенный логист видит `001/26` в «На модерации»;
2. editor сохраняет изменение;
3. другой логист заявку не видит;
4. назначенный логист публикует;
5. после публикации editor исчезает;
6. исполнитель Москвы видит заказ без адреса до назначения;
7. исполнитель другого города заказ не видит;
8. по возможности проверить ручные черновики частного логиста и клиента.

Не делать новый deploy для этой проверки. Использовать только синтетические
данные. Не печатать MobaXterm passwords, CRM/GPM `.env`, tokens и заголовки.

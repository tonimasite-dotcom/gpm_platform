# Частная проверка редактора ставки на Laravel 13

17.11.2026: реальный restore свежего SQL backup TS PASS в НОВОМ отдельном datadir:
72 таблицы, 3 399 842 строки; полные хеши содержимого, DDL и AUTO_INCREMENT совпали.
Частный MySQL выключен. Рабочие CRM и существующая synthetic-база не менялись.
`restore_ts_backup_stream.py` и `receive_ts_backup_restore.py` не запускают приложение,
миграции и scheduler; требуют отдельную сеть, socket и новый каталог, запас 3 GiB.
`sql_snapshot.py` проверяет мультимножества строк, включая дубли и generated columns.
Ключ остается локальным, plaintext SQL/архивы на ПК не сохраняются. Это проверка
backup restore, финансовый write rollback еще не принят. Точка продолжения:
PROJECT_HANDOFF_2026-11-17_APP_TESTING_RESUMED.md. Исторические состояния ниже.

16.11.2026: demo/email/TLS 33 PASS, rate HTTP-kernel/JWT/permissions 18 PASS,
Vue 21 PASS, offline frontend build PASS. Работающая TS не обновлена.
Актуальный контекст: PROJECT_HANDOFF_2026-11-16_TS_RESUMED.md.

Новые инструменты не имеют live apply: adapt_demo.py, adapt_scheduler.py,
adapt_frontend.py, restore_frontend_inputs.py работают только с сохраненным
отмеченным synthetic-кандидатом. Они уже применены, повтор запрещен.
Scheduler кандидата регистрирует ноль событий, отдельный GPM cron не меняется.
Новые debtor-команды и mail-методы отключены до работы с данными/вложениями.
Правило: .agents/skills/gpm-ts-debt-off/SKILL.md в корне проекта.

run_http_fixture.py требует отдельной network namespace, существующего datadir,
уникального run-id и запускает/выключает только synthetic MySQL. До/после сравнивает
строки всех таблиц. --prepare-gate использован один раз: добавлена только таблица
payout_settlement_gate с id=1; upstream миграция выплат не отмечена выполненной.
Теперь 74 таблицы. Metadata/edit card прошли; datatable пока требует
order_worker_mail_states. Финансовый откат и Auto_increment не приняты.

build_frontend.py строит offline, без npm install, с сохраненными private
node_modules. Лимит Node 3 GiB, core dumps OFF, reserve 3 GiB. Сборка уже принята,
повтор setup/resume не нужен. Исходники SCSS и build config сохранены от прежней TS;
их равенство основной не заявляется. UI в браузере еще не принят.

Это исходники адаптации и синтетической проверки, не пакет выпуска TS.
Штатные установщики прежнего runtime не меняются.

`adapt_worker_rate_history.py CANDIDATE` только проверяет известный SHA.
`--apply` допускается лишь для отмеченного `PRIVATE_BOT_FIXTURE` кандидата
с APP_ENV=testing и DB_DATABASE=bot_fixture. Скрипт сохраняет прежний файл
и передает в HistoryOrderService полный снимок заказа с новой ставкой и
явной подписью истории. Авторизация/права и общий сервис истории не меняются.
На сервере подтверждено состояние `already_adapted` и итоговый SHA.

`php worker_rate_private_test.php CANDIDATE` требует заранее подготовленный
изолированный PHP 8.5/Laravel 13, синтетическую MySQL и частные GPM-adapters.
Нельзя запускать против рабочей CRM. Тест не подготавливает и не запускает БД.
Его запускать только внутри окружения без внешней сети, после сверки назначения
socket/БД и снимка строк. После запуска проверить rollback всех таблиц и
штатно выключить частную БД. Контроль структуры/восстановления строк и выключение
выполняются внешним приватным runner; один этот PHP-тест их не доказывает.

15.11.2026 финальная версия: 14 сценариев PASS, строки всех 73 таблиц совпали
до/после rollback, частный MySQL выключен. Auth actor подменен; это проверка
контроллера и модельного guard, не JWT/middleware/UI и не реальные учетки.
Контекст и ограничения: PROJECT_HANDOFF_2026-11-15_BOT_TS_RATE_ACCEPTANCE.md.

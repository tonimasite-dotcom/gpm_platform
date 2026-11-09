# Продолжение подготовки ts после расширенной проверки документов

Прочитай AGENTS.md и PROJECT_HANDOFF_2026-11-09_TS_EXTENDED_DOCUMENTS.md.
Ветка work/ts-resume-2026-11-09, worktree .tmp/ts-resume-20261109, code 2d75426.
Исходную main с пользовательскими правками не менять. Ничего не deploy.

26 сценариев документов прошли, 80 файлов, 40 PDF/82 страницы/50 unique renders
проверены. Найдены и подготовлены только в private candidate: vat_summary
ActDataService, overlay act.docx с НДС и широкой суммой, overlay IP application2
с текущими doc_number/date вместо 033/22 и 2022. Исходные шаблоны/документы
не менялись, бинарники/реквизиты в Git не попали. Рецепт prepare_document_corrections.py
одноразовый и уже выполнен. Не merge/adapt заново поверх candidate.
Manifest candidate-manifest-documents-20261109.json, 1391 файлов, digest
f47de6309adb543870d844b043529124720fe1501d32fb447a74a3c908855548.

После правок 42/40 повторены, independent checker сохранил все исходные строки
72 таблиц, cash_source_captured объяснен, исходный audit-prefix цел. Все 6 private
MySQL OFF, datadir на месте, свободно около 1.97 GB. Новых полных копий без
оценки места не делать, старые попытки не удалять. Основная/live ts не менялись
и не читались. CI/deploy не запускались. Выпуск не готов.

Корень /root/gpm-ts-update/20261106-baseline-01, overlay document-template-overlays-20261109.
После-правочный fixture extended-document-fixtures-862723389003. Все варианты
и ошибки сохранены, raw errors и документы private. Локальные PDF/рендеры в
.tmp/crm-access-20261109/extended-documents-corrected. Безопасные JSON в audits/
crm-ts-extended-documents-2026-11-09. verify/finish уже выполнены, не перезаписывать
отчеты. resume_private_mysql.py принимает --report-name с новым безопасным basename;
прежнее имя отказ до старта. Этот запуск resume-extended-documents-20261109.json.

В switch-среде /root/gpm-ts-update/20261109-switch-01 по-прежнему runtime OLD,
next FINAL NEW предыдущего состава. Новые ActDataService/overlay туда не перенесены,
новой полной репетиции этого manifest нет. Старые switch-результаты не выдавать
за приемку нового пакета. Candidate markers в этом этапе не менялись.

Следующий независимый участок: cash/transport/returns/реальный путь выплаты,
потом UI/API документов. Contracts бизнес-приемка НЕ завершена: в настройке
performer_represented ООО числовой текст вместо представителя, имя не придумывать
и существующие реквизиты не менять. Есть orphan последнего пункта списка приложений
на новой странице; УПД двухстраничный landscape, длинные услуги не проверены.
Для НДС=0 пока getData-тест, полный PDF этого варианта не генерировали.

FPM/storage/planning/live preflight остаются: /opt/php74 master на 3 пула, общий
reload запрещен, безопасный ts-only opcache/cutover не проверен. public/storage
во внешний test.workstaffcrm.ru, покрытие backup цели не доказано. Live planning
guard еще не подготовлен. Сначала окончательный пакет с последствиями/backup/
rollback/активациями и замерами, затем согласование применения. Общие условия
уже подтверждены, не спрашивать заново. Scheduler/sync/publish/внешние отправки
как smoke не запускать, новые sync-правила отдельны, ответы коллег уже есть.
SSH key .tmp/crm-access-20261109/id_ed25519 в исходном Acer, в Git не добавлять.

Основную CRM не менять до завершения тестов/sync без отдельного явного согласования.
Read-only аудит разрешен без записей/заданий/миграций/переноса данных/секретов.
Очистка заявок не разрешает удаления схемы/таблиц/кода/аккаунтов/профилей/авторизации/
приглашений/аудита/конфигурации/секретов/backup/инфраструктуры, также в репетиции/откате.
Для жизненно важных объектов нужны перечень/последствия/восстановление/явное
согласование. Live такие объекты в этом этапе не менялись; private правки генератора
и шаблонов описаны. Ключи/env/identity/raw logs/SQL/реквизиты не печатать/не публиковать.

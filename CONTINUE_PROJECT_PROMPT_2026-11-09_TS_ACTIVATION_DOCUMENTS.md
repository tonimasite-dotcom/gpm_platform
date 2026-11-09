# Продолжение подготовки ts после legacy/activation/documents

Прочитай AGENTS.md, PROJECT_HANDOFF_2026-11-09_TS_ACTIVATION_DOCUMENTS.md и
CRM_TS_SWITCH_REHEARSAL_DESIGN_2026-11-09.md. Ветка work/ts-resume-2026-11-09,
worktree C:\Users\Acer\gpm_platform\.tmp\ts-resume-20261109. SHA: git log -1.
Исходную main с пользовательскими правками не трогать. Ничего не deploy.

9 legacy v1 до worker boundary, 16 activation и генератор счета (4 файла)
прошли. PDF текст/рендер/вид проверены, только вариант без печати/подписи.
Документы содержат private реквизиты ts: не копировать в Git/публичный отчет.
Визуальные копии в .tmp/crm-access-20261109 исходного Acer, все исходники/fixtures
сохранены. Данные всех 72 таблиц после отката synthetic-транзакций сверены;
baseline/checker прежние. 42 normal-сценария форм повторены, 3 PHP payload lint passed.
Код кандидата не менялся, все1391 файлов сверены, manifest dce57370efff2615fafde248addfb7808f13a0560254f2fb4e3982fd7a661b5d.
Предыдущие 40 functional/62GPM/834lint по-прежнему результаты предыдущего этапа.

Обе private MySQL снова OFF, datadir сохранены. --activation-document-report
уже выполнен; старые reports не перезаписывать/не удалять. Кандидат не merge/adapt
повторно. Planning marker кандидата отсутствует, worker marker прежний:
activation-тесты использовали отдельные private-fixtures и ничего не активировали.

Следующий шаг — НОВАЯ private-среда для полного переключения/возврата, явные
идентичности старой/новой версии и negative checks, реализация reviewed design.
Текущий GpmTsRehearsal новый root/DB отвергнет. Не подделывать live TS path,
APP_URL или mounts, не отключать guards. Отдельная новая DB + сохраненная
замороженная исходная DB/файлы для возврата, никаких DROP/migrate:rollback.
Полный switch/rollback еще НЕ сделан, окно НЕ измерено. Весь backup/restore
ранее проверен отдельно, это не полный возврат работающего runtime.
PlanningDayBoundary еще без ts/private guard, нужен свой cutover AUTO_INCREMENT-1
под lock, не MAX(id) и не граница основной. Не включать scheduler/sync/publish
как smoke. Далее также UI, ACT/UPD/печати, cash/transport/returns/путь выплаты.

SSH root 5.183.191.222 с игнорируемым .tmp/crm-access-20261109/id_ed25519.
Корень /root/gpm-ts-update/20261106-baseline-01. Age/key/ciphertext см. DATA_AND_RECOVERY.
Секреты/.env/markers/raw-errors не печатать и не коммитить. Live только после
конкретного checked package review (JWT/API permission fixes тоже); общие пять
условий владелец уже подтвердил. Новые sync-правила отдельно, ответы уже есть.

Основную CRM не менять до завершения тестов/sync без отдельного явного согласования.
Разрешен только read-only аудит без записей/заданий/миграций/переноса данных/секретов.
В этом этапе основная не читалась, обе live CRM и жизненно важные компоненты не менялись.
Очистка заявок не разрешает удаление таблиц/схемы/кода/аккаунтов/профилей/авторизации/
приглашений/аудита/конфигурации/секретов/backup/инфраструктуры. Для жизненно важных
объектов нужен отдельный перечень/последствия/восстановление/явное согласование.
Это действует и в репетиции/откате. Сохраненные экземпляры/реальные строки не удалять.

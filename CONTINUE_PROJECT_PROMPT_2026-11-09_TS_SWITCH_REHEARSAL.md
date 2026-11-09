# Продолжение подготовки ts после private switch/rollback

Прочитай AGENTS.md, PROJECT_HANDOFF_2026-11-09_TS_SWITCH_REHEARSAL.md,
switch/README.md в integrations/workstaff-test-crm/baseline и audits/crm-ts-switch-2026-11-09.
Ветка work/ts-resume-2026-11-09, worktree .tmp/ts-resume-20261109, code 9ad6465.
Исходную main с пользовательскими изменениями не менять. Не deploy.

37 миграций завершены дважды в НОВОЙ частной среде, новая приемка и полный
возврат OLD проверены. 8 email, 42 forms, 40 functional, 5 smoke, 6 negative,
72 исходных таблицы сохранены. Не называть это одним непрерывным прогоном:
были timeout/поврежденная private DB и две ошибки инструментов. Все попытки
сохранены. Миграции 136.856 сек, verified rollback 36.281 сек; простой live не измерен.

В private LoginController воспроизведено принятие чужого кода при правильном
пароле, исправлено ограничением Rule::exists по email запроса; флаг почты уже
учитывался и не менялся. 8 тестов проходят, исходники/до-после сохранены.
Новый manifest candidate-manifest-email-code-20261109.json, 1391 файлов, digest
51cc81a6b5fe049b81296c7cb3c2fc9059e2d5d507b771c94d95bd5ae9a397cf.
Кандидат не merge/adapt повторно. Marker исходного candidate не менять.

Новая среда /root/gpm-ts-update/20261109-switch-01: runtime OLD, next FINAL NEW;
DB final gpm_ts_switch_final в mysql-new/data. accepted-new-first-run сохранен.
Tools /root/gpm-ts-update/switch-tools-20261109. ВСЕ private MySQL OFF, данные
на месте; source /root/gpm-ts-update/20261106-baseline-01 также OFF/сохранен.
Все mutating-скрипты одноразовые; не rerun и не удалять отчеты ради повтора.
Свободно около 2 GB: еще одну полную копию делать нельзя без оценки места.

Следующий независимый участок: UI/ACT/UPD/печати/контракты, оставшиеся cash/
transport/returns/выплаты; подробности прошлой приемки в ACTIVATION_DOCUMENTS.
Одновременно можно продолжать read-only ts preflight/storage/FPM. Найден
/opt/php74/etc/php-fpm.d/ts.workstaffcrm.ru.conf и master на 3 пула; общий reload
запрещен. Эффективный opcache и ts-only смена кода не проверены. Public/storage
указывает во внешний test.workstaffcrm.ru: backup цели не доказан. TS app flag
почты true, DB ts_workstaff. Реальные env/секреты не печатать.
Нужна также настоящая ts-адаптация planning boundary, сейчас новая команда
guard адаптирована только для private slot. Не выдавать private helpers за live-пакет.

Не включать scheduler/sync/publish как smoke; внешние письма/ЭДО/банкинг не слать.
Финальный checkpoint и конкретное согласование выпуска еще впереди. Все общие
условия уже подтверждены, повторно их не спрашивать. Новые sync-решения отдельно,
ответы есть. SSH key в исходном .tmp/crm-access-20261109/id_ed25519 (игнорируется).

Основную CRM не менять до завершения тестов/sync без отдельного явного согласования.
Read-only аудит разрешен без записей/заданий/миграций/переноса данных/секретов.
Основная в этом этапе не читалась, live CRM не менялись. Очистка заявок не
разрешает удаления схемы/таблиц/кода/аккаунтов/профилей/авторизации/приглашений/
аудита/конфигурации/секретов/backup/инфраструктуры, в том числе в репетиции/откате.
Для жизненно важных объектов нужны перечень/последствия/восстановление/явное
согласование. Только частное изменение auth выполнено и описано в handoff.

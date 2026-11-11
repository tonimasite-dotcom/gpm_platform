# Промпт для нового чата

Продолжи GPM из безопасно остановленного сеанса 10.11.2026. Сначала восстанови
контекст, не запускай обновление автоматически. Ветка work/ts-resume-2026-11-09;
git fetch origin и проверка HEAD/статуса обязательны. Старый original checkout
на HEAD6764992 и его пользовательская .vscode не являются актуальной веткой:
не reset/stash/commit чужие изменения. Текущий worktree на этом ПК:
C:/Users/Юра/Desktop/gpm_platform/gpm_platform/.tmp/ts-resume-20261110.

Прочитай AGENTS.md, README.md,
PROJECT_HANDOFF_2026-11-10_SAFE_STOP_FULL_SNAPSHOT.md и
snapshots/2026-11-10-safe-stop/. Там manifest со ссылками/байтами/SHA encrypted assets
GitHub Release snapshot-20261110-order-parity-stop. Крупные данные находятся
в Release того же репозитория, не являются plaintext файлами Git tree.

При необходимости скачай assets авторизованным gh:
gh release download snapshot-20261110-order-parity-stop --repo tonimasite-dotcom/gpm_platform --dir .tmp/session-restore-20261110
Используй НОВУЮ приватную папку. Проверь каждый файл по manifest SHA до расшифровки.
Один backup разделен на36 encrypted частей. Собери его инструментом из Git:
python integrations/workstaff-test-crm/baseline/order-parity/join_snapshot_parts.py --manifest snapshots/2026-11-10-safe-stop/ARTIFACTS.json --directory .tmp/session-restore-20261110
Проверяется SHA каждой части и общего ciphertext, расшифровки и перезаписи нет.
Оригиналы всех encrypted файлов также сохранены на сервере (server_path в manifest)
и локально; их можно забрать по SSH, не создавая snapshot заново.
Ключ отдельно: original-checkout/.tmp/production-backup-20261015/age-identity.txt;
age.exe: original-checkout/.tmp/full-project-snapshot-20261015/tools/age.exe.
SSH key Path.home()/.ssh/id_ed25519, known-hosts сохранен в private client context.
Значения ключей/паролей/кодов/JWT не читать в вывод и не отправлять в чат.

Открой FULL_PRIVATE_HANDOFF.md из расшифрованного snapshot. Там полная точка
продолжения, evidence, карта файлов и operator scripts. Visible transcript и
два исходных скриншота включены; system/developer/reasoning/raw guardian записи
не экспортировались. Текущий snapshot/key проверены отдельно от прежнего
GPM_FULL_CHAT_PRIVATE_20261110.zip.age, для которого нужен старый отдельный
ключ20261109 с Acer. Ciphertext прежнего архива сохранен, текущий ключ его не открыл.

Если сервер на месте, НЕ восстанавливай архив поверх него: рабочие каталоги
уже сохранены. ROOT=/root/gpm-ts-update/order-parity-20261110-02,
AUDIT=/root/gpm-ts-update/order-parity-audit-20261110-01.
Приватные MySQL и caretakers остановлены, все datadir/baseline/failed runs сохранены.
На live TS остается demo-06 c4e5ef2, CI42802391274 SUCCESS, deployment PASS;
maintenance снят, email-код владелец подтвердил, деловые отправки/debt-off действуют.
Новый candidate не выпущен и пока не deployable.

Последний подтвержденный объем: все по заявкам TS идентично основной — визуал
и логика, включая ранее описанные расчетные/кассовые/документные зависимости и
срок редактирования. Лишние TS-only поля/виджеты убрать из UI, не добавлять обратно
ради GPM. Service-only GPM backend сохранить отдельно. ТОТ ЖЕ ОБЪЕМ НЕ СПРАШИВАТЬ
ПОВТОРНО. Это не разрешает удаления колонок/таблиц/аккаунтов/инфраструктуры.
Обычный email-вход и проверки авторизации сохранить; отмененные auth/local-inbox
изменения старых пакетов автоматически не возвращать. Новые sync-решения отдельно,
ответы коллег уже есть, не считать отсутствующими.

Ближайший шаг после прочтения контекста: разобрать последний private migration
failure и согласованность DB/filesystem activation state. Не удалять маркер и
не ослаблять guard. Следующий прогон — новая matched private копия, не rerun
поверх failed datasets. Далее доказать сохранность старых строк/денег/прав,
реальную API/формы/финансы/документы/роль приемку, audit новых outbound callers,
GPM-регрессии, повторный frontend build после переводов без private .env, fresh
main-source SHA. Старые тесты не выдавать за новую приемку. Только после green
проверок, CI и fresh verified backup готовить отдельный TS release.

Основную CRM ТОЛЬКО читать: никаких ее code/settings/DB writes, Laravel/заданий/
миграций/sync и переноса рабочих данных/секретов. Ее выпуск требует отдельного
явного согласования после тестов. В этом сеансе основная только читалась;
соседний test и shared FPM/master/cron/MySQL не трогать.

Убирание полей/очистка заявок не разрешают удаления таблиц/схемы/кода/аккаунтов/
профилей/auth/приглашений/аудита/конфигурации/секретов/backup/инфраструктуры,
включая private rehearsal. Для жизненно важных объектов отдельная задача,
перечень, последствия, восстановление, явное согласование. Старое разрешение
трех backup-дубликатов исполнено, новых удалений не разрешает. В новом этапе
live ничего жизненно важного не менялось. Внутренние отчеты не публиковать в
public GitHub plaintext. Пиши кратко по-русски, используй е.

# Продолжить перед выпуском минимальной защиты TS

Сначала `git fetch origin`: в исходном worktree может оставаться старый HEAD
6764992. Работать в ветке `work/ts-resume-2026-11-09`, отдельный worktree текущего
компьютера `C:/Users/Юра/Desktop/gpm_platform/gpm_platform/.tmp/ts-resume-20261110`.
Пользовательскую .vscode и старый worktree не сбрасывать/не присоединять к commits.

Прочитать AGENTS.md, README.md,
PROJECT_HANDOFF_2026-11-10_TS_DEMO_PACKAGE_READY.md,
integrations/workstaff-test-crm/baseline/demo/README.md и audits/crm-ts-demo-2026-11-10/.
Прежний FULL_CHAT_SNAPSHOT нужен для истории, актуальная точка теперь здесь.

Code commit b24a97da099b93bd6c5d50bf7c032a70fd7baec1, отправлен в GitHub.
CI 42787704677 SUCCESS (backend+flutter). Следующий docs commit смотреть git log.
Deployment НЕ выполнялся, рабочая TS все еще SMTP/Pusher; permanent daily mail OFF
на live еще не доказан. Не выдавать готовый private пакет за рабочее обновление.

Владелец хочет тестировать GPM и входить в ts.workstaffcrm.ru через браузер,
сверять заявки. Подготовлен закрытый зашифрованный ящик кодов по SSH в локальное
окно владельца, без email/нового web endpoint и без обхода пароля/captcha/кода/JWT.
Для реального входа понадобились адресные JWT remember / чужой-code исправления.
Перед live apply нужно отдельное согласование именно готового пакета/последствий,
поскольку это доставка кодов и код авторизации. Общие условия TS-only/данных/
короткой остановки ранее согласованы; их не спрашивать повторно. Если владелец
уже одобрил конкретный пакет после этого снимка, продолжать без повторного вопроса.

Ровно 27 файлов: 24 старых + три новых helper. Manifest SHA
c350b69976a1ff4b43a40878050299ff1dff48bbbc6a172da18a8c16d8860531.
Пакет не переносит Kernel/Order.php/37 миграций/новые финансы/24ч LogistEditAccess/
документы и не меняет GPM hooks/rate/logist guard/routes/roles/env/cron/secret.
Ежедневная почта OFF, побочные mail/SMS/IMAP/bank/calls/геокодер/Dadata demo-denial,
broadcast null. Текущие captcha/security/OAuth проверки не подменены успехом.
Новые правила sync отдельны; ответы коллег уже есть, не писать «ждем ответов».

PASS: 80 transport/inbox; 14 реальных login/verify/JWT/API на private recovery DB;
все строки 72 private таблиц до/после совпали, синтетические учетки откатились;
11+16+35 GPM; 31 отказ/возобновление установки; 7 localhost UI; PHP 7.4 lint; CI.
15 legacy methods fail PHP type checks before transport, не считаются исправным
старым почтовым клиентом. Первый auth-прогон был не принят по причинам fixture/
reap процесса; успешен прогон 02. Все шесть private MySQL OFF, datadir сохранены.
Не повторять старые тесты без новых изменений/неясности.

Сервер: SSH root@5.183.191.222, существующий ключ текущего пользователя в .ssh,
known_hosts в исходном checkout .tmp/test-crm-known-hosts. Значения не печатать.
Final overlay /root/gpm-ts-update/20261110-demo-04/runtime,
tools /root/gpm-ts-update/demo-tools-20261110; demo-01/02/03 не удалять/не перезаписывать.
W=/root/gpm-ts-update/20261106-baseline-01 и S=/root/gpm-ts-update/20261109-switch-01
сохранены. Не rerun init/prepare/merge/restore/migrations/cleanup поверх состояния.

Свежий targeted backup только кода: demo-04/code-backup/ts-demo-code-before.tar.gz.age,
40682 bytes, SHA 4d1555014fd01a636d21444076a5aabdfc95236ad7e2cee17e3198c0d621cc01.
Восстановлены 24 файла, SHA совпали; отсутствие трех новых учтено. Локально
worktree/.tmp/demo-code-backup-04. Ключ отдельно в исходном checkout
.tmp/production-backup-20261015/age-identity.txt. Не выводить/не публиковать.
Это не новая полная SQL/files-копия: в apply нет SQL/migration/seed/правок live данных.

FPM effective: только TS socket /var/run/ts.workstaffcrm.ru.sock, PHP 7.4.33,
opcache validate_timestamps=1, freq=2, invalidate доступен; общих reload не было.
Установка: свой TS maintenance, reserve/atomic swaps с uid/gid/mode, только TS
opcache invalidate, probe реального guarded FPM, HTTP 401 без JWT и 200 главной.
При отказе держать/вернуть свой maintenance, resume только того же manifest.
Не возвращать SMTP-способный baseline автоматически. Existing sync cron не менять
и живой sync как smoke не запускать. Public/storage ведет во внешний test;
он не нужен private inbox и его target не обходился.

После отдельного одобрения конкретного пакета: свежий dry-run; при устаревшем backup
или source drift новый checkpoint без затирания прежних; TS-only apply с reviewed SHA;
FPM/HTTP receipts; открыть владельцу local_login_inbox.py. Обычный пароль/captcha
он вводит сам, код берет в окне 127.0.0.1. Коды/JWT/password не печатать в чат/логи.
Ручная браузерная приемка и подготовленная заявка в связке приложения еще остаются.
Не придумывать реальные тестовые заказы/перенос данных или новые sync-правила.

Обязательные ограничения:
- Основную CRM только читать для сверки. Без ее правок файлов/настроек/БД,
  загрузки Laravel/заданий/миграций/sync и переноса рабочих данных/секретов.
  Будущий выпуск отдельно явно согласуется после тестов. Сегодня основная даже
  не читалась, не менялась; жизненно важные live компоненты не менялись, подготовлены
  auth/delivery изменения только TS и они ожидают согласования перед выпуском.
- Очистка заявок не разрешает удаления схемы/таблиц/кода/аккаунтов/профилей/
  авторизации/приглашений/аудита/конфигурации/секретов/backup/инфраструктуры, также
  в репетиции. Нужны отдельная задача, перечень/последствия/восстановление/явное
  согласование для жизненно важных объектов. Новых удалений не разрешено;
  предыдущее разрешение трех backup-дубликатов уже исполнено.

Фиксировать новый этап в Git/README/новом PROJECT_HANDOFF с commit/CI/deploy/backup,
остатком ручной приемки и границами систем. Писать кратко, использовать е.
